"""Subida y polling de vídeos Gemini entre reruns (evita bloquear el hilo de Streamlit)."""

from __future__ import annotations

import hashlib
import os
import time
from typing import Any

import streamlit as st

from src.core.async_poll import should_poll_async_jobs
from src.core.i18n import t
from src.services.google_genai import get_genai_client


def _job_key(video_paths: list[str]) -> str:
    normalized = "|".join(sorted(os.path.normpath(p) for p in video_paths))
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _file_state_name(video_file: Any) -> str:
    state = getattr(video_file, "state", None)
    return getattr(state, "name", str(state or ""))


def _cleanup_local_paths(paths: list[str]) -> None:
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


def resolve_gemini_video_files(video_paths: list[str], api_key: str) -> list[Any]:
    """
    Devuelve objetos File de Gemini listos para el chat.

    Si el procesamiento sigue en curso, hace ``st.rerun()`` o ``st.stop()`` hasta completar.
    """
    if not video_paths:
        return []

    client = get_genai_client(api_key)
    key = _job_key(video_paths)
    store: dict[str, list[dict]] = st.session_state.setdefault("_gemini_video_jobs", {})
    jobs = store.get(key)
    elapsed_key = f"_gemini_video_elapsed_{key}"
    poll_interval = float(os.getenv("GEMINI_VIDEO_POLL_INTERVAL_SEC", "2.0"))

    if jobs is None:
        jobs = []
        n_vid = len(video_paths)
        for vi, video_path in enumerate(video_paths):
            if not os.path.exists(video_path):
                continue
            label = t("video_status_init")
            if n_vid > 1:
                label = f"{label} ({vi + 1}/{n_vid})"
            with st.status(label, expanded=True) as status:
                st.write(t("video_uploading"))
                video_file = client.files.upload(file=video_path)
                status.update(label=t("video_uploading"), state="running")
            jobs.append({"path": video_path, "name": video_file.name, "file": video_file})
        store[key] = jobs
        st.session_state[elapsed_key] = 0.0
        st.rerun()

    start_ts = float(st.session_state.get(f"_gemini_video_start_{key}") or time.time())
    st.session_state[f"_gemini_video_start_{key}"] = start_ts
    elapsed = int(time.time() - start_ts)
    st.session_state[elapsed_key] = float(elapsed)

    ready: list[Any] = []
    n_vid = len(jobs)
    any_processing = False

    for vi, job in enumerate(jobs):
        video_file = client.files.get(name=job["name"])
        job["file"] = video_file
        state = _file_state_name(video_file)

        label = t("video_status_init")
        if n_vid > 1:
            label = f"{label} ({vi + 1}/{n_vid})"

        if state == "FAILED":
            with st.status(label, expanded=True) as status:
                status.update(label=t("video_failed"), state="error", expanded=True)
            st.error(t("video_decode_error"))
            store.pop(key, None)
            _cleanup_local_paths(video_paths)
            st.stop()

        if state == "PROCESSING":
            any_processing = True
            with st.status(label, expanded=True) as status:
                status.update(
                    label=t("video_analyzing", elapsed=elapsed),
                    state="running",
                )
            continue

        with st.status(label, expanded=False) as status:
            status.update(
                label=t("video_done", seconds=elapsed),
                state="complete",
                expanded=False,
            )
        ready.append(video_file)

    if any_processing:
        if should_poll_async_jobs(poll_interval):
            st.rerun()
        st.stop()

    store.pop(key, None)
    for k in (elapsed_key, f"_gemini_video_start_{key}"):
        st.session_state.pop(k, None)
    _cleanup_local_paths(video_paths)
    return ready
