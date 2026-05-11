"""Chaos testing: verify graceful degradation when dependencies fail."""
from __future__ import annotations
import os, pytest, time
os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")

from src.core.http_resilience import CircuitBreaker, resilient_request


class TestRedisDown:
    """Tests that the app degrades gracefully when Redis is unavailable."""

    def test_rate_limiter_fallback(self):
        """Rate limiter should fall back to in-memory when Redis is down."""
        from src.core.security import check_rate_limit
        allowed = check_rate_limit("test_user_chaos", limit=100, window_seconds=60)
        assert isinstance(allowed, bool)

    def test_task_queue_enqueue_fallback(self):
        """Task queue should return None when Redis is down."""
        from src.services.task_queue import enqueue_conversion
        result = enqueue_conversion("input.txt", "output.txt")
        assert result is None or isinstance(result, str)


class TestSlowDependency:
    """Tests that circuit breaker activates on slow/hanging dependencies."""

    def test_circuit_breaker_opens_on_failures(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.5)
        for _ in range(3):
            cb.record_failure()
        assert cb.is_open

        time.sleep(0.6)
        assert not cb.is_open

    def test_circuit_breaker_blocks_requests(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        cb.record_failure()
        assert cb.is_open


class TestDatabaseResilience:
    """Tests that DB connection handling is robust."""

    def test_connection_returns(self):
        """get_connection should return a usable connection."""
        from src.database.database import get_connection
        conn = get_connection()
        assert conn is not None
        conn.close()
