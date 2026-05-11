"""Tests for cost optimization: semantic cache, model routing, failover."""

from __future__ import annotations

import pytest

from src.services.semantic_cache import SemanticCache, get_semantic_cache
from src.services.model_router import (
    ModelProfile,
    ModelRouter,
    ProviderHealth,
    TaskComplexity,
    classify_task_complexity,
    get_model_router,
)


class TestSemanticCache:
    def test_cache_miss(self):
        cache = SemanticCache()
        assert cache.get("hello", "gpt-4") is None

    def test_cache_hit(self):
        cache = SemanticCache()
        cache.put("hello", "gpt-4", "Hi there!", tokens_total=10)
        assert cache.get("hello", "gpt-4") == "Hi there!"

    def test_normalized_prompt_match(self):
        cache = SemanticCache()
        cache.put("Hello World!", "gpt-4", "response")
        assert cache.get("  hello   world!  ", "gpt-4") == "response"

    def test_different_models_separate(self):
        cache = SemanticCache()
        cache.put("hello", "gpt-4", "response-4")
        cache.put("hello", "gpt-3.5", "response-3.5")
        assert cache.get("hello", "gpt-4") == "response-4"
        assert cache.get("hello", "gpt-3.5") == "response-3.5"

    def test_ttl_expiration(self):
        cache = SemanticCache()
        cache.put("hello", "gpt-4", "response", ttl=0.01)
        import time
        time.sleep(0.02)
        assert cache.get("hello", "gpt-4") is None

    def test_eviction_on_full(self):
        cache = SemanticCache(max_size=3)
        cache.put("a", "m", "1")
        cache.put("b", "m", "2")
        cache.put("c", "m", "3")
        cache.put("d", "m", "4")
        assert len(cache._store) <= 3

    def test_invalidate(self):
        cache = SemanticCache()
        cache.put("hello", "gpt-4", "response")
        assert cache.invalidate("hello", "gpt-4")
        assert cache.get("hello", "gpt-4") is None

    def test_clear(self):
        cache = SemanticCache()
        cache.put("a", "m", "1")
        cache.put("b", "m", "2")
        cache.clear()
        assert len(cache._store) == 0

    def test_stats(self):
        cache = SemanticCache()
        cache.put("hello", "gpt-4", "response", tokens_total=100, cost_usd=0.01)
        cache.get("hello", "gpt-4")
        cache.get("hello", "gpt-4")
        cache.get("miss", "gpt-4")
        stats = cache.get_stats()
        assert stats["total_hits"] == 2
        assert stats["total_misses"] == 1
        assert stats["entries"] == 1

    def test_system_instruction_affects_key(self):
        cache = SemanticCache()
        cache.put("hello", "gpt-4", "r1", system_instruction="sys1")
        cache.put("hello", "gpt-4", "r2", system_instruction="sys2")
        assert cache.get("hello", "gpt-4", system_instruction="sys1") == "r1"
        assert cache.get("hello", "gpt-4", system_instruction="sys2") == "r2"


class TestModelRouter:
    def _make_router(self) -> ModelRouter:
        return ModelRouter([
            ModelProfile("cheap", "cheap-model", 0.0001, 32_000, 200, quality_tier=1),
            ModelProfile("mid", "mid-model", 0.001, 128_000, 500, quality_tier=3),
            ModelProfile("premium", "premium-model", 0.01, 1_000_000, 2000, quality_tier=4, supports_vision=True),
        ])

    def test_selects_cheapest_for_simple(self):
        router = self._make_router()
        model = router.select_model(complexity=TaskComplexity.SIMPLE)
        assert model is not None
        assert model.provider == "cheap"

    def test_selects_quality_for_complex(self):
        router = self._make_router()
        model = router.select_model(complexity=TaskComplexity.COMPLEX)
        assert model is not None
        assert model.quality_tier >= 3

    def test_respects_cost_constraint(self):
        router = self._make_router()
        model = router.select_model(max_cost_per_1k=0.0005)
        assert model is not None
        assert model.cost_per_1k_tokens <= 0.0005

    def test_respects_vision_requirement(self):
        router = self._make_router()
        model = router.select_model(require_vision=True)
        assert model is not None
        assert model.supports_vision

    def test_respects_context_requirement(self):
        router = self._make_router()
        model = router.select_model(min_context=500_000)
        assert model is not None
        assert model.max_context >= 500_000

    def test_preferred_provider(self):
        router = self._make_router()
        model = router.select_model(preferred_provider="mid")
        assert model.provider == "mid"

    def test_failover(self):
        router = self._make_router()
        for _ in range(5):
            router.record_failure("cheap")
        fallback = router.get_failover("cheap")
        assert fallback is not None
        assert fallback.provider != "cheap"

    def test_health_tracking(self):
        router = self._make_router()
        router.record_success("cheap", 150.0)
        router.record_success("cheap", 200.0)
        health = router.get_provider_health()
        assert health["cheap"]["health"] == "healthy"
        assert health["cheap"]["total_requests"] == 2

    def test_provider_goes_down(self):
        router = self._make_router()
        for _ in range(5):
            router.record_failure("cheap")
        health = router.get_provider_health()
        assert health["cheap"]["health"] == "down"

    def test_no_models_returns_none(self):
        router = ModelRouter([])
        assert router.select_model() is None

    def test_estimate_cost(self):
        router = self._make_router()
        model = ModelProfile("test", "test", 0.001, 128_000)
        cost = router.estimate_cost(model, 5000)
        assert cost == pytest.approx(0.005)


class TestTaskClassification:
    def test_simple_question(self):
        assert classify_task_complexity("What is 2+2?") == TaskComplexity.SIMPLE

    def test_complex_task(self):
        result = classify_task_complexity(
            "Analyze and compare these two architectures, then design an optimized solution"
        )
        assert result in (TaskComplexity.COMPLEX, TaskComplexity.MODERATE)

    def test_creative_task(self):
        assert classify_task_complexity("Write a creative story about a robot") == TaskComplexity.CREATIVE

    def test_image_forces_complex(self):
        assert classify_task_complexity("What is this?", has_image=True) == TaskComplexity.COMPLEX


class TestGetSingletons:
    def test_semantic_cache_singleton(self):
        c1 = get_semantic_cache()
        c2 = get_semantic_cache()
        assert c1 is c2

    def test_model_router_singleton(self):
        r1 = get_model_router()
        r2 = get_model_router()
        assert r1 is r2
