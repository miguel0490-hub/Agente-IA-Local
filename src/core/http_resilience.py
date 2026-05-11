"""HTTP resilience utilities: timeouts, retries with exponential backoff, and circuit breaker.

Provides a drop-in wrapper around ``requests`` for external API calls that
need consistent timeout/retry policies.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import requests

from src.core.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_CONNECT_TIMEOUT = float(os.getenv("HTTP_CONNECT_TIMEOUT", "10"))
_DEFAULT_READ_TIMEOUT = float(os.getenv("HTTP_READ_TIMEOUT", "120"))
_DEFAULT_MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES", "3"))

_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_RETRYABLE_EXCEPTIONS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


@dataclass
class CircuitBreaker:
    """Simple circuit breaker that opens after consecutive failures."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0

    _failures: int = field(default=0, init=False, repr=False)
    _last_failure: float = field(default=0.0, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    @property
    def is_open(self) -> bool:
        with self._lock:
            if self._failures < self.failure_threshold:
                return False
            if time.monotonic() - self._last_failure > self.recovery_timeout:
                self._failures = 0
                return False
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            self._last_failure = time.monotonic()


_breakers: dict[str, CircuitBreaker] = {}
_breakers_lock = threading.Lock()


def _get_breaker(key: str) -> CircuitBreaker:
    with _breakers_lock:
        if key not in _breakers:
            _breakers[key] = CircuitBreaker()
        return _breakers[key]


def resilient_request(
    method: str,
    url: str,
    *,
    connect_timeout: float | None = None,
    read_timeout: float | None = None,
    max_retries: int | None = None,
    circuit_breaker_key: str | None = None,
    **kwargs: Any,
) -> requests.Response:
    """Wrapper around requests with timeout, retry, and circuit breaker.

    Args:
        method: HTTP method (GET, POST, etc.).
        url: Target URL.
        connect_timeout: Connection timeout in seconds.
        read_timeout: Read timeout in seconds.
        max_retries: Max retry attempts for transient errors.
        circuit_breaker_key: Shared key for the circuit breaker (e.g. provider name).
        **kwargs: Forwarded to ``requests.request()``.

    Returns:
        The Response object from the first successful attempt.

    Raises:
        requests.exceptions.RequestException: After all retries exhausted.
        RuntimeError: If the circuit breaker is open.
    """
    ct = connect_timeout or _DEFAULT_CONNECT_TIMEOUT
    rt = read_timeout or _DEFAULT_READ_TIMEOUT
    retries = max_retries if max_retries is not None else _DEFAULT_MAX_RETRIES

    kwargs.setdefault("timeout", (ct, rt))

    breaker = _get_breaker(circuit_breaker_key or url) if circuit_breaker_key else _get_breaker(url)

    if breaker.is_open:
        raise RuntimeError(
            f"Circuit breaker abierto para '{circuit_breaker_key or url}'. "
            f"Reintenta en {breaker.recovery_timeout}s."
        )

    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.request(method, url, **kwargs)
            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < retries:
                wait = min(2 ** attempt, 30)
                logger.warning(
                    "HTTP %s %s returned %d, retrying in %ds (attempt %d/%d)",
                    method, url, response.status_code, wait, attempt, retries,
                )
                time.sleep(wait)
                continue
            breaker.record_success()
            return response
        except _RETRYABLE_EXCEPTIONS as exc:
            last_exc = exc
            breaker.record_failure()
            if attempt < retries:
                wait = min(2 ** attempt, 30)
                logger.warning(
                    "HTTP %s %s failed (%s), retrying in %ds (attempt %d/%d)",
                    method, url, type(exc).__name__, wait, attempt, retries,
                )
                time.sleep(wait)
            else:
                logger.error(
                    "HTTP %s %s failed after %d attempts: %s", method, url, retries, exc,
                )
        except Exception as exc:
            breaker.record_failure()
            raise

    raise last_exc or RuntimeError(f"HTTP {method} {url} failed after {retries} retries.")
