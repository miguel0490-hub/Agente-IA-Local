"""Resolución de modelos Gemini (API Google AI) con fallbacks."""

from __future__ import annotations

import os

DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"
_BUILTIN_FALLBACKS = ("gemini-2.5-flash", "gemini-2.0-flash")


def gemini_model_candidates() -> list[str]:
    """Orden de modelos a probar: env primario + fallbacks sin duplicados."""
    primary = (os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL).strip()
    extra = (os.getenv("GEMINI_MODEL_FALLBACKS") or "").strip()
    fallbacks = (
        [m.strip() for m in extra.split(",") if m.strip()]
        if extra
        else list(_BUILTIN_FALLBACKS)
    )
    seen: set[str] = set()
    out: list[str] = []
    for name in (primary, *fallbacks):
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def is_gemini_model_not_found_error(exc: BaseException) -> bool:
    """True si la API indica modelo inexistente o no soportado (p. ej. 404)."""
    msg = str(exc).lower()
    needles = (
        "not found",
        "404",
        "is not supported",
        "unknown model",
        "invalid model",
    )
    return any(n in msg for n in needles)
