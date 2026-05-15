"""Async task queue facade (RQ with sync fallback)."""

from __future__ import annotations

import os
from typing import Optional, Any

try:
    import redis
    from rq import Queue
    from rq.job import Job
except Exception:  # pragma: no cover
    redis = None
    Queue = None
    Job = None


_redis_connection: Any = None
_redis_url_cached: str | None = None


def _get_redis_connection():
    global _redis_connection, _redis_url_cached
    if not redis:
        return None
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return None
    if _redis_connection is not None and _redis_url_cached == redis_url:
        try:
            _redis_connection.ping()
            return _redis_connection
        except Exception:
            _redis_connection = None
            _redis_url_cached = None
    try:
        # RQ serializa jobs con pickle; decode_responses=True rompe payloads binarios.
        conn = redis.from_url(redis_url, decode_responses=False, socket_timeout=1.5)
        conn.ping()
        _redis_connection = conn
        _redis_url_cached = redis_url
        return conn
    except Exception:
        _redis_connection = None
        _redis_url_cached = None
        return None


def _enqueue_task(task_path: str, *args: Any, timeout: int = 600):
    if os.getenv("ENABLE_ASYNC_TASKS", "1").strip() not in {"1", "true", "TRUE"}:
        return None
    if not Queue:
        return None
    conn = _get_redis_connection()
    if not conn:
        return None
    queue_name = os.getenv("RQ_QUEUE_NAME", "superagente")
    q = Queue(queue_name, connection=conn, default_timeout=timeout)
    return q.enqueue(task_path, *args, result_ttl=86400, failure_ttl=86400)


def enqueue_rag_indexing(filename: str, content: str) -> Optional[str]:
    """Enqueues large-document indexing; returns job id or None if unavailable."""
    job = _enqueue_task("src.services.background_tasks.index_document_task", filename, content, timeout=600)
    return job.id if job else None


def enqueue_conversion(input_path: str, output_path: str) -> Optional[str]:
    """Enqueues a heavy conversion task; returns job id or None if unavailable."""
    job = _enqueue_task("src.services.background_tasks.convert_file_task", input_path, output_path, timeout=1800)
    return job.id if job else None


def enqueue_transcription(audio_bytes: bytes, filename: str, user_id: int) -> Optional[str]:
    """Enqueues STT transcription task; returns job id or None if unavailable.

    No se envía la API key por Redis: el worker resuelve GROQ desde la BD del usuario
    (o variable de entorno GROQ_API_KEY como respaldo operativo).
    """
    job = _enqueue_task(
        "src.services.background_tasks.transcribe_audio_task",
        audio_bytes,
        filename,
        int(user_id),
        timeout=1800,
    )
    return job.id if job else None


def get_job_status(job_id: str) -> dict:
    """Returns job status payload for UI polling."""
    if not job_id or not Job:
        return {"status": "unknown", "result": None, "error": "Job inválido."}
    conn = _get_redis_connection()
    if not conn:
        return {"status": "unavailable", "result": None, "error": "Cola asíncrona no disponible."}
    try:
        job = Job.fetch(job_id, connection=conn)
    except Exception as e:
        return {"status": "missing", "result": None, "error": str(e)}
    status = job.get_status(refresh=True)
    if status == "finished":
        return {"status": "finished", "result": job.result, "error": None}
    if status == "failed":
        return {"status": "failed", "result": None, "error": str(job.exc_info or "Task fallida.")}
    return {"status": status, "result": None, "error": None}
