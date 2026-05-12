"""Integration tests for the Agent Health Monitor."""

from __future__ import annotations

import os
import time
import pytest

os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")

from src.agents.health_monitor import (
    AgentHealthMonitor,
    CircuitState,
    ProviderCircuitBreaker,
)


class TestCircuitBreaker:

    def test_starts_closed(self):
        cb = ProviderCircuitBreaker(provider="test")
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request()

    def test_opens_after_threshold_failures(self):
        cb = ProviderCircuitBreaker(provider="test", failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.failure_count == 3
        assert not cb.allow_request()

    def test_does_not_open_below_threshold(self):
        cb = ProviderCircuitBreaker(provider="test", failure_threshold=5)
        for _ in range(4):
            cb.record_failure()
        assert cb.allow_request()

    def test_success_resets_in_half_open(self):
        cb = ProviderCircuitBreaker(provider="test", failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.allow_request()
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_success_decrements_failure_count(self):
        cb = ProviderCircuitBreaker(provider="test", failure_threshold=5)
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2
        cb.record_success()
        assert cb.failure_count == 1

    def test_to_dict_serialization(self):
        cb = ProviderCircuitBreaker(provider="gemini")
        cb.record_success()
        d = cb.to_dict()
        assert d["provider"] == "gemini"
        assert d["state"] == "CLOSED"
        assert d["success_count"] == 1


class TestAgentHealthMonitor:

    def setup_method(self):
        self.monitor = AgentHealthMonitor(hung_check_interval=0.5, default_timeout=2.0)

    def test_provider_availability_default(self):
        assert self.monitor.is_provider_available("gemini")
        assert self.monitor.is_provider_available("groq")

    def test_record_success_and_failure(self):
        self.monitor.record_provider_success("gemini")
        breaker = self.monitor.get_breaker("gemini")
        assert breaker.success_count == 1

        self.monitor.record_provider_failure("gemini")
        assert breaker.failure_count == 1

    def test_start_and_complete_request(self):
        hb = self.monitor.start_request("req-1", "tech_lead", "gemini")
        assert hb.request_id == "req-1"
        assert not hb.completed

        self.monitor.heartbeat("req-1")
        self.monitor.complete_request("req-1")

        status = self.monitor.get_health_status()
        assert len(status["active_requests"]) == 0

    def test_complete_with_error_records_failure(self):
        self.monitor.start_request("req-2", "tech_lead", "groq")
        self.monitor.complete_request("req-2", error="Connection timeout")
        breaker = self.monitor.get_breaker("groq")
        assert breaker.failure_count >= 1

    def test_health_status_structure(self):
        self.monitor.start_request("req-3", "tech_lead", "gemini")
        status = self.monitor.get_health_status()
        assert "active_requests" in status
        assert "circuit_breakers" in status
        assert "recent_hung_events" in status
        self.monitor.complete_request("req-3")

    def test_hung_detection(self):
        self.monitor._default_timeout = 0.05
        self.monitor._hung_check_interval = 0.02
        self.monitor.start_request("req-hung", "tech_lead", "gemini", timeout=0.05)
        time.sleep(0.15)
        self.monitor._check_hung_requests()
        status = self.monitor.get_health_status()
        assert len(status["recent_hung_events"]) >= 1
