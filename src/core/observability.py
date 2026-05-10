"""Runtime observability bootstrap (Sentry + shared telemetry hooks)."""

from __future__ import annotations

import os
import re

try:
    import sentry_sdk
except Exception:  # pragma: no cover
    sentry_sdk = None


_SECRET_PATTERNS = [
    re.compile(r"(api[_-]?key\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE),
    re.compile(r"(token\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE),
    re.compile(r"(password\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE),
]


def _redact_text(value: str) -> str:
    text = str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(r"\1[REDACTED]", text)
    return text


def _before_send(event, _hint):  # pragma: no cover
    """Redacts common secrets before sending events to Sentry (firma exigida por Sentry SDK)."""
    if "message" in event and event["message"]:
        event["message"] = _redact_text(event["message"])
    if "exception" in event and event["exception"]:
        for exc in event["exception"].get("values", []):
            if "value" in exc and exc["value"]:
                exc["value"] = _redact_text(exc["value"])
    return event


def init_observability() -> bool:
    """Initializes Sentry when DSN is configured. Returns True if enabled."""
    if not sentry_sdk:
        return False
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    traces_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.15"))
    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("ENVIRONMENT", "dev"),
        traces_sample_rate=traces_rate,
        send_default_pii=False,
        before_send=_before_send,
    )
    return True
