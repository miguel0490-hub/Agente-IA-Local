"""Cookie helpers for authentication flows."""

from __future__ import annotations

import os
from datetime import datetime


def _is_production() -> bool:
    env = (os.getenv("ENVIRONMENT") or "production").strip().lower()
    return env in {"prod", "production"}


def set_auth_cookie(cookie_manager, token: str, expires_at: datetime, key: str = "set_auth_cookie") -> None:
    """
    Sets auth cookie with secure defaults.

    `extra_streamlit_components` versions vary in supported kwargs, so we
    progressively fall back to a minimal compatible call.
    """
    base_kwargs = {
        "expires_at": expires_at,
        "key": key,
        "secure": _is_production(),
        "same_site": "Strict",
    }
    try:
        cookie_manager.set("auth_token", token, httponly=True, **base_kwargs)
        return
    except TypeError:
        pass
    try:
        cookie_manager.set("auth_token", token, **base_kwargs)
        return
    except TypeError:
        cookie_manager.set("auth_token", token)

