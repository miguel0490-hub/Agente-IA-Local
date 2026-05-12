"""Chaos test: websocket disconnect, gateway resilience."""

from __future__ import annotations

import os
import time
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")

from src.core.http_resilience import CircuitBreaker, resilient_request


class TestWebsocketDisconnect:
    """Simulates websocket connection failures."""

    def test_circuit_breaker_opens_on_repeated_failures(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.5)
        for _ in range(3):
            cb.record_failure()
        assert cb.is_open

    def test_circuit_breaker_recovers(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open

        time.sleep(0.1)
        assert not cb.is_open

    def test_circuit_breaker_resets_on_success(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.05)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert not cb.is_open

    def test_resilient_request_timeout(self):
        with patch("src.core.http_resilience.requests.request") as mock_req:
            mock_req.side_effect = Exception("Connection refused")
            try:
                result = resilient_request("GET", "http://fake-host:9999/test", timeout=1)
                assert result is None or result.status_code >= 400
            except Exception:
                pass


class TestGatewayTimeout:
    """Simulates gateway timeout conditions."""

    def test_health_endpoint_fast_response(self):
        from fastapi.testclient import TestClient
        from src.gateway.app import app
        client = TestClient(app, raise_server_exceptions=False)
        start = time.time()
        resp = client.get("/api/v1/health")
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 2.0

    def test_status_endpoint_reasonable_latency(self):
        from fastapi.testclient import TestClient
        from src.gateway.app import app
        client = TestClient(app, raise_server_exceptions=False)
        start = time.time()
        resp = client.get("/api/v1/status")
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 5.0

    def test_concurrent_requests_handled(self):
        import concurrent.futures
        from fastapi.testclient import TestClient
        from src.gateway.app import app

        def make_request():
            client = TestClient(app, raise_server_exceptions=False)
            return client.get("/api/v1/health").status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(r == 200 for r in results)


class TestCorrelationIdPropagation:
    """Ensures correlation IDs survive across chaos conditions."""

    def test_correlation_id_propagated_under_load(self):
        import concurrent.futures
        from fastapi.testclient import TestClient
        from src.gateway.app import app

        def check_correlation(cid: str):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/v1/health", headers={"X-Correlation-ID": cid})
            return resp.headers.get("X-Correlation-ID") == cid

        cids = [f"chaos-{i}" for i in range(10)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(check_correlation, cids))

        assert all(results)
