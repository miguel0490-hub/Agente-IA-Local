"""Saludos iniciales al seleccionar cada motor / proveedor (textos vía i18n)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from src.core.i18n import t
from src.core.sanitizer import sanitize_markdown_text


def _has_user_or_assistant_messages(messages: list[dict[str, Any]]) -> bool:
    return any(m.get("role") in ("user", "assistant") for m in messages)


def _motor_greeting_kind(motor: str) -> str:
    """Clasifica el motor por etiqueta traducida (cualquier idioma activo)."""
    if motor.startswith("🤖 "):
        return "custom"
    if "Whisper" in motor or ("STT" in motor and "Groq" in motor):
        return "whisper"
    if "TTS" in motor or "Text-to-Speech" in motor:
        return "tts"
    if (
        "Asset Generator" in motor
        or "Generador" in motor
        or "Text to Image" in motor
        or "Texto a Imagen" in motor
    ):
        return "image"
    if "OpenRouter" in motor:
        return "openrouter"
    if "Gemini" in motor:
        return "gemini"
    if "Groq" in motor:
        return "groq"
    return "generic"


def build_provider_greeting(motor: str) -> str:
    """Markdown de saludo según motor (traducido al idioma de la sesión)."""
    kind = _motor_greeting_kind(motor)
    if kind == "custom":
        name = motor.replace("🤖 ", "", 1).strip() or "model"
        return t("greeting_custom", name=name)
    key = {
        "groq": "greeting_groq",
        "gemini": "greeting_gemini",
        "openrouter": "greeting_openrouter",
        "whisper": "greeting_whisper",
        "tts": "greeting_tts",
        "image": "greeting_image",
        "generic": "greeting_generic",
    }.get(kind, "greeting_generic")
    if key == "greeting_generic":
        return t("greeting_generic", motor=motor)
    return t(key)


def plan_provider_greeting(
    *,
    prev_tracked_chat_id: int | None,
    chat_id: int | None,
    messages: list,
    motor: str,
    last_motor_selected: str | None,
) -> tuple[int | None, str | None, str | None]:
    """
    Decide si hay que insertar saludo.

    Devuelve:
      - nuevo id de chat seguido para futuras ejecuciones
      - último motor a recordar (tras sincronizar o tras saludo)
      - texto de saludo o None si no corresponde
    """
    chat_just_changed = (
        prev_tracked_chat_id is not None and chat_id is not None and prev_tracked_chat_id != chat_id
    )

    new_tracked = prev_tracked_chat_id
    effective_last = last_motor_selected

    if chat_just_changed:
        new_tracked = chat_id
        if _has_user_or_assistant_messages(messages):
            return (new_tracked, motor, None)
        effective_last = None
    elif prev_tracked_chat_id is None and chat_id is not None:
        new_tracked = chat_id

    if motor == effective_last:
        return (new_tracked, effective_last, None)

    return (new_tracked, motor, build_provider_greeting(motor))


def _apply_provider_greeting_session(
    session_state: Any,
    motor: str,
    guardar_memoria_fn,
) -> None:
    """Implementación testeable sobre el objeto `session_state` de Streamlit."""
    prev = session_state.get("_greeting_prev_chat_id")
    chat_id = session_state.chat_id
    last_motor = session_state.get("last_motor_selected")
    msgs = list(session_state.messages)

    new_tracked, new_last, greeting = plan_provider_greeting(
        prev_tracked_chat_id=prev,
        chat_id=chat_id,
        messages=msgs,
        motor=motor,
        last_motor_selected=last_motor,
    )

    session_state._greeting_prev_chat_id = new_tracked
    if greeting is None:
        session_state.last_motor_selected = new_last
        return

    safe = sanitize_markdown_text(greeting)
    session_state.messages.append({"role": "assistant", "content": safe})
    session_state.last_motor_selected = new_last
    if chat_id:
        guardar_memoria_fn(chat_id, session_state.messages, session_state.api_keys)


def maybe_inject_provider_greeting(motor: str, guardar_memoria_fn) -> None:
    """Inserta un saludo del asistente cuando cambia el motor o un chat vacío nuevo."""
    _apply_provider_greeting_session(st.session_state, motor, guardar_memoria_fn)
