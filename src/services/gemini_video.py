"""Polling de vídeo Gemini con timeout configurable."""

from __future__ import annotations

import os
import time
from typing import Any, Callable


def wait_for_gemini_video_file(
    client: Any,
    video_file: Any,
    *,
    status_update: Callable[[str], None] | None = None,
    poll_interval_sec: float | None = None,
) -> Any:
    """Espera a que el fichero deje estado PROCESSING (bloqueante acotado)."""
    interval = poll_interval_sec
    if interval is None:
        interval = float(os.getenv("GEMINI_VIDEO_POLL_INTERVAL_SEC", "1.5"))
    max_sec = float(os.getenv("GEMINI_VIDEO_MAX_POLL_SEC", "300"))
    start = time.time()
    while getattr(video_file.state, "name", str(video_file.state)) == "PROCESSING":
        if time.time() - start > max_sec:
            raise TimeoutError("Gemini video processing timeout")
        if status_update:
            status_update(str(int(time.time() - start)))
        time.sleep(interval)
        video_file = client.files.get(name=video_file.name)
    return video_file
