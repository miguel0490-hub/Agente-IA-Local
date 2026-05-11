"""Simple in-memory TTL cache for frequently-accessed, rarely-changing data.

Designed for user profiles, role lookups, and admin dashboard stats.
Thread-safe with minimal overhead.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable


class TTLCache:
    """Thread-safe cache with per-key time-to-live expiration."""

    def __init__(self, default_ttl: float = 60.0, max_size: int = 1000):
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()
        self._default_ttl = default_ttl
        self._max_size = max_size

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        with self._lock:
            if len(self._store) >= self._max_size:
                self._evict_expired()
                if len(self._store) >= self._max_size:
                    oldest_key = next(iter(self._store))
                    del self._store[oldest_key]
            self._store[key] = (value, time.monotonic() + (ttl or self._default_ttl))

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]


profile_cache = TTLCache(default_ttl=120.0, max_size=500)
stats_cache = TTLCache(default_ttl=30.0, max_size=50)
role_cache = TTLCache(default_ttl=300.0, max_size=500)


def cached_get(
    cache: TTLCache,
    key: str,
    loader: Callable[[], Any],
    ttl: float | None = None,
) -> Any:
    """Gets value from cache or calls loader to populate it."""
    value = cache.get(key)
    if value is not None:
        return value
    value = loader()
    if value is not None:
        cache.set(key, value, ttl)
    return value
