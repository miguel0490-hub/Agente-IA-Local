"""Main page header renderer."""

from __future__ import annotations

import streamlit as st

from src.core.i18n import t


def render_main_header() -> None:
    """Renders the branded hero title block."""
    st.markdown(
        f"""
<div class="hero-header">
    <h1 class="hero-title">⚡ {t("app_title")}</h1>
    <p class="hero-subtitle">{t("header_subtitle")}</p>
</div>
""",
        unsafe_allow_html=True,
    )
