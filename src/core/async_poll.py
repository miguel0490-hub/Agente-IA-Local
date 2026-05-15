"""Limita polling de colas async (Redis/RQ) en cada rerun de Streamlit."""

from __future__ import annotations

import time

import streamlit as st

_DEFAULT_INTERVAL_SEC = 2.5


def should_poll_async_jobs(interval_sec: float | None = None) -> bool:
    """True si ha pasado el intervalo desde el último poll (evita Redis en cada rerun)."""
    interval = interval_sec if interval_sec is not None else _DEFAULT_INTERVAL_SEC
    now = time.time()
    last = float(st.session_state.get("_async_jobs_poll_ts") or 0.0)
    if now - last < interval:
        return False
    st.session_state["_async_jobs_poll_ts"] = now
    return True
