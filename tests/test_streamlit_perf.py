"""Tests de optimizaciones de rendimiento Streamlit."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


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
