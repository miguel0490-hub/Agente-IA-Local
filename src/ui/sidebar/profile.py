"""Sidebar profile card with hamburger menu for actions."""

from __future__ import annotations

import html
import streamlit as st


def render_sidebar_profile(
    get_user_profile_fn,
    cookie_manager,
    clear_remember_token_fn,
    is_admin: bool = False,
    panel_admin_fn=None,
    panel_contacto_fn=None,
    panel_ajustes_fn=None,
) -> None:
    """Renders user profile card with integrated hamburger menu."""
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

    with st.popover("☰ Menú", use_container_width=True):
        if is_admin and panel_admin_fn is not None:
            if st.button("🛡️ Panel de Administración", key="menu_admin", use_container_width=True):
                st.session_state.show_admin = True
                st.rerun()

        if panel_contacto_fn is not None:
            if st.button("📩 Contactar al Administrador", key="menu_contact", use_container_width=True):
                st.session_state.show_contact = True
                st.rerun()

        if panel_ajustes_fn is not None:
            if st.button("⚙️ Centro de Control", key="menu_settings", use_container_width=True):
                st.session_state.show_settings = True
                st.rerun()

        st.divider()

        st.markdown('<div class="danger-btn">', unsafe_allow_html=True)
        if st.button("🚪 Cerrar Sesión", use_container_width=True, type="primary", key="sidebar_logout"):
            cookie_manager.delete("auth_token")
            clear_remember_token_fn(st.session_state.user_id)
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.get("show_admin"):
        st.session_state.show_admin = False
        if panel_admin_fn is not None:
            panel_admin_fn()

    if st.session_state.get("show_contact"):
        st.session_state.show_contact = False
        if panel_contacto_fn is not None:
            panel_contacto_fn()

    if st.session_state.get("show_settings"):
        st.session_state.show_settings = False
        if panel_ajustes_fn is not None:
            panel_ajustes_fn()

    st.divider()
