"""Cross-component integration: Health Monitor <-> Fallback Chain <-> Circuit Breaker."""

from __future__ import annotations

import os
import time
import pytest

os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")

from src.agents.health_monitor import AgentHealthMonitor, CircuitState
from src.agents.model_fallback import ModelFallbackChain


class TestFallbackHealthIntegration:
    """Validates that the fallback chain correctly reacts to circuit breaker state."""

    def setup_method(self):
        AgentHealthMonitor._instance = None
        self.monitor = AgentHealthMonitor.get_instance()
        self.chain = ModelFallbackChain()
        self.keys = {
            "GEMINI_API_KEY": "fake-gemini",
            "GROQ_API_KEY": "fake-groq",
            "OPENROUTER_API_KEY": "fake-openrouter",
        }

    def test_healthy_chain_selects_primary(self):
        selected = self.chain.select_provider(self.keys)
        assert selected is not None
        assert selected.name == "Gemini"

    def test_failed_provider_triggers_fallback(self):
        for _ in range(5):
            self.monitor.record_provider_failure("gemini")
        breaker = self.monitor.get_breaker("gemini")
        assert not breaker.allow_request()

        fallback = self.chain.get_fallback("Gemini", self.keys)
        assert fallback is not None
        assert fallback.name != "Gemini"

    def test_recovery_after_timeout(self):
        breaker = self.monitor.get_breaker("gemini")
        breaker.recovery_timeout = 0.05
        for _ in range(5):
            self.monitor.record_provider_failure("gemini")
        assert not self.monitor.is_provider_available("gemini")

        time.sleep(0.1)
        assert self.monitor.is_provider_available("gemini")

    def test_full_lifecycle_request_tracking(self):
        hb = self.monitor.start_request("req-lc", "tech_lead", "gemini")
        self.monitor.heartbeat("req-lc")
        self.monitor.complete_request("req-lc")
        breaker = self.monitor.get_breaker("gemini")
        assert breaker.success_count >= 1

    def test_full_lifecycle_with_error(self):
        self.monitor.start_request("req-err", "tech_lead", "groq")
        self.monitor.complete_request("req-err", error="API rate limited")
        breaker = self.monitor.get_breaker("groq")
        assert breaker.failure_count >= 1

    def test_chain_status_reflects_breaker_state(self):
        for _ in range(5):
            self.monitor.record_provider_failure("gemini")
        status = self.chain.get_chain_status(self.keys)
        gemini_status = next(s for s in status if s["name"] == "Gemini")
        assert not gemini_status["circuit_healthy"]

    def test_cascade_fallback_sequence(self):
        for _ in range(5):
            self.monitor.record_provider_failure("gemini")
        for _ in range(5):
            self.monitor.record_provider_failure("groq")

        fallback = self.chain.get_fallback("Gemini", self.keys)
        assert fallback is not None
        assert fallback.name not in ("Gemini", "Groq")


class TestSessionPersistence:
    """Validates database session persistence."""

    def test_connection_and_query(self):
        from sqlalchemy import text
        from src.database.database import get_connection
        conn = get_connection()
        assert conn is not None
        result = conn.execute(text("SELECT 1"))
        row = result.fetchone()
        assert row[0] == 1
        conn.close()

    def test_user_creation_and_retrieval(self):
        from sqlalchemy import text
        from src.database.database import get_connection
        conn = get_connection()
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS _test_users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        ))
        conn.execute(text("INSERT INTO _test_users (name) VALUES (:n)"), {"n": "test-user-integration"})
        conn.commit()
        result = conn.execute(text("SELECT name FROM _test_users WHERE name = :n"), {"n": "test-user-integration"})
        row = result.fetchone()
        assert row[0] == "test-user-integration"
        conn.execute(text("DROP TABLE IF EXISTS _test_users"))
        conn.commit()
        conn.close()


class TestAuditLogging:
    """Validates audit log infrastructure."""

    def test_logger_outputs(self):
        from src.core.logger import get_logger
        logger = get_logger("test.audit")
        logger.info("Integration test audit entry")

    def test_request_context_remote_address(self):
        from src.core.request_context import get_remote_address
        addr = get_remote_address()
        assert isinstance(addr, str)
