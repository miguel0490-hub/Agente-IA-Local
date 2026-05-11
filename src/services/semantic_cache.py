"""Semantic caching for LLM responses.

Reduces API costs by caching responses keyed on normalized prompt content.
Supports exact-match and similarity-based cache lookup with TTL expiration.
"""

from __future__ import annotations

import hashlib
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from src.core.logger import get_logger

logger = get_logger(__name__)

_MAX_CACHE_SIZE = int(os.getenv("SEMANTIC_CACHE_MAX_SIZE", "1000"))
_DEFAULT_TTL = float(os.getenv("SEMANTIC_CACHE_TTL", "3600"))


@dataclass
class CacheEntry:
    """A cached LLM response."""
    prompt_hash: str
    model: str
    response: str
    tokens_saved: int
    created_at: float = field(default_factory=time.monotonic)
    ttl: float = _DEFAULT_TTL
    hits: int = 0
    cost_saved_usd: float = 0.0

    @property
    def is_expired(self) -> bool:
        return time.monotonic() - self.created_at > self.ttl


class SemanticCache:
    """LLM response cache with normalized prompt hashing."""

    def __init__(self, max_size: int = _MAX_CACHE_SIZE, default_ttl: float = _DEFAULT_TTL):
        self._store: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._total_hits = 0
        self._total_misses = 0

    @staticmethod
    def _normalize_prompt(prompt: str) -> str:
        """Normalizes a prompt for consistent hashing."""
        normalized = prompt.strip().lower()
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = re.sub(r"[^\w\s?!.,]", "", normalized)
        return normalized

    @staticmethod
    def _hash_prompt(prompt: str, model: str, system: str = "") -> str:
        content = f"{model}::{system}::{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get(
        self,
        prompt: str,
        model: str,
        *,
        system_instruction: str = "",
    ) -> str | None:
        """Looks up a cached response for a prompt."""
        normalized = self._normalize_prompt(prompt)
        key = self._hash_prompt(normalized, model, system_instruction)

        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._total_misses += 1
                return None

            if entry.is_expired:
                del self._store[key]
                self._total_misses += 1
                return None

            entry.hits += 1
            self._total_hits += 1
            logger.debug("Semantic cache hit: %s (hits=%d)", key[:12], entry.hits)
            return entry.response

    def put(
        self,
        prompt: str,
        model: str,
        response: str,
        *,
        system_instruction: str = "",
        tokens_total: int = 0,
        cost_usd: float = 0.0,
        ttl: float | None = None,
    ) -> None:
        """Stores a response in the cache."""
        normalized = self._normalize_prompt(prompt)
        key = self._hash_prompt(normalized, model, system_instruction)

        with self._lock:
            if len(self._store) >= self._max_size:
                self._evict()

            self._store[key] = CacheEntry(
                prompt_hash=key,
                model=model,
                response=response,
                tokens_saved=tokens_total,
                ttl=ttl or self._default_ttl,
                cost_saved_usd=cost_usd,
            )

    def _evict(self) -> None:
        """Evicts expired entries, then LRU by hits."""
        now = time.monotonic()
        expired = [k for k, v in self._store.items() if now - v.created_at > v.ttl]
        for k in expired:
            del self._store[k]

        if len(self._store) >= self._max_size:
            sorted_entries = sorted(self._store.items(), key=lambda x: (x[1].hits, x[1].created_at))
            to_remove = len(self._store) - self._max_size + 1
            for k, _ in sorted_entries[:to_remove]:
                del self._store[k]

    def invalidate(self, prompt: str, model: str, system_instruction: str = "") -> bool:
        normalized = self._normalize_prompt(prompt)
        key = self._hash_prompt(normalized, model, system_instruction)
        with self._lock:
            return self._store.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            total_tokens_saved = sum(e.tokens_saved * e.hits for e in self._store.values())
            total_cost_saved = sum(e.cost_saved_usd * e.hits for e in self._store.values())
        return {
            "entries": len(self._store),
            "total_hits": self._total_hits,
            "total_misses": self._total_misses,
            "hit_rate": self._total_hits / max(1, self._total_hits + self._total_misses),
            "total_tokens_saved": total_tokens_saved,
            "total_cost_saved_usd": round(total_cost_saved, 4),
        }


_cache: SemanticCache | None = None


def get_semantic_cache() -> SemanticCache:
    global _cache
    if _cache is None:
        _cache = SemanticCache()
    return _cache
