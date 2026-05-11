"""Tests for HTTP resilience (circuit breaker, retries, timeouts)."""
from __future__ import annotations
import os, pytest
os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")

from src.core.http_resilience import CircuitBreaker, resilient_request


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker(failure_threshold=3)
        assert not cb.is_open

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        for _ in range(3):
            cb.record_failure()
        assert cb.is_open

    def test_resets_on_success(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert not cb.is_open

    def test_recovers_after_timeout(self):
        import time
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        assert cb.is_open
        time.sleep(0.15)
        assert not cb.is_open


class TestResilientRequest:
    def test_successful_request(self):
        import requests as _req
        try:
            response = resilient_request("GET", "https://httpbin.org/get", max_retries=1, read_timeout=10)
            assert response.status_code == 200
        except _req.exceptions.SSLError:
            pytest.skip("SSL certificate verification failed on this machine")

    def test_timeout_handling(self):
        import requests as _req
        try:
            with pytest.raises(Exception):
                resilient_request(
                    "GET", "https://httpbin.org/delay/10",
                    connect_timeout=1, read_timeout=1, max_retries=1,
                )
        except _req.exceptions.SSLError:
            pytest.skip("SSL certificate verification failed on this machine")

    def test_circuit_breaker_blocks(self):
        cb_key = "test_block_key"
        from src.core.http_resilience import _get_breaker
        breaker = _get_breaker(cb_key)
        for _ in range(5):
            breaker.record_failure()
        with pytest.raises(RuntimeError, match="Circuit breaker"):
            resilient_request("GET", "https://httpbin.org/get", circuit_breaker_key=cb_key)
        breaker.record_success()
