"""Tests para resolución de modelos Gemini."""

from __future__ import annotations

import pytest

from src.services.gemini_models import (
    DEFAULT_GEMINI_MODEL,
    gemini_model_candidates,
    is_gemini_model_not_found_error,
)


def test_default_model_is_25_pro():
    assert DEFAULT_GEMINI_MODEL == "gemini-2.5-pro"


def test_candidates_dedupe(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-pro")
    monkeypatch.setenv("GEMINI_MODEL_FALLBACKS", "gemini-2.5-pro,gemini-2.5-flash")
    names = gemini_model_candidates()
    assert names[0] == "gemini-2.5-pro"
    assert names.count("gemini-2.5-pro") == 1
    assert "gemini-2.5-flash" in names


def test_is_model_not_found():
    assert is_gemini_model_not_found_error(Exception("404 models/gemini-1.5-pro is not found"))
    assert not is_gemini_model_not_found_error(Exception("rate limit exceeded"))
