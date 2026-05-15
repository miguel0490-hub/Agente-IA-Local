"""Authentication gate UI (login, register, password reset request)."""

from __future__ import annotations

import datetime
import os
import re
import time

import streamlit as st

from src.core.auth_cookies import set_auth_cookie
from src.core.logger import get_logger
from src.core.request_context import get_remote_address
from src.core.security import check_scoped_rate_limit
from src.core.security import get_login_backoff_seconds
from src.core.security import get_login_rate_limit_config
from src.core.security import record_login_failure
from src.core.security import reset_login_throttle_state
from src.core.i18n import t

_logger = get_logger(__name__)


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

    # Desbloqueo opcional: CLEAR_LOGIN_RATELIMIT=1 en .env (una vez por sesión de navegador).
    if (os.getenv("CLEAR_LOGIN_RATELIMIT") or "").strip().lower() in ("1", "true", "yes", "on"):
        if "_login_rl_cleared_env" not in st.session_state:
            reset_login_throttle_state()
            st.session_state._login_rl_cleared_env = True

    col_left, central_col, col_right = st.columns([1, 2, 1])
    with central_col:
        st.markdown(
            f"""
<div class="hero-header">
    <h1 class="hero-title">⚡ {t("app_title")}</h1>
    <p class="hero-subtitle">{t("header_subtitle")}</p>
</div>
""",
            unsafe_allow_html=True,
        )

        tab_login, tab_register, tab_forgot = st.tabs(
            [t("login"), t("register"), t("forgot_password")]
        )

        with tab_login:
            with st.form("login_form"):
                username = st.text_input(t("username"), placeholder=t("username_placeholder"), autocomplete="username")
                password = st.text_input(t("password"), type="password", autocomplete="current-password")
                remember_me = st.checkbox(t("remember_me"), value=False)
                submitted = st.form_submit_button(t("submit_login"), use_container_width=True)
                if submitted:
                    if username and password:
                        remote = get_remote_address()
                        user_key = f"user:{str(username).strip().lower()}"
                        user_limit, user_window = get_login_rate_limit_config("user")
                        # Streamlit local: sin IP real, los intentos se acumulan muy rápido en el cubo por usuario.
                        if remote == "unknown":
                            user_limit = max(user_limit, 250)
                            user_window = max(user_window, 900)
                        # Streamlit en local suele no exponer IP real → "unknown" compartía un
                        # solo cubo `ip:unknown` y se bloqueaba a todos en pocos intentos.
                        ip_key = f"ip:{remote}" if remote != "unknown" else None
                        user_limit, user_window = get_login_rate_limit_config("user")
                        if ip_key:
                            ip_limit, ip_window = get_login_rate_limit_config("ip")
                            ip_denied = not check_scoped_rate_limit(
                                ip_key, "login", limit=ip_limit, window_seconds=ip_window
                            )
                        else:
                            ip_denied = False
                        if ip_denied:
                            st.error(t("auth_too_many_ip"))
                        elif not check_scoped_rate_limit(
                            user_key, "login", limit=user_limit, window_seconds=user_window
                        ):
                            st.error(t("auth_too_many_user"))
                        else:
                            ip_wait = get_login_backoff_seconds(ip_key, "ip") if ip_key else 0
                            user_wait = get_login_backoff_seconds(user_key, "user")
                            wait_seconds = max(ip_wait, user_wait)
                            if wait_seconds > 0:
                                st.error(t("auth_backoff", wait_seconds=wait_seconds))
                            else:
                                try:
                                    with st.spinner(t("authenticating")):
                                        success, result = verify_login_fn(username, password)
                                    if success:
                                        from src.core.streamlit_cache import invalidate_sidebar_cache

                                        st.session_state.user_id = result
                                        st.session_state.pop("_app_dialogs", None)
                                        invalidate_sidebar_cache()
                                        keys = get_user_api_keys_fn(result)
                                        st.session_state.api_keys = keys
                                        if keys:
                                            st.session_state.onboarding_done = True
                                        if remember_me:
                                            import uuid

                                            _token = uuid.uuid4().hex
                                            remember_days = int((os.getenv("REMEMBER_ME_DAYS") or "7").strip() or "7")
                                            expires_date = datetime.datetime.now() + datetime.timedelta(
                                                days=max(1, remember_days)
                                            )
                                            update_remember_token_fn(result, _token, expires_date)
                                            try:
                                                set_auth_cookie(cookie_manager, _token, expires_date, key="set_auth_cookie")
                                            except Exception as exc:
                                                _logger.warning("No se pudo fijar cookie Remember Me: %s", exc)
                                        else:
                                            cookie_manager.delete("auth_token")
                                            clear_remember_token_fn(result)
                                        time.sleep(0.8)
                                        st.rerun()
                                    else:
                                        if ip_key:
                                            record_login_failure(ip_key, "ip")
                                        record_login_failure(user_key, "user")
                                        st.error(t(result))
                                except Exception:
                                    _logger.exception("Fallo no controlado en login")
                                    st.error(t("auth_login_exception"))
                    else:
                        st.warning(t("fill_all_fields"))

        with tab_register:
            with st.form("register_form"):
                first_name = st.text_input(t("first_name"), placeholder=t("first_name_placeholder"))
                last_name = st.text_input(t("last_name"), placeholder=t("last_name_placeholder"))
                email = st.text_input(t("email"), placeholder=t("email_placeholder"))
                new_username = st.text_input(t("new_username"), placeholder=t("new_username_placeholder"))
                new_password = st.text_input(t("new_password"), type="password")
                confirm_password = st.text_input(t("confirm_password"), type="password")

                reg_submitted = st.form_submit_button(t("create_account"), use_container_width=True)
                if reg_submitted:
                    if not all([first_name, last_name, email, new_username, new_password, confirm_password]):
                        st.error(t("all_fields_required"))
                    elif new_password != confirm_password:
                        st.error(t("passwords_mismatch"))
                    elif not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
                        st.error(t("invalid_email"))
                    else:
                        success, result = register_user_fn(first_name, last_name, email, new_username, new_password)
                        if success:
                            user_id, token = result
                            from src.services.email_service import send_verification_email

                            send_verification_email(email, first_name, token)
                            st.success(t("welcome_registered", name=first_name))
                        else:
                            st.error(t(result))

        with tab_forgot:
            with st.form("forgot_password_form"):
                rec_email = st.text_input(t("registered_email"))
                if st.form_submit_button(t("send_recovery"), use_container_width=True):
                    if rec_email:
                        from src.database.database import generate_password_reset_token
                        from src.services.email_service import send_password_reset_email

                        success, f_name, r_token = generate_password_reset_token(rec_email)
                        if success:
                            send_password_reset_email(rec_email, f_name, r_token)
                        st.success(t("recovery_sent"))
                    else:
                        st.warning(t("enter_email"))

    st.stop()
