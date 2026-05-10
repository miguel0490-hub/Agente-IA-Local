"""Authentication gate UI (login, register, password reset request)."""

from __future__ import annotations

import datetime
import os
import re
import time

import streamlit as st
from src.core.auth_cookies import set_auth_cookie
from src.core.request_context import get_remote_address
from src.core.security import check_scoped_rate_limit
from src.core.security import get_login_backoff_seconds
from src.core.security import get_login_rate_limit_config
from src.core.security import login_security_backend_ready
from src.core.security import record_login_failure


def render_auth_gate(
    cookie_manager,
    verify_login_fn,
    get_user_api_keys_fn,
    update_remember_token_fn,
    clear_remember_token_fn,
    register_user_fn,
) -> None:
    """Renders auth UI and stops execution until user session is established."""
    if st.session_state.user_id:
        return

    col_left, central_col, col_right = st.columns([1, 2, 1])
    with central_col:
        st.markdown("<h1 style='text-align: center; color: #00F2FE;'>⚡ SuperAgente IA Pro</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: #A0AAB5;'>Acceso al Sistema</h3>", unsafe_allow_html=True)

        tab1, tab2, tab3 = st.tabs(["Iniciar Sesión", "Registrarse", "Olvidé mi contraseña"])

        with tab1:
            with st.form("login_form"):
                username = st.text_input("Usuario", placeholder="Tu usuario", autocomplete="username")
                password = st.text_input("Contraseña", type="password", autocomplete="current-password")
                remember_me = st.checkbox("🔒 Recuérdame en este dispositivo", value=False)
                submitted = st.form_submit_button("Entrar", use_container_width=True)
                if submitted:
                    if username and password:
                        remote = get_remote_address()
                        user_key = f"user:{str(username).strip().lower()}"
                        ip_key = f"ip:{remote}"
                        ip_limit, ip_window = get_login_rate_limit_config("ip")
                        user_limit, user_window = get_login_rate_limit_config("user")
                        if not login_security_backend_ready():
                            st.error(
                                "El servicio de autenticación no está disponible temporalmente. Intenta de nuevo más tarde."
                            )
                        elif not check_scoped_rate_limit(ip_key, "login", limit=ip_limit, window_seconds=ip_window):
                            st.error("Demasiados intentos desde esta red. Espera unos minutos e inténtalo de nuevo.")
                        elif not check_scoped_rate_limit(
                            user_key, "login", limit=user_limit, window_seconds=user_window
                        ):
                            st.error("Demasiados intentos de inicio de sesión para este usuario. Espera unos minutos.")
                        else:
                            ip_wait = get_login_backoff_seconds(ip_key, "ip")
                            user_wait = get_login_backoff_seconds(user_key, "user")
                            wait_seconds = max(ip_wait, user_wait)
                            if wait_seconds > 0:
                                st.error(
                                    f"Por seguridad, espera {wait_seconds}s antes de volver a intentar iniciar sesión."
                                )
                            else:
                                with st.spinner("Autenticando conexión segura..."):
                                    success, result = verify_login_fn(username, password)
                                if success:
                                    st.session_state.user_id = result
                                    keys = get_user_api_keys_fn(result)
                                    st.session_state.api_keys = keys
                                    if keys:
                                        st.session_state.onboarding_done = True
                                    if remember_me:
                                        import uuid

                                        _token = uuid.uuid4().hex
                                        remember_days = int((os.getenv("REMEMBER_ME_DAYS") or "7").strip() or "7")
                                        expires_date = datetime.datetime.now() + datetime.timedelta(days=max(1, remember_days))
                                        update_remember_token_fn(result, _token, expires_date)
                                        set_auth_cookie(cookie_manager, _token, expires_date, key="set_auth_cookie")
                                    else:
                                        cookie_manager.delete("auth_token")
                                        clear_remember_token_fn(result)
                                    time.sleep(0.8)
                                    st.rerun()
                                else:
                                    record_login_failure(ip_key, "ip")
                                    record_login_failure(user_key, "user")
                                    st.error(result)
                    else:
                        st.warning("Completa todos los campos.")

        with tab2:
            with st.form("register_form"):
                col1, col2 = st.columns(2)
                with col1:
                    first_name = st.text_input("Nombre", placeholder="Ingresa tu nombre")
                with col2:
                    last_name = st.text_input("Apellidos", placeholder="Ingresa tus apellidos")

                email = st.text_input("Correo Electrónico", placeholder="ejemplo@correo.com")
                new_username = st.text_input("Nuevo Usuario", placeholder="Elige un nombre de usuario")
                new_password = st.text_input("Nueva Contraseña", type="password")
                confirm_password = st.text_input("Confirmar Contraseña", type="password")

                reg_submitted = st.form_submit_button("Crear Cuenta Premium", use_container_width=True)
                if reg_submitted:
                    if not all([first_name, last_name, email, new_username, new_password, confirm_password]):
                        st.error("Todos los campos son obligatorios.")
                    elif new_password != confirm_password:
                        st.error("Las contraseñas no coinciden.")
                    elif not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
                        st.error("Por favor, introduce un correo electrónico válido.")
                    else:
                        success, result = register_user_fn(first_name, last_name, email, new_username, new_password)
                        if success:
                            user_id, token = result
                            from src.services.email_service import send_verification_email

                            send_verification_email(email, first_name, token)
                            st.success(
                                f"¡Bienvenido/a {first_name}! Revisa tu bandeja de entrada (y Spam) para activar tu cuenta Premium."
                            )
                        else:
                            st.error(result)

        with tab3:
            with st.form("forgot_password_form"):
                rec_email = st.text_input("Correo Electrónico registrado")
                if st.form_submit_button("Enviar enlace de recuperación", use_container_width=True):
                    if rec_email:
                        from src.database.database import generate_password_reset_token
                        from src.services.email_service import send_password_reset_email

                        success, f_name, r_token = generate_password_reset_token(rec_email)
                        if success:
                            send_password_reset_email(rec_email, f_name, r_token)
                        st.success("Si el correo está registrado, recibirás un enlace de recuperación pronto.")
                    else:
                        st.warning("Por favor, introduce tu correo electrónico.")

    st.stop()
