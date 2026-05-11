"""Operational endpoints for health, metrics, and AI observability."""

from __future__ import annotations

import time

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from src.core.observability import init_observability
from src.observability.tracing import init_tracing

init_observability()
init_tracing()

import src.observability.ai_metrics  # noqa: E402, F401 — register AI metrics with collector

REQUEST_COUNT = Counter("superagente_requests_total", "Total monitoring endpoint requests", ["endpoint"])
REQUEST_LATENCY = Histogram("superagente_request_latency_seconds", "Latency by endpoint", ["endpoint"])

app = FastAPI(title="SuperAgente Monitoring API", version="1.0.0")


@app.get("/health")
def health() -> dict:
    start = time.perf_counter()
    REQUEST_COUNT.labels(endpoint="/health").inc()
    payload = {"status": "ok"}
    REQUEST_LATENCY.labels(endpoint="/health").observe(time.perf_counter() - start)
    return payload


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    start = time.perf_counter()
    REQUEST_COUNT.labels(endpoint="/metrics").inc()
    data = generate_latest()
    REQUEST_LATENCY.labels(endpoint="/metrics").observe(time.perf_counter() - start)
    return PlainTextResponse(data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


@app.get("/ai/metrics")
def ai_metrics_summary() -> dict:
    """Returns a JSON snapshot of current AI metric counters for dashboards."""
    from src.observability import ai_metrics as m

    return {
        "llm_requests": _counter_value(m.LLM_REQUESTS),
        "llm_errors": _counter_value(m.LLM_ERRORS),
        "security_events": _counter_value(m.SECURITY_EVENTS),
        "tool_executions": _counter_value(m.TOOL_EXECUTIONS),
        "active_users": m.ACTIVE_USERS._value.get(),
        "active_chats": m.ACTIVE_CHATS._value.get(),
    }


def _counter_value(counter: Counter) -> float:
    """Sums all label combinations of a prometheus Counter."""
    total = 0.0
    for metric in counter.collect():
        for sample in metric.samples:
            if sample.name.endswith("_total"):
                total += sample.value
    return total
