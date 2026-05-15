"""Lazy helpers for the ``google.genai`` SDK (replaces deprecated ``google.generativeai``)."""

from __future__ import annotations

from typing import Any


def lazy_google_genai() -> Any:
    """Import ``google.genai`` only when Gemini is used."""
    from google import genai

    return genai


def get_genai_client(api_key: str) -> Any:
    """Build an authenticated Gemini client."""
    return lazy_google_genai().Client(api_key=api_key)
