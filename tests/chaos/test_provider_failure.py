"""Chaos test: LLM provider failure and recovery."""

from __future__ import annotations

import os
import time
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")

from src.agents.health_monitor import AgentHealthMonitor, CircuitState
from src.agents.model_fallback import ModelFallbackChain


class TestProviderDown:
    """Simulates a provider going completely down."""

    def setup_method(self):
        AgentHealthMonitor._instance = None
        self.monitor = AgentHealthMonitor.get_instance()
        self.chain = ModelFallbackChain()
        self.keys = {
            "GEMINI_API_KEY": "fake",
            "GROQ_API_KEY": "fake",
            "OPENROUTER_API_KEY": "fake",
        }

    def test_single_provider_failure_triggers_fallback(self):
        for _ in range(5):
            self.monitor.record_provider_failure("gemini")
        fallback = self.chain.get_fallback("Gemini", self.keys)
        assert fallback is not None
        assert fallback.name == "Groq"

    def test_two_providers_down_falls_to_third(self):
        for _ in range(5):
            self.monitor.record_provider_failure("gemini")
            self.monitor.record_provider_failure("groq")
        fallback = self.chain.get_fallback("Gemini", self.keys, already_tried={"Gemini", "Groq"})
        assert fallback is not None
        assert fallback.name == "OpenRouter"

    def test_all_cloud_providers_down_falls_to_ollama(self):
        for provider in ("gemini", "groq", "openrouter"):
            for _ in range(5):
                self.monitor.record_provider_failure(provider)

        fallback = self.chain.get_fallback(
            "Gemini", self.keys,
            already_tried={"Gemini", "Groq", "OpenRouter"},
        )
        assert fallback is not None
        assert fallback.name == "Ollama"

    def test_all_providers_exhausted_returns_none(self):
        for provider in ("gemini", "groq", "openrouter", "ollama"):
            for _ in range(5):
                self.monitor.record_provider_failure(provider)
        fallback = self.chain.get_fallback(
            "Gemini", self.keys,
            already_tried={"Gemini", "Groq", "OpenRouter", "Ollama"},
        )
        assert fallback is None

    def test_provider_recovery_after_timeout(self):
        breaker = self.monitor.get_breaker("gemini")
        breaker.recovery_timeout = 0.05
        for _ in range(5):
            self.monitor.record_provider_failure("gemini")
        assert not self.monitor.is_provider_available("gemini")

        time.sleep(0.1)
        assert self.monitor.is_provider_available("gemini")
        self.monitor.record_provider_success("gemini")
        breaker = self.monitor.get_breaker("gemini")
        assert breaker.state == CircuitState.CLOSED


class TestAPIKeyLoss:
    """Simulates losing an API key at runtime."""

    def test_empty_key_skips_provider(self):
        chain = ModelFallbackChain()
        keys = {"GEMINI_API_KEY": "", "GROQ_API_KEY": "valid"}
        available = chain.get_available_providers(keys)
        names = [t.name for t in available]
        assert "Gemini" not in names
        assert "Groq" in names

    def test_all_keys_missing(self):
        chain = ModelFallbackChain()
        available = chain.get_available_providers({})
        names = [t.name for t in available]
        assert "Ollama" in names
        assert len([n for n in names if n != "Ollama"]) == 0

    def test_key_revoked_mid_session(self):
        chain = ModelFallbackChain()
        keys1 = {"GEMINI_API_KEY": "valid", "GROQ_API_KEY": "valid"}
        assert chain.select_provider(keys1).name == "Gemini"

        keys2 = {"GEMINI_API_KEY": "", "GROQ_API_KEY": "valid"}
        selected = chain.select_provider(keys2)
        assert selected.name == "Groq"


class TestTimeoutStorm:
    """Simulates rapid successive timeouts from a provider."""

    def test_rapid_failures_open_circuit(self):
        monitor = AgentHealthMonitor(hung_check_interval=0.5, default_timeout=2.0)
        for i in range(10):
            monitor.start_request(f"storm-{i}", "tech_lead", "gemini")
            monitor.complete_request(f"storm-{i}", error="Timeout after 30s")

        breaker = monitor.get_breaker("gemini")
        assert breaker.failure_count >= 5
        assert not breaker.allow_request()

    def test_timeout_storm_logs_hung_events(self):
        monitor = AgentHealthMonitor(hung_check_interval=0.02, default_timeout=0.01)
        for i in range(5):
            monitor.start_request(f"hung-storm-{i}", "tech_lead", "groq", timeout=0.01)
        time.sleep(0.1)
        monitor._check_hung_requests()
        status = monitor.get_health_status()
        assert len(status["recent_hung_events"]) >= 1
