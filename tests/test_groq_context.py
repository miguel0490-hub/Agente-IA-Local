"""Tests de límites de contexto Groq."""

from __future__ import annotations

from src.services.context_manager import truncate_text
from src.services.llm_provider import GroqProvider


def test_truncate_text():
    long = "a" * 100
    out, cut = truncate_text(long, 50, suffix="…")
    assert cut
    assert len(out) <= 50 + 5


def test_groq_candidates_no_8b_by_default(monkeypatch):
    monkeypatch.delenv("GROQ_EXTRA_FALLBACK_MODEL", raising=False)
    names = GroqProvider._groq_model_candidates("llama-3.3-70b-versatile", "llama-3.3-70b-versatile")
    assert "llama-3.1-8b-instant" not in names


def test_groq_candidates_extra_fallback(monkeypatch):
    monkeypatch.setenv("GROQ_EXTRA_FALLBACK_MODEL", "llama-3.1-8b-instant")
    names = GroqProvider._groq_model_candidates("llama-3.3-70b-versatile", "")
    assert "llama-3.1-8b-instant" in names
