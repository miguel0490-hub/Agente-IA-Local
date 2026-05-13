"""Handlers for auth-related query params."""

from __future__ import annotations

import time
import streamlit as st

from src.core.i18n import t


def handle_auth_query_params(verify_user_token_fn, update_password_with_token_fn) -> None:
    """Processes verification and reset password tokens from query params."""
    if "token" in st.query_params:
        token = st.query_params["token"]
        if verify_user_token_fn(token):
            st.success(t("account_verified"))
        else:
            st.error(t("invalid_token"))
        st.query_params.clear()

    if "reset_token" in st.query_params:
        reset_token = st.query_params["reset_token"]
        st.markdown(f"<h2 style='text-align: center; color: #00F2FE;'>{t('password_reset_title')}</h2>", unsafe_allow_html=True)
        with st.form("reset_password_form"):
            new_password = st.text_input(t("new_password"), type="password")
            confirm_password = st.text_input(t("confirm_new_password"), type="password")
            if st.form_submit_button(t("update_password")):
                if new_password and new_password == confirm_password:
                    success, msg = update_password_with_token_fn(reset_token, new_password)
                    if success:
                        st.success(t(msg))
                        st.query_params.clear()
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(t(msg))
                else:
                    st.error(t("passwords_empty_mismatch"))
        st.stop()
