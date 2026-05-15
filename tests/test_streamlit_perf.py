"""Tests de optimizaciones de rendimiento Streamlit."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_redact_text_masks_secrets():
    from src.core.observability import _redact_text

    out = _redact_text("api_key=SECRET token=abc password=pw")
    assert "SECRET" not in out
    assert "[REDACTED]" in out


def test_before_send_redacts_event():
    from src.core.observability import _before_send

    event = {
        "message": "api_key=leak",
        "exception": {"values": [{"value": "password=leak2"}]},
    }
    result = _before_send(event, {})
    assert "[REDACTED]" in result["message"]
    assert "[REDACTED]" in result["exception"]["values"][0]["value"]


def test_init_observability_without_sentry_sdk():
    import src.core.observability as obs

    obs._SENTRY_INITIALIZED = False
    with patch.object(obs, "sentry_sdk", None):
        assert obs.init_observability() is False


def test_init_observability_without_dsn():
    import src.core.observability as obs

    obs._SENTRY_INITIALIZED = False
    fake_sdk = MagicMock()
    with patch.object(obs, "sentry_sdk", fake_sdk):
        with patch.dict("os.environ", {"SENTRY_DSN": ""}, clear=False):
            assert obs.init_observability() is False
            fake_sdk.init.assert_not_called()


def test_init_observability_only_initializes_sentry_once():
    import src.core.observability as obs

    obs._SENTRY_INITIALIZED = False
    fake_sdk = MagicMock()
    with patch.object(obs, "sentry_sdk", fake_sdk):
        with patch.dict("os.environ", {"SENTRY_DSN": "https://example@sentry.io/1"}, clear=False):
            assert obs.init_observability() is True
            assert obs.init_observability() is True
            fake_sdk.init.assert_called_once()


def test_cached_user_chats_invalidates_on_bump(monkeypatch):
    pytest.importorskip("streamlit")
    import streamlit as st

    if not hasattr(st, "session_state"):
        pytest.skip("No Streamlit session in unit test")

    from src.core.streamlit_cache import cached_user_chats, invalidate_sidebar_cache

    calls = {"n": 0}

    def _fetch(uid: int):
        calls["n"] += 1
        return [{"id": 1, "title": "t"}]

    st.session_state.clear()
    cached_user_chats(7, _fetch)
    cached_user_chats(7, _fetch)
    assert calls["n"] == 1
    invalidate_sidebar_cache()
    cached_user_chats(7, _fetch)
    assert calls["n"] == 2
