"""Saludos iniciales personalizados al seleccionar cada motor / proveedor de IA."""

from __future__ import annotations

from typing import Any

import streamlit as st

from src.core.sanitizer import sanitize_markdown_text


def _has_user_or_assistant_messages(messages: list[dict[str, Any]]) -> bool:
    return any(m.get("role") in ("user", "assistant") for m in messages)


def build_provider_greeting(motor: str) -> str:
    """Devuelve un saludo en Markdown según el motor seleccionado."""
    if motor.startswith("🤖 "):
        name = motor.replace("🤖 ", "", 1).strip() or "tu modelo conectado"
        return (
            f"### 👋 Hola, soy **{name}**\n\n"
            "Estoy conectada por API compatible con OpenAI (OpenAI-like). "
            "Puedo ayudarte con **texto**, razonamiento, código y tareas de agente "
            "según las capacidades del modelo que tienes detrás de esta URL.\n\n"
            "**Cuéntame qué necesitas** y trabajamos en ello."
        )

    catalog: dict[str, str] = {
        "Groq Llama 3.3 (Lead Software Engineer / Creador)": (
            "### 👋 Hola, soy **Groq (Llama 3.3)**\n\n"
            "Estoy optimizada para **velocidad** y **código**: diseño de software, revisión, "
            "refactors, documentación técnica y respuestas largas sin quedarme a medias.\n\n"
            "No genero imágenes ni vídeo por mí sola: para arte usa **Gemini** o el "
            "**Generador de Assets**; para voz e imagen avanzada tienes las herramientas del panel lateral.\n\n"
            "**Pásame tu consulta** — estoy aquí para ayudarte."
        ),
        "Gemini 2.5 Pro (Análisis Multimedia y Arte)": (
            "### 👋 Hola, soy **Gemini 2.5 Pro**\n\n"
            "Soy tu motor **multimodal**: **texto**, **imagen** (generación y análisis de adjuntos) "
            "y **vídeo** (subes un archivo y lo analizo). También combino bien con herramientas y archivos.\n\n"
            "**Cuéntame qué necesitas** — estoy aquí para ayudarte."
        ),
        "OpenRouter (Modelos Gratuitos y de Pago)": (
            "### 👋 Hola, soy **OpenRouter**\n\n"
            "Actúo como puerta de acceso a **muchos modelos** (gratuitos y de pago). "
            "Según el modelo que elijas en tu cuenta, podré ofrecerte distintos estilos de "
            "razonamiento, código y redacción; la calidad multimodal depende del modelo concreto.\n\n"
            "**Pásame tu consulta o el objetivo del documento** — estoy aquí para ayudarte."
        ),
        "Groq Whisper (Oídos: Transcripción STT)": (
            "### 👋 Hola, soy **Groq Whisper**\n\n"
            "Mi función es **transcribir audio a texto** con alta precisión. "
            "Sube tu archivo en el panel **Groq Whisper** del lateral y pulsa transcribir; "
            "el resultado se publicará en el chat.\n\n"
            "**Trae tu audio** cuando quieras — estoy aquí para ayudarte."
        ),
        "OpenAI TTS (Voz: Text-to-Speech)": (
            "### 👋 Hola, soy **OpenAI TTS**\n\n"
            "Convierto **texto en voz natural**. Escribe o pega el guion en el panel **OpenAI TTS** "
            "del lateral, elige voz y genera; el audio aparecerá en el chat para escucharlo y descargarlo.\n\n"
            "**Dime qué quieres que narre** — estoy aquí para ayudarte."
        ),
        "Generador de Assets (Manos: Texto a Imagen)": (
            "### 👋 Hola, soy el **Generador de Assets**\n\n"
            "Convierto tus **descripciones en imágenes** (según las claves configuradas: OpenAI, Stability, etc.). "
            "Usa el panel del lateral, escribe el prompt artístico y genera.\n\n"
            "**Describe la imagen que buscas** — estoy aquí para ayudarte."
        ),
    }

    return catalog.get(
        motor,
        (
            "### 👋 Hola\n\n"
            f"Motor seleccionado: **{motor}**.\n\n"
            "Puedo ayudarte según las capacidades configuradas en la app. "
            "**Cuéntame tu objetivo** — estoy aquí para ayudarte."
        ),
    )


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
