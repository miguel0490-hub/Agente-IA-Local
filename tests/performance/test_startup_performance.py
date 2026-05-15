"""Performance audit: startup time, import costs, and resource usage."""

from __future__ import annotations

import importlib
import os
import sys
import time
import tracemalloc

import pytest

os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")


class TestStartupPerformance:
    """Measures cold-start import times for critical modules."""

    @staticmethod
    def _timed_import(module_name: str) -> float:
        if module_name in sys.modules:
            del sys.modules[module_name]
        start = time.perf_counter()
        importlib.import_module(module_name)
        return time.perf_counter() - start

    def test_config_import_fast(self):
        elapsed = self._timed_import("src.core.config")
        assert elapsed < 2.0, f"src.core.config took {elapsed:.3f}s"

    def test_security_module_import_fast(self):
        elapsed = self._timed_import("src.core.security")
        assert elapsed < 2.0, f"src.core.security took {elapsed:.3f}s"

    def test_agent_tools_import_fast(self):
        elapsed = self._timed_import("src.core.agent_tools")
        assert elapsed < 2.0, f"src.core.agent_tools took {elapsed:.3f}s"

    def test_capabilities_import_fast(self):
        elapsed = self._timed_import("src.agents.capabilities")
        assert elapsed < 1.0, f"Capabilities took {elapsed:.3f}s"

    def test_tool_router_import_fast(self):
        elapsed = self._timed_import("src.agents.tool_router")
        assert elapsed < 1.0, f"Tool router took {elapsed:.3f}s"

    def test_health_monitor_import_fast(self):
        elapsed = self._timed_import("src.agents.health_monitor")
        assert elapsed < 1.0, f"Health monitor took {elapsed:.3f}s"

    def test_fallback_chain_import_fast(self):
        elapsed = self._timed_import("src.agents.model_fallback")
        assert elapsed < 1.0, f"Model fallback took {elapsed:.3f}s"

    def test_validators_import_fast(self):
        elapsed = self._timed_import("src.agents.validators.response_validator")
        assert elapsed < 1.0, f"Response validator took {elapsed:.3f}s"

    def test_gateway_import_fast(self):
        elapsed = self._timed_import("src.gateway.app")
        assert elapsed < 3.0, f"Gateway took {elapsed:.3f}s"


class TestLazyImportVerification:
    """Verifies that heavy SDKs are NOT loaded at import time."""

    def test_google_genai_not_imported_at_startup(self):
        for mod in list(sys.modules):
            if mod == "google.genai" or mod.startswith("google.genai."):
                del sys.modules[mod]

        importlib.import_module("src.services.llm_provider")

        google_genai_loaded = any(
            mod == "google.genai" or mod.startswith("google.genai.")
            for mod in sys.modules
        )
        assert not google_genai_loaded, "google.genai should be lazy-imported"

    def test_groq_not_imported_at_startup(self):
        for mod in list(sys.modules):
            if mod.startswith("groq"):
                del sys.modules[mod]

        groq_loaded = any(
            mod == "groq" or mod.startswith("groq.") for mod in sys.modules
            if not mod.startswith("src")
        )
        assert not groq_loaded, "groq should be lazy-imported"


class TestMemoryUsage:
    """Profiles memory consumption of critical operations."""

    def test_capability_registry_memory(self):
        tracemalloc.start()
        from src.agents.capabilities import CAPABILITY_PROFILES
        _ = list(CAPABILITY_PROFILES.values())
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert peak < 10 * 1024 * 1024, f"Registry peak memory: {peak / 1024 / 1024:.1f}MB"

    def test_tool_router_memory(self):
        tracemalloc.start()
        from src.agents.tool_router import ToolRouter
        router = ToolRouter()
        for _ in range(100):
            router.route("tech_lead", "test prompt")
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert peak < 20 * 1024 * 1024, f"Router 100x peak memory: {peak / 1024 / 1024:.1f}MB"

    def test_health_monitor_memory_bounded(self):
        tracemalloc.start()
        from src.agents.health_monitor import AgentHealthMonitor
        monitor = AgentHealthMonitor(hung_check_interval=60, default_timeout=60)
        for i in range(500):
            monitor.start_request(f"perf-{i}", "tech_lead", "gemini")
            monitor.complete_request(f"perf-{i}")
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert peak < 30 * 1024 * 1024, f"Monitor 500-req peak: {peak / 1024 / 1024:.1f}MB"

    def test_semantic_cache_memory_bounded(self):
        tracemalloc.start()
        from src.services.semantic_cache import SemanticCache
        cache = SemanticCache(max_size=100, default_ttl=60)
        for i in range(500):
            cache.put(f"prompt-{i}", "model", f"response-{i}" * 100, tokens_total=50)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert peak < 50 * 1024 * 1024, f"Cache 500-entry peak: {peak / 1024 / 1024:.1f}MB"


class TestLatencyBenchmarks:
    """Measures operation latencies."""

    def test_tool_routing_latency(self):
        from src.agents.tool_router import ToolRouter
        router = ToolRouter()
        times = []
        for _ in range(100):
            start = time.perf_counter()
            router.route("tech_lead", "busca información sobre Python")
            times.append(time.perf_counter() - start)
        avg = sum(times) / len(times)
        p99 = sorted(times)[98]
        assert avg < 0.01, f"Avg routing: {avg*1000:.2f}ms"
        assert p99 < 0.05, f"P99 routing: {p99*1000:.2f}ms"

    def test_prompt_composition_latency(self):
        from src.agents.prompt_manager import compose_system_prompt
        times = []
        for _ in range(100):
            start = time.perf_counter()
            compose_system_prompt("Base prompt", profile_name="tech_lead", task_type="code_review")
            times.append(time.perf_counter() - start)
        avg = sum(times) / len(times)
        assert avg < 0.02, f"Avg prompt composition: {avg*1000:.2f}ms"

    def test_response_validation_latency(self):
        from src.agents.validators.response_validator import validate_response
        sample = "```python\nprint('hello world')\n```\n\nEste es un texto de respuesta normal.\n" * 10
        times = []
        for _ in range(100):
            start = time.perf_counter()
            validate_response(sample)
            times.append(time.perf_counter() - start)
        avg = sum(times) / len(times)
        assert avg < 0.01, f"Avg validation: {avg*1000:.2f}ms"

    def test_gateway_health_latency(self):
        from fastapi.testclient import TestClient
        from src.gateway.app import app
        client = TestClient(app, raise_server_exceptions=False)
        times = []
        for _ in range(50):
            start = time.perf_counter()
            client.get("/api/v1/health")
            times.append(time.perf_counter() - start)
        avg = sum(times) / len(times)
        assert avg < 0.1, f"Avg health endpoint: {avg*1000:.2f}ms"
