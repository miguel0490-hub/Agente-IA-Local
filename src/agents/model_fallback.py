"""Fallback Model Chain — automatic provider failover with priority ordering.

Implements a multi-tier failover chain: when the primary provider fails,
the system automatically switches to the next healthy provider in the chain.
Integrates with the AgentHealthMonitor circuit breakers for intelligent routing.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Generator

from src.core.i18n import t
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ProviderTier:
    """A provider entry in the fallback chain."""

    name: str
    motor_key: str
    priority: int
    enabled: bool = True
    requires_key: str | None = None

    def is_configured(self, api_keys: dict[str, Any]) -> bool:
        """Checks if this provider has the necessary API key configured."""
        if self.requires_key is None:
            return True
        key_val = api_keys.get(self.requires_key, "")
        return bool(key_val and str(key_val).strip())


DEFAULT_CHAIN: list[ProviderTier] = [
    ProviderTier(
        name="Gemini",
        motor_key="⚡ Gemini 2.5 Pro (Cerebro)",
        priority=1,
        requires_key="GEMINI_API_KEY",
    ),
    ProviderTier(
        name="Groq",
        motor_key="🚀 Groq LLaMA (Velocidad)",
        priority=2,
        requires_key="GROQ_API_KEY",
    ),
    ProviderTier(
        name="OpenRouter",
        motor_key="🌐 OpenRouter (Multi-Modelo)",
        priority=3,
        requires_key="OPENROUTER_API_KEY",
    ),
    ProviderTier(
        name="Ollama",
        motor_key="🦙 Ollama (Local)",
        priority=4,
        requires_key=None,
    ),
]


class ModelFallbackChain:
    """Manages automatic failover between LLM providers."""

    def __init__(self, chain: list[ProviderTier] | None = None):
        self._chain = sorted(
            chain or list(DEFAULT_CHAIN),
            key=lambda t: t.priority,
        )
        self._last_used: str | None = None
        self._failover_log: list[dict[str, Any]] = []

    def get_available_providers(self, api_keys: dict[str, Any]) -> list[ProviderTier]:
        """Returns providers that are enabled, configured, and circuit-healthy."""
        available = []
        for tier in self._chain:
            if not tier.enabled:
                continue
            if not tier.is_configured(api_keys):
                continue
            if not self._is_circuit_healthy(tier.name):
                continue
            available.append(tier)
        return available

    def select_provider(
        self,
        api_keys: dict[str, Any],
        preferred: str | None = None,
        exclude: set[str] | None = None,
    ) -> ProviderTier | None:
        """Selects the best available provider with optional preference."""
        available = self.get_available_providers(api_keys)
        if exclude:
            available = [t for t in available if t.name not in exclude]

        if not available:
            logger.error("No providers available in fallback chain")
            return None

        if preferred:
            for tier in available:
                if tier.name.lower() == preferred.lower():
                    return tier

        return available[0]

    def get_fallback(
        self,
        failed_provider: str,
        api_keys: dict[str, Any],
        already_tried: set[str] | None = None,
    ) -> ProviderTier | None:
        """Gets the next fallback provider after a failure."""
        tried = (already_tried or set()) | {failed_provider}
        fallback = self.select_provider(api_keys, exclude=tried)

        if fallback:
            self._failover_log.append({
                "from": failed_provider,
                "to": fallback.name,
                "timestamp": time.time(),
                "tried": list(tried),
            })
            logger.info(
                "Fallback: %s -> %s (tried: %s)",
                failed_provider,
                fallback.name,
                tried,
            )
        return fallback

    def stream_with_fallback(
        self,
        api_keys: dict[str, Any],
        motor_name: str,
        mensaje: str,
        historial: list,
        system_instruction: str | None = None,
    ) -> Generator[str, None, None]:
        """Streams a chat response with automatic failover on provider failure.

        Yields chunks from the primary provider; on failure, transparently
        switches to the next available provider in the chain.
        """
        from src.services.llm_provider import LLMFactory

        tried: set[str] = set()
        current_motor = motor_name
        max_attempts = len(self._chain)

        for attempt in range(max_attempts):
            provider_name = self._extract_provider_name(current_motor)
            tried.add(provider_name)

            try:
                provider = LLMFactory.get_provider(
                    motor_name=current_motor, api_keys=api_keys
                )
                for chunk in provider.stream_chat(
                    mensaje, historial, system_instruction=system_instruction
                ):
                    if chunk:
                        yield chunk
                self._report_success(provider_name)
                return

            except Exception as e:
                logger.warning(
                    "Provider %s failed (attempt %d/%d): %s",
                    provider_name,
                    attempt + 1,
                    max_attempts,
                    str(e)[:200],
                )
                self._report_failure(provider_name)

                fallback = self.get_fallback(provider_name, api_keys, tried)
                if not fallback:
                    yield t("mf_all_failed", error=e)
                    return

                yield t("mf_switching", provider=provider_name, fallback=fallback.name)
                current_motor = fallback.motor_key

        yield t("mf_exhausted")

    def _extract_provider_name(self, motor_name: str) -> str:
        """Extracts the provider name from a motor display name."""
        for tier in self._chain:
            if tier.name.lower() in motor_name.lower():
                return tier.name
        return motor_name.split()[0] if motor_name else "Unknown"

    def _is_circuit_healthy(self, provider_name: str) -> bool:
        """Checks provider health via the AgentHealthMonitor circuit breaker."""
        try:
            from src.agents.health_monitor import AgentHealthMonitor
            monitor = AgentHealthMonitor.get_instance()
            return monitor.is_provider_available(provider_name.lower())
        except Exception:
            return True

    def _report_success(self, provider_name: str) -> None:
        try:
            from src.agents.health_monitor import AgentHealthMonitor
            monitor = AgentHealthMonitor.get_instance()
            monitor.record_provider_success(provider_name.lower())
        except Exception:
            pass

    def _report_failure(self, provider_name: str) -> None:
        try:
            from src.agents.health_monitor import AgentHealthMonitor
            monitor = AgentHealthMonitor.get_instance()
            monitor.record_provider_failure(provider_name.lower())
        except Exception:
            pass

    def get_failover_log(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._failover_log[-limit:]

    def get_chain_status(self, api_keys: dict[str, Any]) -> list[dict[str, Any]]:
        """Returns the status of all providers in the chain."""
        status = []
        for tier in self._chain:
            is_configured = tier.is_configured(api_keys)
            is_healthy = self._is_circuit_healthy(tier.name)
            status.append({
                "name": tier.name,
                "priority": tier.priority,
                "enabled": tier.enabled,
                "configured": is_configured,
                "circuit_healthy": is_healthy,
                "available": tier.enabled and is_configured and is_healthy,
            })
        return status


_chain_instance: ModelFallbackChain | None = None


def get_fallback_chain() -> ModelFallbackChain:
    """Returns the global ModelFallbackChain singleton."""
    global _chain_instance
    if _chain_instance is None:
        _chain_instance = ModelFallbackChain()
    return _chain_instance
