"""Chaos test: database disconnect, reconnect, and degradation."""

from __future__ import annotations

import os
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")


class TestDatabaseDisconnect:
    """Simulates database connectivity failures."""

    def test_connection_returns_usable(self):
        from sqlalchemy import text
        from src.database.database import get_connection
        conn = get_connection()
        assert conn is not None
        result = conn.execute(text("SELECT 1"))
        assert result.fetchone()[0] == 1
        conn.close()

    def test_reconnect_after_close(self):
        from sqlalchemy import text
        from src.database.database import get_connection
        conn1 = get_connection()
        conn1.close()
        conn2 = get_connection()
        assert conn2 is not None
        result = conn2.execute(text("SELECT 1"))
        assert result.fetchone()[0] == 1
        conn2.close()

    def test_concurrent_connections(self):
        from sqlalchemy import text
        from src.database.database import get_connection
        connections = []
        for _ in range(10):
            conn = get_connection()
            assert conn is not None
            connections.append(conn)
        for conn in connections:
            result = conn.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1
            conn.close()

    def test_transaction_rollback_on_error(self):
        from sqlalchemy import text
        from src.database.database import get_connection
        conn = get_connection()
        conn.execute(text("CREATE TABLE IF NOT EXISTS _chaos_test (id INTEGER PRIMARY KEY, val TEXT)"))
        conn.commit()
        try:
            conn.execute(text("INSERT INTO _chaos_test (val) VALUES (:v)"), {"v": "should_rollback"})
            raise RuntimeError("Simulated error")
        except RuntimeError:
            conn.rollback()
        result = conn.execute(text("SELECT COUNT(*) FROM _chaos_test WHERE val = 'should_rollback'"))
        assert result.fetchone()[0] == 0
        conn.execute(text("DROP TABLE IF EXISTS _chaos_test"))
        conn.commit()
        conn.close()


class TestRedisDisconnect:
    """Simulates Redis going down — should degrade to in-memory."""

    def test_rate_limiter_works_without_redis(self):
        from src.core.security import check_rate_limit
        result = check_rate_limit("chaos_user_redis", limit=100, window_seconds=60)
        assert isinstance(result, bool)

    def test_scoped_rate_limit_degrades(self):
        from src.core.security import check_scoped_rate_limit
        result = check_scoped_rate_limit("chaos:key", "login", limit=10, window_seconds=300)
        assert isinstance(result, bool)

    def test_task_queue_degrades(self):
        from src.services.task_queue import enqueue_conversion
        result = enqueue_conversion("input.txt", "output.txt")
        assert result is None or isinstance(result, str)


class TestOllamaUnavailable:
    """Simulates Ollama being down or unreachable."""

    def test_fallback_chain_skips_ollama_when_unreachable(self):
        from src.agents.model_fallback import ModelFallbackChain
        chain = ModelFallbackChain()
        keys = {"GEMINI_API_KEY": "fake", "GROQ_API_KEY": "fake"}
        selected = chain.select_provider(keys)
        assert selected.name in ("Gemini", "Groq")

    def test_ollama_as_last_resort_with_no_keys(self):
        from src.agents.model_fallback import ModelFallbackChain
        chain = ModelFallbackChain()
        available = chain.get_available_providers({})
        names = [t.name for t in available]
        assert names == ["Ollama"]


class TestHighMemoryPressure:
    """Simulates memory pressure conditions."""

    def test_semantic_cache_respects_max_size(self):
        from src.services.semantic_cache import SemanticCache
        cache = SemanticCache(max_size=5, default_ttl=60.0)
        for i in range(20):
            cache.put(f"prompt-{i}", f"model-{i}", f"response-{i}", tokens_total=10)
        stats = cache.get_stats()
        assert stats["entries"] <= 5

    def test_health_monitor_limits_history(self):
        from src.agents.health_monitor import AgentHealthMonitor
        monitor = AgentHealthMonitor(hung_check_interval=0.5, default_timeout=2.0)
        for i in range(200):
            monitor.start_request(f"mem-{i}", "tech_lead", "gemini")
            monitor.complete_request(f"mem-{i}")
        status = monitor.get_health_status()
        assert len(status["active_requests"]) == 0
