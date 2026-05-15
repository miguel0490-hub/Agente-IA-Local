"""Inyección de estilos globales (estático preferido sobre HTML inline)."""

from __future__ import annotations

import streamlit as st

_STATIC_CSS_HREF = "/app/static/superagente.css"


def inject_app_styles() -> None:
    """Enlaza CSS estático; fallback a inline si el usuario desactiva estáticos."""
    if st.session_state.get("_disable_static_css"):
        from src.ui.theme import ESTILOS_CSS

        st.markdown(ESTILOS_CSS, unsafe_allow_html=True)
        return
    st.markdown(
        f"<link rel='stylesheet' href='{_STATIC_CSS_HREF}'/>",
        unsafe_allow_html=True,
    )
