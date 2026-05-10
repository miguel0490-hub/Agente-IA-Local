"""Handlers for auth-related query params."""

from __future__ import annotations

import time
import streamlit as st


def handle_auth_query_params(verify_user_token_fn, update_password_with_token_fn) -> None:
    """Processes verification and reset password tokens from query params."""
    if "token" in st.query_params:
        token = st.query_params["token"]
        if verify_user_token_fn(token):
            st.success("✅ Cuenta Premium verificada exitosamente. Ya puedes iniciar sesión.")
        else:
            st.error("❌ El token de verificación es inválido o la cuenta ya ha sido verificada.")
        st.query_params.clear()

    if "reset_token" in st.query_params:
        reset_token = st.query_params["reset_token"]
        st.markdown("<h2 style='text-align: center; color: #00F2FE;'>Recuperación de Contraseña</h2>", unsafe_allow_html=True)
        with st.form("reset_password_form"):
            new_password = st.text_input("Nueva Contraseña", type="password")
            confirm_password = st.text_input("Confirmar Nueva Contraseña", type="password")
            if st.form_submit_button("Actualizar Contraseña"):
                if new_password and new_password == confirm_password:
                    success, msg = update_password_with_token_fn(reset_token, new_password)
                    if success:
                        st.success(msg)
                        st.query_params.clear()
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.error("Las contraseñas no coinciden o están vacías.")
        st.stop()
