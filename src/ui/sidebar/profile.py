"""Sidebar profile card and logout actions."""

from __future__ import annotations

import html
import streamlit as st


def render_sidebar_profile(get_user_profile_fn, cookie_manager, clear_remember_token_fn) -> None:
    """Renders user profile card and logout flow inside sidebar."""
    user_data = get_user_profile_fn(st.session_state.user_id)
    if user_data:
        safe_first = html.escape(user_data.get("first_name", "Usuario"))
        safe_last = html.escape(user_data.get("last_name", ""))
        safe_user = html.escape(user_data.get("username", "user"))

        profile_html = f"""
<div class="user-profile-card">
    <div class="user-greeting">👋 BIENVENIDO</div>
    <div class="user-name">{safe_first} {safe_last}</div>
    <div class="user-handle">@{safe_user}</div>
</div>
"""
        st.markdown(profile_html, unsafe_allow_html=True)

    st.markdown('<div class="danger-btn">', unsafe_allow_html=True)
    if st.button("🚪 Cerrar Sesión", use_container_width=True, type="primary", key="sidebar_logout"):
        cookie_manager.delete("auth_token")
        clear_remember_token_fn(st.session_state.user_id)
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.divider()
