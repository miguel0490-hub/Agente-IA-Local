"""Tests para saludos por proveedor."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.ui.chat.provider_greetings import (
    _apply_provider_greeting_session,
    build_provider_greeting,
    maybe_inject_provider_greeting,
    plan_provider_greeting,
)


class _FakeSession:
    """Sustituto mínimo de st.session_state para pruebas."""

    def __init__(self) -> None:
        self.messages: list = []
        self.chat_id = 1
        self.api_keys: dict = {}
        self._greeting_prev_chat_id: int | None = None
        self.last_motor_selected: str | None = None

    def get(self, key: str, default=None):
        return getattr(self, key, default)


@pytest.mark.parametrize(
    "motor,needle",
    [
        ("Groq Llama 3.3 (Lead Software Engineer / Creador)", "Groq"),
        ("Gemini 2.5 Pro (Análisis Multimedia y Arte)", "Gemini"),
        ("OpenRouter (Modelos Gratuitos y de Pago)", "OpenRouter"),
        ("Groq Whisper (Oídos: Transcripción STT)", "Whisper"),
        ("OpenAI TTS (Voz: Text-to-Speech)", "OpenAI TTS"),
        ("Generador de Assets (Manos: Texto a Imagen)", "Generador de Assets"),
        ("🤖 Mi modelo local", "Mi modelo local"),
        ("Motor fantasma desconocido", "Motor fantasma"),
    ],
)
def test_build_provider_greeting_contains_identity(motor: str, needle: str) -> None:
    text = build_provider_greeting(motor)
    assert needle in text
    assert "Hola" in text


def test_plan_chat_switch_with_history_syncs_no_greeting() -> None:
    new_tr, last, greet = plan_provider_greeting(
        prev_tracked_chat_id=1,
        chat_id=2,
        messages=[{"role": "user", "content": "hola"}],
        motor="Groq Llama 3.3 (Lead Software Engineer / Creador)",
        last_motor_selected=None,
    )
    assert new_tr == 2
    assert last == "Groq Llama 3.3 (Lead Software Engineer / Creador)"
    assert greet is None


def test_plan_chat_switch_empty_injects() -> None:
    new_tr, last, greet = plan_provider_greeting(
        prev_tracked_chat_id=1,
        chat_id=2,
        messages=[],
        motor="Gemini 2.5 Pro (Análisis Multimedia y Arte)",
        last_motor_selected="Groq Llama 3.3 (Lead Software Engineer / Creador)",
    )
    assert new_tr == 2
    assert last == "Gemini 2.5 Pro (Análisis Multimedia y Arte)"
    assert greet is not None
    assert "Gemini" in greet


def test_plan_first_open_injects() -> None:
    new_tr, last, greet = plan_provider_greeting(
        prev_tracked_chat_id=None,
        chat_id=9,
        messages=[],
        motor="OpenRouter (Modelos Gratuitos y de Pago)",
        last_motor_selected=None,
    )
    assert new_tr == 9
    assert greet is not None


def test_plan_same_motor_skips() -> None:
    m = "Groq Llama 3.3 (Lead Software Engineer / Creador)"
    new_tr, last, greet = plan_provider_greeting(
        prev_tracked_chat_id=9,
        chat_id=9,
        messages=[{"role": "assistant", "content": "x"}],
        motor=m,
        last_motor_selected=m,
    )
    assert greet is None
    assert last == m


def test_apply_persists_when_greeting(monkeypatch) -> None:
    sess = _FakeSession()
    saved = []

    def _save(cid, msgs, keys):
        saved.append((cid, len(msgs)))

    _apply_provider_greeting_session(sess, "Groq Llama 3.3 (Lead Software Engineer / Creador)", _save)
    assert len(sess.messages) == 1
    assert sess.messages[0]["role"] == "assistant"
    assert saved == [(1, 1)]


def test_apply_skips_when_synced(monkeypatch) -> None:
    sess = _FakeSession()
    sess.messages = [{"role": "user", "content": "hola"}]
    sess._greeting_prev_chat_id = 5
    sess.chat_id = 7

    def _boom(*a, **k):
        raise AssertionError("no debería guardar")

    _apply_provider_greeting_session(
        sess,
        "Groq Llama 3.3 (Lead Software Engineer / Creador)",
        _boom,
    )
    assert len(sess.messages) == 1


def test_maybe_inject_delegates_to_apply() -> None:
    with patch("src.ui.chat.provider_greetings._apply_provider_greeting_session") as mock_apply:
        maybe_inject_provider_greeting("Groq Llama 3.3 (Lead Software Engineer / Creador)", lambda *a, **k: None)
        mock_apply.assert_called_once()
