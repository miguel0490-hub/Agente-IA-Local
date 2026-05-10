"""Operational endpoints for health and metrics."""

from __future__ import annotations

import time

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from src.core.observability import init_observability

init_observability()

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
