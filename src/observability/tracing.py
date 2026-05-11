"""OpenTelemetry distributed tracing configuration.

Initializes OTLP exporter, tracer provider, and provides decorators/context managers
for instrumenting code paths.
"""

from __future__ import annotations

import functools
import os
from contextlib import contextmanager
from typing import Any, Callable, Optional

from src.core.logger import get_logger

logger = get_logger(__name__)

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace import StatusCode

    _HAS_OTEL = True
except ImportError:
    _HAS_OTEL = False

_initialized = False


def init_tracing(service_name: str = "superagente-ia") -> None:
    """Initializes OpenTelemetry tracing with OTLP exporter."""
    global _initialized
    if _initialized or not _HAS_OTEL:
        return

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        logger.info("OTEL_EXPORTER_OTLP_ENDPOINT not set, tracing disabled")
        return

    resource = Resource.create({
        "service.name": service_name,
        "service.version": os.getenv("APP_VERSION", "0.0.0"),
        "deployment.environment": os.getenv("ENVIRONMENT", "dev"),
    })

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _initialized = True
    logger.info("OpenTelemetry tracing initialized → %s", endpoint)


def get_tracer(name: str) -> Any:
    """Returns an OTel tracer or a no-op object with compatible interface."""
    if _HAS_OTEL:
        return trace.get_tracer(name)
    return _NoOpTracer()


def traced(
    name: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Callable:
    """Decorator that wraps a function in an OTel span."""

    def decorator(fn: Callable) -> Callable:
        span_name = name or f"{fn.__module__}.{fn.__qualname__}"

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer(fn.__module__)
            with tracer.start_as_current_span(span_name, attributes=attributes or {}):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    if _HAS_OTEL:
                        current = trace.get_current_span()
                        current.set_status(StatusCode.ERROR, str(exc))
                        current.record_exception(exc)
                    raise

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer(fn.__module__)
            with tracer.start_as_current_span(span_name, attributes=attributes or {}):
                try:
                    return await fn(*args, **kwargs)
                except Exception as exc:
                    if _HAS_OTEL:
                        current = trace.get_current_span()
                        current.set_status(StatusCode.ERROR, str(exc))
                        current.record_exception(exc)
                    raise

        import inspect

        return async_wrapper if inspect.iscoroutinefunction(fn) else wrapper

    return decorator


@contextmanager
def span(name: str, attributes: dict[str, Any] | None = None):
    """Context manager for creating a span."""
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span(name, attributes=attributes or {}) as s:
        try:
            yield s
        except Exception as exc:
            if _HAS_OTEL:
                s.set_status(StatusCode.ERROR, str(exc))
                s.record_exception(exc)
            raise


class _NoOpSpan:
    """Minimal no-op span for when OTel is not installed."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, status: Any, description: str = "") -> None:
        pass

    def record_exception(self, exc: BaseException) -> None:
        pass

    def add_event(self, name: str, attributes: dict | None = None) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _NoOpTracer:
    """Minimal no-op tracer for when OTel is not installed."""

    def start_as_current_span(self, name: str, **kwargs):
        return _NoOpSpan()

    def start_span(self, name: str, **kwargs):
        return _NoOpSpan()
