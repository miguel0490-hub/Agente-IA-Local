"""AI platform metrics for Prometheus/Grafana.

Tracks LLM performance, costs, security events, and tool execution.
"""

from __future__ import annotations

from typing import Any

from prometheus_client import Counter, Gauge, Histogram

from src.core.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# LLM Metrics
# ---------------------------------------------------------------------------
LLM_REQUESTS = Counter(
    "superagente_llm_requests_total",
    "Total LLM requests",
    ["provider", "model", "status"],
)
LLM_TOKENS_IN = Counter(
    "superagente_llm_tokens_input_total",
    "Total input tokens consumed",
    ["provider", "model"],
)
LLM_TOKENS_OUT = Counter(
    "superagente_llm_tokens_output_total",
    "Total output tokens generated",
    ["provider", "model"],
)
LLM_LATENCY = Histogram(
    "superagente_llm_latency_seconds",
    "LLM response latency",
    ["provider", "model"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120],
)
LLM_COST = Counter(
    "superagente_llm_cost_usd_total",
    "Estimated LLM cost in USD",
    ["provider", "model"],
)
LLM_ERRORS = Counter(
    "superagente_llm_errors_total",
    "LLM errors by type",
    ["provider", "model", "error_type"],
)

# ---------------------------------------------------------------------------
# Security Metrics
# ---------------------------------------------------------------------------
SECURITY_EVENTS = Counter(
    "superagente_security_events_total",
    "Security events",
    ["event_type"],
)
PROMPT_INJECTION_DETECTED = Counter(
    "superagente_prompt_injection_total",
    "Prompt injection attempts detected",
    ["risk_level"],
)
SSRF_BLOCKED = Counter(
    "superagente_ssrf_blocked_total",
    "SSRF attempts blocked",
)
TOOL_BLOCKED = Counter(
    "superagente_tool_blocked_total",
    "Tool executions blocked by guard",
    ["tool", "reason"],
)

# ---------------------------------------------------------------------------
# Tool Metrics
# ---------------------------------------------------------------------------
TOOL_EXECUTIONS = Counter(
    "superagente_tool_executions_total",
    "Tool executions",
    ["tool", "status"],
)
TOOL_LATENCY = Histogram(
    "superagente_tool_latency_seconds",
    "Tool execution latency",
    ["tool"],
)

# ---------------------------------------------------------------------------
# User / Session Metrics
# ---------------------------------------------------------------------------
ACTIVE_USERS = Gauge(
    "superagente_active_users",
    "Currently active users",
)
ACTIVE_CHATS = Gauge(
    "superagente_active_chats",
    "Active chat sessions",
)

# ---------------------------------------------------------------------------
# System Metrics
# ---------------------------------------------------------------------------
CIRCUIT_BREAKER_STATE = Gauge(
    "superagente_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open)",
    ["service"],
)


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------
def record_llm_request(
    provider: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    latency_s: float,
    cost: float,
    *,
    error: str = "",
) -> None:
    """Records a complete LLM request with all associated metrics."""
    status = "error" if error else "ok"
    LLM_REQUESTS.labels(provider=provider, model=model, status=status).inc()
    LLM_TOKENS_IN.labels(provider=provider, model=model).inc(tokens_in)
    LLM_TOKENS_OUT.labels(provider=provider, model=model).inc(tokens_out)
    LLM_LATENCY.labels(provider=provider, model=model).observe(latency_s)
    LLM_COST.labels(provider=provider, model=model).inc(cost)
    if error:
        LLM_ERRORS.labels(provider=provider, model=model, error_type=error).inc()


def record_security_event(
    event_type: str,
    *,
    details: dict[str, Any] | None = None,
) -> None:
    """Records a security event and bumps specialised counters."""
    SECURITY_EVENTS.labels(event_type=event_type).inc()

    if event_type == "prompt_injection":
        risk = (details or {}).get("risk_level", "unknown")
        PROMPT_INJECTION_DETECTED.labels(risk_level=risk).inc()
    elif event_type == "ssrf_blocked":
        SSRF_BLOCKED.inc()
    elif event_type == "tool_blocked":
        tool = (details or {}).get("tool", "unknown")
        reason = (details or {}).get("reason", "policy")
        TOOL_BLOCKED.labels(tool=tool, reason=reason).inc()

    logger.info("Security event recorded: %s %s", event_type, details or "")


def record_tool_execution(
    tool: str,
    latency_s: float,
    *,
    success: bool = True,
    blocked_reason: str = "",
) -> None:
    """Records a tool execution with latency and status."""
    if blocked_reason:
        TOOL_BLOCKED.labels(tool=tool, reason=blocked_reason).inc()
        TOOL_EXECUTIONS.labels(tool=tool, status="blocked").inc()
    else:
        status = "ok" if success else "error"
        TOOL_EXECUTIONS.labels(tool=tool, status=status).inc()
        TOOL_LATENCY.labels(tool=tool).observe(latency_s)
