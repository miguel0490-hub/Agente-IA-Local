"""Integration tests for the Model Fallback Chain."""

from __future__ import annotations

import os
import pytest

os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")

from src.agents.model_fallback import (
    DEFAULT_CHAIN,
    ModelFallbackChain,
    ProviderTier,
    get_fallback_chain,
)


class TestProviderTier:

    def test_configured_with_key(self):
        tier = ProviderTier(name="Test", motor_key="test", priority=1, requires_key="MY_KEY")
        assert not tier.is_configured({})
        assert not tier.is_configured({"MY_KEY": ""})
        assert tier.is_configured({"MY_KEY": "actual-value"})

    def test_configured_without_key_requirement(self):
        tier = ProviderTier(name="Ollama", motor_key="ollama", priority=4, requires_key=None)
        assert tier.is_configured({})


class TestFallbackChain:

    def setup_method(self):
        from src.agents.health_monitor import AgentHealthMonitor
        AgentHealthMonitor._instance = None
        self.chain = ModelFallbackChain()

    def test_default_chain_order(self):
        assert DEFAULT_CHAIN[0].name == "Gemini"
        assert DEFAULT_CHAIN[1].name == "Groq"
        assert DEFAULT_CHAIN[2].name == "OpenRouter"
        assert DEFAULT_CHAIN[3].name == "Ollama"

    def test_get_available_providers_with_keys(self, sample_api_keys):
        available = self.chain.get_available_providers(sample_api_keys)
        names = [t.name for t in available]
        assert "Gemini" in names
        assert "Groq" in names
        assert "Ollama" in names

    def test_get_available_providers_empty_keys(self):
        available = self.chain.get_available_providers({})
        names = [t.name for t in available]
        assert "Ollama" in names
        assert "Gemini" not in names

    def test_select_provider_respects_priority(self, sample_api_keys):
        selected = self.chain.select_provider(sample_api_keys)
        assert selected is not None
        assert selected.name == "Gemini"

    def test_select_provider_with_preference(self, sample_api_keys):
        selected = self.chain.select_provider(sample_api_keys, preferred="Groq")
        assert selected is not None
        assert selected.name == "Groq"

    def test_select_provider_with_exclusion(self, sample_api_keys):
        selected = self.chain.select_provider(sample_api_keys, exclude={"Gemini"})
        assert selected is not None
        assert selected.name != "Gemini"

    def test_get_fallback_after_failure(self, sample_api_keys):
        fallback = self.chain.get_fallback("Gemini", sample_api_keys)
        assert fallback is not None
        assert fallback.name != "Gemini"

    def test_get_fallback_logs_event(self, sample_api_keys):
        self.chain.get_fallback("Gemini", sample_api_keys)
        log = self.chain.get_failover_log()
        assert len(log) >= 1
        assert log[-1]["from"] == "Gemini"

    def test_chain_status_structure(self, sample_api_keys):
        status = self.chain.get_chain_status(sample_api_keys)
        assert len(status) == 4
        for entry in status:
            assert "name" in entry
            assert "priority" in entry
            assert "available" in entry
            assert "configured" in entry
            assert "circuit_healthy" in entry

    def test_no_fallback_when_all_tried(self):
        all_names = {t.name for t in DEFAULT_CHAIN}
        fallback = self.chain.get_fallback("Gemini", {}, already_tried=all_names)
        assert fallback is None

    def test_extract_provider_name(self):
        assert self.chain._extract_provider_name("⚡ Gemini 2.5 Pro (Cerebro)") == "Gemini"
        assert self.chain._extract_provider_name("🚀 Groq LLaMA (Velocidad)") == "Groq"


class TestFallbackChainSingleton:
    def test_singleton(self):
        c1 = get_fallback_chain()
        c2 = get_fallback_chain()
        assert c1 is c2
