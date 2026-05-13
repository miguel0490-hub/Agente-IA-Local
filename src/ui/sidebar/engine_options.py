"""Etiquetas del selector de motor (misma orden que el sidebar principal)."""

from __future__ import annotations

from typing import Any


def motor_disponibles_labels(api_keys: dict[str, Any] | None) -> list[str]:
    """Devuelve las etiquetas del desplegable Cerebro activo (Groq, Gemini, … + custom)."""
    from src.core.i18n import t

    keys = api_keys or {}
    opts: list[str] = [
        t("engine_groq"),
        t("engine_gemini"),
        t("engine_openrouter"),
        t("engine_whisper"),
        t("engine_tts"),
        t("engine_image"),
    ]
    for cm in keys.get("CUSTOM_MODELS", []):
        opts.append(f"🤖 {cm['name']}")
    return opts


def default_motor_index_for_preferred(preferred: str | None) -> int | None:
    """Índice por defecto según ``preferred_model`` del perfil (solo Groq/Gemini en base)."""
    if not preferred:
        return None
    p = preferred.lower()
    if p == "groq":
        return 0
    if p == "gemini":
        return 1
    return None
