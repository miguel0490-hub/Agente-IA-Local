"""Tests for proxy-aware client IP helper."""

import importlib
import sys
import types

import pytest


def test_get_header_ci_none_and_mapping():
    from src.core import request_context as rc

    assert rc._get_header_ci(None, "X-Forwarded-For") is None
    assert rc._get_header_ci({"X-Forwarded-For": " 10.0.0.1 "}, "X-Forwarded-For") == "10.0.0.1"
    assert rc._get_header_ci({"x-forwarded-for": "10.0.0.2"}, "X-Forwarded-For") == "10.0.0.2"


def test_get_header_ci_object_with_get():
    from src.core import request_context as rc

    class H:
        def get(self, k, default=None):
            if k in ("X-Real-IP", "x-real-ip"):
                return "198.51.100.5"
            return default

    assert rc._get_header_ci(H(), "X-Real-IP") == "198.51.100.5"


def test_get_header_ci_non_mapping_without_get():
    from src.core import request_context as rc

    class Weird:
        pass

    assert rc._get_header_ci(Weird(), "X-Forwarded-For") is None


def _reload_rc(monkeypatch, st_mod):
    monkeypatch.setitem(sys.modules, "streamlit", st_mod)
    import src.core.request_context as rc

    return importlib.reload(rc)


def test_get_remote_address_x_forwarded_for(monkeypatch):
    st_mod = types.SimpleNamespace()
    st_mod.context = types.SimpleNamespace(headers={"X-Forwarded-For": "203.0.113.7, 10.0.0.1"})
    rc = _reload_rc(monkeypatch, st_mod)
    assert rc.get_remote_address() == "203.0.113.7"


def test_get_remote_address_x_real_ip(monkeypatch):
    st_mod = types.SimpleNamespace()
    st_mod.context = types.SimpleNamespace(headers={"X-Real-IP": "198.18.0.9"})
    rc = _reload_rc(monkeypatch, st_mod)
    assert rc.get_remote_address() == "198.18.0.9"


def test_get_remote_address_unknown_without_headers(monkeypatch):
    st_mod = types.SimpleNamespace()
    st_mod.context = types.SimpleNamespace(headers={})
    rc = _reload_rc(monkeypatch, st_mod)
    assert rc.get_remote_address() == "unknown"


def test_get_remote_address_swallows_context_error(monkeypatch):
    class Hook(types.ModuleType):
        def __getattr__(self, name):
            if name == "context":
                raise RuntimeError("boom")
            raise AttributeError(name)

    rc = _reload_rc(monkeypatch, Hook("streamlit"))
    assert rc.get_remote_address() == "unknown"
