"""Tests for RQ background task handlers."""

from __future__ import annotations

from unittest.mock import patch


def test_transcribe_audio_task_rejects_zero_user():
    from src.services.background_tasks import transcribe_audio_task

    out = transcribe_audio_task(b"x", "f.wav", 0)
    assert out["ok"] is False
    assert out["text"] == ""


def test_transcribe_audio_task_requires_groq_key(monkeypatch):
    monkeypatch.setattr(
        "src.services.background_tasks.get_user_api_keys",
        lambda _uid: {},
    )
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    from src.services.background_tasks import transcribe_audio_task

    out = transcribe_audio_task(b"x", "f.wav", 1)
    assert out["ok"] is False
    assert "GROQ" in (out.get("error") or "")


def test_transcribe_audio_task_ok(monkeypatch):
    monkeypatch.setattr(
        "src.services.background_tasks.get_user_api_keys",
        lambda _uid: {"GROQ_API_KEY": "k"},
    )
    monkeypatch.setattr(
        "src.services.background_tasks.transcribe_audio_with_groq",
        lambda _b, _k, _fn: ("hola", None),
    )

    from src.services.background_tasks import transcribe_audio_task

    out = transcribe_audio_task(b"x", "f.wav", 1)
    assert out["ok"] is True
    assert out["text"] == "hola"


def test_transcribe_audio_task_falls_back_to_env_groq(monkeypatch):
    monkeypatch.setattr(
        "src.services.background_tasks.get_user_api_keys",
        lambda _uid: {},
    )
    monkeypatch.setenv("GROQ_API_KEY", "env-key")
    with patch(
        "src.services.background_tasks.transcribe_audio_with_groq",
        return_value=("ok", None),
    ) as m:
        from src.services.background_tasks import transcribe_audio_task

        transcribe_audio_task(b"x", "f.wav", 2)
    m.assert_called_once()
    assert m.call_args[0][1] == "env-key"
