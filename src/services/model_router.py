"""Adaptive model routing, failover, and cost-aware orchestration.

Routes LLM requests to the optimal provider based on task complexity,
cost constraints, latency requirements, and provider health.
"""

from __future__ import annotations

import os
import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.core.logger import get_logger

logger = get_logger(__name__)


class TaskComplexity(Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    CREATIVE = "creative"


class ProviderHealth(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


@dataclass
class ModelProfile:
    """Capability and cost profile for a model."""
    provider: str
    model_id: str
    cost_per_1k_tokens: float
    max_context: int
    avg_latency_ms: int = 1000
    supports_streaming: bool = True
    supports_vision: bool = False
    quality_tier: int = 3  # 1=basic, 2=good, 3=premium, 4=frontier
    enabled: bool = True


@dataclass
class ProviderStatus:
    """Real-time health tracking for a provider."""
    provider: str
    health: ProviderHealth = ProviderHealth.HEALTHY
    consecutive_failures: int = 0
    last_failure: float = 0.0
    avg_latency_ms: float = 0.0
    total_requests: int = 0
    total_errors: int = 0

    def record_success(self, latency_ms: float) -> None:
        self.consecutive_failures = 0
        self.health = ProviderHealth.HEALTHY
        self.total_requests += 1
        alpha = 0.1
        self.avg_latency_ms = (1 - alpha) * self.avg_latency_ms + alpha * latency_ms

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        self.last_failure = time.monotonic()
        self.total_errors += 1
        self.total_requests += 1
        if self.consecutive_failures >= 5:
            self.health = ProviderHealth.DOWN
        elif self.consecutive_failures >= 2:
            self.health = ProviderHealth.DEGRADED


_DEFAULT_MODELS: list[ModelProfile] = [
    ModelProfile("gemini", "gemini-2.5-pro", 0.00125, 1_000_000, 2000, quality_tier=4, supports_vision=True),
    ModelProfile("groq", "llama-3.3-70b-versatile", 0.00059, 128_000, 500, quality_tier=3),
    ModelProfile("openrouter", "openrouter/auto", 0.001, 128_000, 1500, quality_tier=3),
]


class ModelRouter:
    """Routes requests to the optimal model based on context and constraints."""

    def __init__(self, models: list[ModelProfile] | None = None) -> None:
        self._models = list(_DEFAULT_MODELS) if models is None else models
        self._status: dict[str, ProviderStatus] = {}
        self._lock = threading.Lock()

        for m in self._models:
            self._status[m.provider] = ProviderStatus(provider=m.provider)

    def select_model(
        self,
        *,
        complexity: TaskComplexity = TaskComplexity.MODERATE,
        max_cost_per_1k: float | None = None,
        require_vision: bool = False,
        require_streaming: bool = False,
        min_context: int = 0,
        preferred_provider: str | None = None,
    ) -> ModelProfile | None:
        """Selects the best model for a request based on constraints."""
        candidates = [
            m for m in self._models
            if m.enabled
            and self._is_healthy(m.provider)
            and (not require_vision or m.supports_vision)
            and (not require_streaming or m.supports_streaming)
            and m.max_context >= min_context
            and (max_cost_per_1k is None or m.cost_per_1k_tokens <= max_cost_per_1k)
        ]

        if not candidates:
            logger.warning("No healthy models match constraints")
            candidates = [m for m in self._models if m.enabled]
            if not candidates:
                return None

        if preferred_provider:
            preferred = [c for c in candidates if c.provider == preferred_provider]
            if preferred:
                return preferred[0]

        min_tier = {
            TaskComplexity.SIMPLE: 1,
            TaskComplexity.MODERATE: 2,
            TaskComplexity.COMPLEX: 3,
            TaskComplexity.CREATIVE: 3,
        }.get(complexity, 2)

        tier_candidates = [c for c in candidates if c.quality_tier >= min_tier]
        if tier_candidates:
            candidates = tier_candidates

        return min(candidates, key=lambda m: m.cost_per_1k_tokens)

    def get_failover(self, failed_provider: str, **constraints: Any) -> ModelProfile | None:
        """Returns a fallback model when the primary provider fails."""
        alternatives = [
            m for m in self._models
            if m.provider != failed_provider
            and m.enabled
            and self._is_healthy(m.provider)
        ]
        if not alternatives:
            return None
        return min(alternatives, key=lambda m: m.cost_per_1k_tokens)

    def record_success(self, provider: str, latency_ms: float) -> None:
        with self._lock:
            if provider in self._status:
                self._status[provider].record_success(latency_ms)

    def record_failure(self, provider: str) -> None:
        with self._lock:
            if provider in self._status:
                self._status[provider].record_failure()

    def _is_healthy(self, provider: str) -> bool:
        status = self._status.get(provider)
        if not status:
            return True
        if status.health == ProviderHealth.DOWN:
            if time.monotonic() - status.last_failure > 60:
                return True  # Allow retry after cooldown
            return False
        return True

    def get_provider_health(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "health": s.health.value,
                "avg_latency_ms": round(s.avg_latency_ms, 1),
                "total_requests": s.total_requests,
                "error_rate": s.total_errors / max(1, s.total_requests),
                "consecutive_failures": s.consecutive_failures,
            }
            for name, s in self._status.items()
        }

    def add_model(self, model: ModelProfile) -> None:
        self._models.append(model)
        self._status[model.provider] = ProviderStatus(provider=model.provider)

    def estimate_cost(self, model: ModelProfile, tokens: int) -> float:
        return (tokens / 1000) * model.cost_per_1k_tokens


def classify_task_complexity(prompt: str, *, has_image: bool = False) -> TaskComplexity:
    """Heuristic classification of task complexity for routing."""
    word_count = len(prompt.split())

    complexity_indicators = [
        "analyze", "compare", "synthesize", "evaluate", "architect",
        "design", "implement", "refactor", "optimize", "debug",
    ]
    creative_indicators = [
        "write", "create", "generate", "compose", "imagine",
        "story", "poem", "essay", "creative",
    ]

    prompt_lower = prompt.lower()

    if any(w in prompt_lower for w in creative_indicators):
        return TaskComplexity.CREATIVE

    indicator_count = sum(1 for w in complexity_indicators if w in prompt_lower)

    if has_image or indicator_count >= 2 or word_count > 500:
        return TaskComplexity.COMPLEX
    elif indicator_count >= 1 or word_count > 100:
        return TaskComplexity.MODERATE
    else:
        return TaskComplexity.SIMPLE


_router: ModelRouter | None = None


def get_model_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router
