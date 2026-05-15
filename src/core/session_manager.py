"""Session lifecycle management: cookie init, idle timeout, auto-login."""

from __future__ import annotations

import datetime
import os
import time
import uuid

import streamlit as st
import extra_streamlit_components as stx

from src.core.auth_cookies import set_auth_cookie
from src.core.i18n import t

_USER_SESSION_KEYS = frozenset(
    {
        "user_id",
        "api_keys",
        "chat_id",
        "onboarding_done",
        "messages",
        "rol_activo",
        "motor_activo_idx",
        "selector_rol",
        "onboarding_step",
        "temp_keys",
        "auto_close_sidebar",
        "temp_custom_models",
        "show_settings",
        "show_contact",
        "show_admin",
        "show_notifications",
        "form_clear_counter",
        "security_events",
        "last_activity_ts",
        "staged_attachments",
        "attachment_hub_uploader_inc",
        "confirm_delete_chat",
        "pending_conversion_jobs",
        "pending_stt_jobs",
        "suggested_format",
        "last_motor_selected",
        "chat_list",
        "active_role",
        "motor_manual_selector",
        "sidebar_lang_selectbox",
    }
)


def clear_user_session() -> None:
    """Clears only app-owned user state, preserving Streamlit/widget internals."""
    for key in _USER_SESSION_KEYS:
        if key in st.session_state:
            del st.session_state[key]


def init_cookie_manager():
    """Initializes and caches the CookieManager singleton in session_state."""
    if "cookie_manager" not in st.session_state:
        st.session_state.cookie_manager = stx.CookieManager(key="global_cookie_manager")
    return st.session_state.cookie_manager


def check_idle_timeout(cookie_manager, clear_remember_token_fn) -> None:
    """Expires the session if idle time exceeds the configured threshold."""
    if not st.session_state.user_id:
        return

    idle_timeout_min = int((os.getenv("SESSION_IDLE_TIMEOUT_MINUTES") or "120").strip() or "120")
    idle_timeout_sec = max(5, idle_timeout_min) * 60
    now_ts = time.time()
    last_ts = float(st.session_state.get("last_activity_ts", now_ts))

    if now_ts - last_ts > idle_timeout_sec:
        cookie_manager.delete("auth_token")
        clear_remember_token_fn(st.session_state.user_id)
        clear_user_session()
        st.warning(t("session_idle_expired"))
        st.rerun()

    st.session_state.last_activity_ts = now_ts


def try_auto_login(cookie_manager, verify_remember_token_fn, get_user_api_keys_fn, update_remember_token_fn) -> None:
    """Restores a session from the auth cookie (Remember Me) with token rotation."""
    if st.session_state.user_id:
        return

    cookies = cookie_manager.get_all()
    auth_cookie = cookies.get("auth_token") if isinstance(cookies, dict) else cookie_manager.get("auth_token")
    if not auth_cookie:
        return

    remembered_user_id = verify_remember_token_fn(auth_cookie)
    if not remembered_user_id:
        cookie_manager.delete("auth_token")
        return

    from src.core.streamlit_cache import invalidate_sidebar_cache

    st.session_state.user_id = remembered_user_id
    st.session_state.pop("_app_dialogs", None)
    invalidate_sidebar_cache()
    keys = get_user_api_keys_fn(remembered_user_id)
    st.session_state.api_keys = keys
    if keys:
        st.session_state.onboarding_done = True

    new_token = uuid.uuid4().hex
    remember_days = int((os.getenv("REMEMBER_ME_DAYS") or "7").strip() or "7")
    expires = datetime.datetime.now() + datetime.timedelta(days=max(1, remember_days))
    update_remember_token_fn(remembered_user_id, new_token, expires)
    set_auth_cookie(cookie_manager, new_token, expires, key="refresh_auth_cookie")
    st.rerun()
