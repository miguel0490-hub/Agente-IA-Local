"""Factory helpers for model/audio providers.

Decoupled from ``st.session_state`` — callers must pass ``api_keys`` explicitly.
A thin compatibility layer reads from session_state when the dict is omitted,
so existing call-sites keep working while new code can be fully testable.
"""

from __future__ import annotations

from typing import Any

from src.services.llm_provider import (
    EdgeTTSProvider,
    GeminiProvider,
    GroqWhisperProvider,
    OpenAITTSProvider,
)


def _resolve_keys(api_keys: dict[str, Any] | None) -> dict[str, Any]:
    if api_keys is not None:
        return api_keys
    import streamlit as st
    return st.session_state.get("api_keys", {})


def get_gemini_provider(api_keys: dict[str, Any] | None = None):
    keys = _resolve_keys(api_keys)
    return GeminiProvider(api_key=keys.get("GEMINI_API_KEY"))


def get_groq_whisper_provider(api_keys: dict[str, Any] | None = None):
    keys = _resolve_keys(api_keys)
    return GroqWhisperProvider(api_key=keys.get("GROQ_API_KEY"))


def get_openai_tts_provider(voice: str = "alloy", api_keys: dict[str, Any] | None = None):
    keys = _resolve_keys(api_keys)
    return OpenAITTSProvider(voice=voice, api_key=keys.get("OPENAI_API_KEY"))


def get_edge_tts_provider(voice: str):
    return EdgeTTSProvider(voice=voice)
