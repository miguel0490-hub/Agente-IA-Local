"""Límites de visualización del historial de chat en UI."""

from __future__ import annotations

import os

DEFAULT_CHAT_UI_MESSAGE_LIMIT = 80


def chat_ui_message_limit() -> int:
    raw = os.getenv("CHAT_UI_MESSAGE_LIMIT", str(DEFAULT_CHAT_UI_MESSAGE_LIMIT)).strip()
    try:
        return max(20, min(500, int(raw)))
    except ValueError:
        return DEFAULT_CHAT_UI_MESSAGE_LIMIT


def messages_for_display(messages: list, *, limit: int | None = None) -> tuple[list, int]:
    """Devuelve (ventana visible, número de mensajes ocultos al inicio)."""
    if not messages:
        return [], 0
    cap = limit if limit is not None else chat_ui_message_limit()
    if len(messages) <= cap:
        return messages, 0
    hidden = len(messages) - cap
    return messages[-cap:], hidden
