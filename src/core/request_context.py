"""Best-effort HTTP context helpers for Streamlit (proxy-aware client IP)."""

from __future__ import annotations

from typing import Any, Mapping


def _get_header_ci(headers: Any, *names: str) -> str | None:
    if headers is None:
        return None
    if isinstance(headers, Mapping):
        lower = {str(k).lower(): str(v) for k, v in headers.items()}
        for n in names:
            v = lower.get(n.lower())
            if v:
                return v.strip()
        return None
    get = getattr(headers, "get", None)
    if callable(get):
        for n in names:
            raw = get(n) or get(n.lower())
            if raw:
                return str(raw).strip()
    return None


def get_remote_address() -> str:
    """
    Returns client IP when Streamlit exposes request headers (typical behind Nginx).

    En ejecución local sin proxy, Streamlit a menudo no expone la IP; en ese caso se
    devuelve el literal 'unknown'. El login no debe usar ese valor como cubo único de
    rate limit por IP (ver auth_gate).
    """
    try:
        import streamlit as st

        ctx = getattr(st, "context", None)
        hdrs = getattr(ctx, "headers", None)
        xff = _get_header_ci(hdrs, "X-Forwarded-For", "X-FORWARDED-FOR")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first
        xri = _get_header_ci(hdrs, "X-Real-IP", "X-REAL-IP")
        if xri:
            return xri
    except Exception:
        pass

    return "unknown"
