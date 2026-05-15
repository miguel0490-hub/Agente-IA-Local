"""Sidebar profile card with hamburger menu for actions."""

from __future__ import annotations

import html

import streamlit as st

from src.core.i18n import SUPPORTED_LANGUAGES, get_language, set_language, t
from src.core.session_manager import clear_user_session
from src.ui.components.notifications import get_unread_count, render_notification_center

# ISO 3166-1 alpha-2 for flagcdn (PNG flags — evita fallos de emoji en Windows).
_SIDEBAR_FLAG_CC: dict[str, str] = {
    "es": "es",
    "en": "gb",
    "fr": "fr",
    "de": "de",
    "pt": "pt",
}


def _sidebar_flag_image_url(code: str) -> str:
    cc = _SIDEBAR_FLAG_CC.get(code, code)
    return f"https://flagcdn.com/w20/{cc}.png"


def _on_sidebar_language_change() -> None:
    code = st.session_state.get("sidebar_lang_selectbox")
    if code in SUPPORTED_LANGUAGES:
        set_language(code)


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
    lang_codes = list(SUPPORTED_LANGUAGES.keys())
    current_lang = get_language()
    if current_lang not in lang_codes:
        current_lang = "es"

    st.markdown(
        f'<p class="sidebar-language-hint" style="margin:-0.45rem 0 0.2rem 0;padding:0;'
        f'text-align:left;line-height:1.3;'
        f'color:#94a3b8;font-weight:500;">{html.escape(t("sidebar_language_choose_label"))}</p>',
        unsafe_allow_html=True,
    )
    flag_col, sel_col = st.columns([0.12, 0.88], gap="small")
    with flag_col:
        st.markdown(
            f'<div class="sidebar-language-flag-cell" style="min-height:2.2rem;display:flex;align-items:center;justify-content:center;">'
            f'<img src="{html.escape(_sidebar_flag_image_url(current_lang))}" width="22" height="16" '
            f'style="display:block;border-radius:2px;object-fit:cover;'
            f'box-shadow:0 0 0 1px rgba(255,255,255,0.08);" alt="" loading="lazy"/>'
            f"</div>",
            unsafe_allow_html=True,
        )
    with sel_col:
        st.selectbox(
            t("sidebar_language"),
            options=lang_codes,
            index=lang_codes.index(current_lang),
            format_func=lambda c: SUPPORTED_LANGUAGES[c],
            key="sidebar_lang_selectbox",
            label_visibility="collapsed",
            on_change=_on_sidebar_language_change,
        )

    st.markdown('<div style="height:0.2rem;"></div>', unsafe_allow_html=True)

    user_data = get_user_profile_fn(st.session_state.user_id)
    if user_data:
        safe_first = html.escape(user_data.get("first_name", t("username")))
        safe_last = html.escape(user_data.get("last_name", ""))
        safe_user = html.escape(user_data.get("username", "user"))

        profile_html = f"""
<div class="user-profile-card">
    <div class="user-greeting">👋 {t("welcome")}</div>
    <div class="user-name">{safe_first} {safe_last}</div>
    <div class="user-handle">@{safe_user}</div>
</div>
"""
        st.markdown(profile_html, unsafe_allow_html=True)

    with st.popover(t("menu"), use_container_width=True):
        if is_admin and panel_admin_fn is not None:
            if st.button(t("admin_panel"), key="menu_admin", use_container_width=True):
                st.session_state.show_admin = True
                st.rerun()

        if panel_contacto_fn is not None:
            if st.button(t("contact_admin"), key="menu_contact", use_container_width=True):
                st.session_state.show_contact = True
                st.rerun()

        if panel_ajustes_fn is not None:
            if st.button(t("control_center"), key="menu_settings", use_container_width=True):
                st.session_state.show_settings = True
                st.rerun()

        unread = get_unread_count()
        notif_label = t("notifications_with_count", count=unread) if unread > 0 else "🔔 " + t("notifications")
        if st.button(notif_label, key="menu_notif", use_container_width=True):
            st.session_state.show_notifications = True
            st.rerun()

        st.divider()

        if st.button(t("logout"), use_container_width=True, key="sidebar_logout"):
            cookie_manager.delete("auth_token")
            clear_remember_token_fn(st.session_state.user_id)
            clear_user_session()
            st.rerun()

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

    if st.session_state.get("show_notifications"):
        st.session_state.show_notifications = False
        _panel_notificaciones()

    st.divider()


@st.dialog("🔔 " + t("notifications"), width="large")
def _panel_notificaciones() -> None:
    """Full notification panel rendered as a dialog, consistent with other menu panels."""
    render_notification_center()
