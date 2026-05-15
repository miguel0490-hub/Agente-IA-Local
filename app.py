"""
SuperAgente IA Pro — punto de entrada Streamlit.

Solo configura la página y delega en `src.ui.app_shell`.
"""

from __future__ import annotations

import os

import streamlit as st

from src.core.i18n import set_language, t
from src.ui.app_shell import run_authenticated_app, run_bootstrap_and_public_ui

if "app_language" in st.session_state:
    set_language(st.session_state.app_language)

st.set_page_config(
    page_title=t("app_title"),
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

if not os.getenv("APP_URL"):
    os.environ["STREAMLIT_SERVER_PORT"] = str(st.get_option("server.port"))

_cookie_manager = run_bootstrap_and_public_ui()
run_authenticated_app(_cookie_manager)
