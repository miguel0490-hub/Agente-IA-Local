"""Agent Health Monitor — heartbeat, hung detection, auto-recovery, circuit breaker.

Monitors the health of AI agent interactions and provider connections.
Detects hung requests, manages circuit breaker state per provider, and
triggers auto-recovery when agents become unresponsive.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

from src.core.logger import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    CLOSED = auto()      # Normal operation
    OPEN = auto()        # Provider is failing — reject requests
    HALF_OPEN = auto()   # Testing recovery — allow one request


@dataclass
class ProviderCircuitBreaker:
    """Circuit breaker state for a single provider."""

    provider: str
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    open_since: float = 0.0

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_max_attempts: int = 2
    _half_open_attempts: int = 0

    def record_success(self) -> None:
        self.success_count += 1
        self.last_success_time = time.monotonic()
        if self.state == CircuitState.HALF_OPEN:
            self._half_open_attempts = 0
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            logger.info("Circuit CLOSED for provider=%s (recovered)", self.provider)
        elif self.state == CircuitState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.monotonic()

        if self.state == CircuitState.HALF_OPEN:
            self._half_open_attempts += 1
            if self._half_open_attempts >= self.half_open_max_attempts:
                self.state = CircuitState.OPEN
                self.open_since = time.monotonic()
                logger.warning("Circuit re-OPENED for provider=%s (half-open failed)", self.provider)
        elif self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.open_since = time.monotonic()
            logger.warning(
                "Circuit OPENED for provider=%s after %d failures",
                self.provider,
                self.failure_count,
            )

    def allow_request(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self.open_since >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self._half_open_attempts = 0
                logger.info("Circuit HALF-OPEN for provider=%s (testing recovery)", self.provider)
                return True
            return False
        return True  # HALF_OPEN allows requests

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "state": self.state.name,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_ago": round(time.monotonic() - self.last_failure_time, 1) if self.last_failure_time else None,
        }


@dataclass
class AgentHeartbeat:
    """Tracks the liveness of an active agent request."""

    request_id: str
    agent_role: str
    provider: str
    start_time: float
    last_heartbeat: float
    timeout: float = 120.0
    completed: bool = False
    error: str | None = None

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.start_time

    @property
    def since_last_beat(self) -> float:
        return time.monotonic() - self.last_heartbeat

    @property
    def is_hung(self) -> bool:
        return not self.completed and self.since_last_beat > self.timeout

    def beat(self) -> None:
        self.last_heartbeat = time.monotonic()


class AgentHealthMonitor:
    """Centralized health monitoring for agent interactions."""

    _instance: AgentHealthMonitor | None = None
    _init_lock = threading.Lock()

    def __init__(
        self,
        hung_check_interval: float = 10.0,
        default_timeout: float = 120.0,
    ):
        self._breakers: dict[str, ProviderCircuitBreaker] = {}
        self._heartbeats: dict[str, AgentHeartbeat] = {}
        self._lock = threading.Lock()
        self._hung_check_interval = hung_check_interval
        self._default_timeout = default_timeout
        self._running = False
        self._thread: threading.Thread | None = None
        self._on_hung_callbacks: list[Callable[[AgentHeartbeat], None]] = []
        self._hung_events: list[dict[str, Any]] = []

    @classmethod
    def get_instance(cls) -> AgentHealthMonitor:
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = cls()
                    cls._instance.start()
        return cls._instance

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="agent-health-monitor"
        )
        self._thread.start()
        logger.info("AgentHealthMonitor started (check_interval=%.0fs)", self._hung_check_interval)

    def stop(self) -> None:
        self._running = False

    def get_breaker(self, provider: str) -> ProviderCircuitBreaker:
        """Gets or creates a circuit breaker for a provider."""
        with self._lock:
            if provider not in self._breakers:
                self._breakers[provider] = ProviderCircuitBreaker(provider=provider)
            return self._breakers[provider]

    def is_provider_available(self, provider: str) -> bool:
        """Checks if a provider's circuit breaker allows requests."""
        return self.get_breaker(provider).allow_request()

    def record_provider_success(self, provider: str) -> None:
        self.get_breaker(provider).record_success()

    def record_provider_failure(self, provider: str) -> None:
        self.get_breaker(provider).record_failure()

    def start_request(
        self,
        request_id: str,
        agent_role: str,
        provider: str,
        timeout: float | None = None,
    ) -> AgentHeartbeat:
        """Begins monitoring a new agent request."""
        now = time.monotonic()
        hb = AgentHeartbeat(
            request_id=request_id,
            agent_role=agent_role,
            provider=provider,
            start_time=now,
            last_heartbeat=now,
            timeout=timeout or self._default_timeout,
        )
        with self._lock:
            self._heartbeats[request_id] = hb
        return hb

    def heartbeat(self, request_id: str) -> None:
        """Updates the heartbeat for an active request (call during streaming)."""
        with self._lock:
            hb = self._heartbeats.get(request_id)
        if hb:
            hb.beat()

    def complete_request(self, request_id: str, error: str | None = None) -> None:
        """Marks a request as completed."""
        with self._lock:
            hb = self._heartbeats.pop(request_id, None)
        if hb:
            hb.completed = True
            hb.error = error
            if error:
                self.record_provider_failure(hb.provider)
            else:
                self.record_provider_success(hb.provider)

    def on_hung_detected(self, callback: Callable[[AgentHeartbeat], None]) -> None:
        """Registers a callback for hung request detection."""
        self._on_hung_callbacks.append(callback)

    def _monitor_loop(self) -> None:
        while self._running:
            time.sleep(self._hung_check_interval)
            self._check_hung_requests()

    def _check_hung_requests(self) -> None:
        """Detects and handles hung agent requests."""
        hung: list[AgentHeartbeat] = []

        with self._lock:
            for rid, hb in list(self._heartbeats.items()):
                if hb.is_hung:
                    hung.append(hb)
                    self._heartbeats.pop(rid, None)

        for hb in hung:
            logger.warning(
                "HUNG request detected: id=%s role=%s provider=%s elapsed=%.1fs",
                hb.request_id,
                hb.agent_role,
                hb.provider,
                hb.elapsed,
            )
            self.record_provider_failure(hb.provider)
            self._hung_events.append({
                "request_id": hb.request_id,
                "agent_role": hb.agent_role,
                "provider": hb.provider,
                "elapsed": round(hb.elapsed, 1),
                "timestamp": time.time(),
            })
            for cb in self._on_hung_callbacks:
                try:
                    cb(hb)
                except Exception as e:
                    logger.error("Hung callback error: %s", e)

    def get_health_status(self) -> dict[str, Any]:
        """Returns a complete health status snapshot."""
        with self._lock:
            active = [
                {
                    "request_id": hb.request_id,
                    "agent_role": hb.agent_role,
                    "provider": hb.provider,
                    "elapsed": round(hb.elapsed, 1),
                    "since_last_beat": round(hb.since_last_beat, 1),
                }
                for hb in self._heartbeats.values()
            ]
            breakers = {
                name: b.to_dict()
                for name, b in self._breakers.items()
            }

        return {
            "active_requests": active,
            "circuit_breakers": breakers,
            "recent_hung_events": self._hung_events[-20:],
        }
