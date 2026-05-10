"""Factory helpers for model/audio providers."""

from __future__ import annotations

import streamlit as st

from src.services.llm_provider import (
    EdgeTTSProvider,
    GeminiProvider,
    GroqWhisperProvider,
    OpenAITTSProvider,
)


def get_gemini_provider():
    return GeminiProvider(api_key=st.session_state.api_keys.get("GEMINI_API_KEY"))


def get_groq_whisper_provider():
    return GroqWhisperProvider(api_key=st.session_state.api_keys.get("GROQ_API_KEY"))


def get_openai_tts_provider(voice="alloy"):
    return OpenAITTSProvider(voice=voice, api_key=st.session_state.api_keys.get("OPENAI_API_KEY"))


def get_edge_tts_provider(voice):
    return EdgeTTSProvider(voice=voice)
