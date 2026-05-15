"""
Composición de la UI Streamlit (fase pública y autenticada).

`app.py` solo delega aquí tras configurar página y bootstrap.
"""

from __future__ import annotations

import streamlit as st

from src.core.bootstrap import bootstrap_app
from src.core.i18n import set_language, t
from src.core.session_manager import check_idle_timeout, init_cookie_manager, try_auto_login
from src.database.database import (
    clear_remember_token,
    get_user_api_keys,
    register_user,
    update_password_with_token,
    update_remember_token,
    verify_login,
    verify_remember_token,
    verify_user_token,
)
from src.ui.auth.auth_gate import render_auth_gate
from src.ui.auth.query_params_gate import handle_auth_query_params
from src.ui.fragments import render_chat_workspace_fragment, render_sidebar_fragment
from src.ui.pwa import inject_pwa_meta
from src.ui.styles import inject_app_styles


def run_bootstrap_and_public_ui():
    """Inicialización, estilos, cookies y login. Hace st.stop() si no hay sesión. Devuelve cookie_manager."""
    if "app_language" in st.session_state:
        set_language(st.session_state.app_language)

    bootstrap_app()

    cookie_manager = init_cookie_manager()
    check_idle_timeout(cookie_manager, clear_remember_token_fn=clear_remember_token)

    inject_app_styles()
    inject_pwa_meta()

    try_auto_login(
        cookie_manager,
        verify_remember_token_fn=verify_remember_token,
        get_user_api_keys_fn=get_user_api_keys,
        update_remember_token_fn=update_remember_token,
    )

    handle_auth_query_params(
        verify_user_token_fn=verify_user_token,
        update_password_with_token_fn=update_password_with_token,
    )

    render_auth_gate(
        cookie_manager=cookie_manager,
        verify_login_fn=verify_login,
        get_user_api_keys_fn=get_user_api_keys,
        update_remember_token_fn=update_remember_token,
        clear_remember_token_fn=clear_remember_token,
        register_user_fn=register_user,
    )

    if not st.session_state.get("user_id"):
        st.stop()
    return cookie_manager


def run_authenticated_app(cookie_manager) -> None:
    """UI principal tras login."""
    from src.core.observability import init_observability
    from src.core.streamlit_cache import (
        cached_is_admin,
        cached_user_chats,
        cached_user_profile,
    )
    from src.database.database import (
        create_chat,
        delete_chat,
        get_user_chats,
        get_user_profile,
        is_user_admin,
        search_chat_messages,
        update_api_keys,
        update_chat_title as update_chat_title_db,
    )
    from src.services.converter_service import run_conversion
    from src.services.memory_service import cargar_memoria, guardar_memoria, limpiar_memoria
    from src.core.config import CARPETA_IMAGENES
    from src.core.system_prompts import PROMPT_APP_BUILDER, PROMPT_TECH_LEAD, PROMPT_UI_DESIGNER
    from src.core.intent_parser import parse_intent
    from src.core.ui_helpers import render_download_button
    from src.security.tool_guard import ToolGuard
    from src.services.upload_security import secure_upload_check
    from src.ui.sidebar.chat_management import render_chat_management
    from src.ui.sidebar.main_panel import render_main_sidebar_panel
    from src.ui.sidebar.profile import render_sidebar_profile
    from src.ui.onboarding.onboarding_gate import render_onboarding_gate
    from src.ui.components.chat_messages import render_chat_messages
    from src.ui.components.header import render_main_header
    from src.ui.chat.runtime import handle_chat_interaction
    from src.ui.sidebar.attachments import render_sidebar_attachment_uploader
    from src.ui.multimedia.sidebar_tools import render_multimedia_sidebar_tools
    from src.ui.chat.provider_greetings import maybe_inject_provider_greeting
    from src.ui.sidebar.mobile_behavior import apply_mobile_sidebar_autoclose, apply_mobile_sidebar_default_closed
    from src.ui.dialogs import create_dialogs
    from src.services.provider_factory import (
        get_gemini_provider,
        get_groq_whisper_provider,
        get_openai_tts_provider,
        get_edge_tts_provider,
    )

    init_observability()

    render_onboarding_gate(update_api_keys_fn=update_api_keys)

    if "_app_dialogs" not in st.session_state:
        st.session_state._app_dialogs = create_dialogs(
            update_api_keys_fn=update_api_keys,
            carpeta_imagenes=CARPETA_IMAGENES,
            secure_upload_check_fn=secure_upload_check,
            run_conversion_fn=run_conversion,
            guardar_memoria_fn=guardar_memoria,
            prompt_tech_lead=PROMPT_TECH_LEAD,
            prompt_app_builder=PROMPT_APP_BUILDER,
            prompt_ui_designer=PROMPT_UI_DESIGNER,
        )
    dialogs = st.session_state._app_dialogs

    def _get_user_chats_cached(uid: int):
        return cached_user_chats(uid, get_user_chats)

    def _get_user_profile_cached(uid: int):
        return cached_user_profile(uid, get_user_profile)

    def _render_sidebar() -> None:
        with st.sidebar:
            render_sidebar_profile(
                get_user_profile_fn=_get_user_profile_cached,
                cookie_manager=cookie_manager,
                clear_remember_token_fn=clear_remember_token,
                is_admin=cached_is_admin(st.session_state.user_id, is_user_admin),
                panel_admin_fn=dialogs.panel_admin,
                panel_contacto_fn=dialogs.panel_contacto,
                panel_ajustes_fn=dialogs.panel_ajustes,
            )
            render_multimedia_sidebar_tools(
                panel_conversor_fn=dialogs.panel_conversor,
                secure_upload_check_fn=secure_upload_check,
                get_groq_whisper_provider_fn=get_groq_whisper_provider,
                get_openai_tts_provider_fn=get_openai_tts_provider,
                get_edge_tts_provider_fn=get_edge_tts_provider,
                guardar_memoria_fn=guardar_memoria,
            )
            render_sidebar_attachment_uploader(secure_upload_check_fn=secure_upload_check)
            render_chat_management(
                create_chat_fn=create_chat,
                get_user_chats_fn=_get_user_chats_cached,
                cargar_memoria_fn=cargar_memoria,
                search_chat_messages_fn=search_chat_messages,
                update_chat_title_fn=update_chat_title_db,
            )

    render_sidebar_fragment(_render_sidebar)

    apply_mobile_sidebar_autoclose()
    apply_mobile_sidebar_default_closed()

    render_main_header()

    motor, system_instruction_activo = render_main_sidebar_panel(
        get_roles_fn=dialogs.get_roles,
        cambiar_rol_fn=dialogs.cambiar_rol,
        limpiar_memoria_fn=limpiar_memoria,
        delete_chat_fn=delete_chat,
    )

    maybe_inject_provider_greeting(motor, guardar_memoria)

    def _render_messages(msgs: list) -> None:
        render_chat_messages(msgs, render_download_button)

    render_chat_workspace_fragment(
        st.session_state.messages,
        _render_messages,
        handle_chat_interaction,
        motor=motor,
        archivos_adjuntos=None,
        system_instruction_activo=system_instruction_activo,
        parse_intent_fn=parse_intent,
        get_gemini_provider_fn=get_gemini_provider,
        panel_conversor_fn=dialogs.panel_conversor,
        render_download_button_fn=render_download_button,
        guardar_memoria_fn=guardar_memoria,
        tool_guard_cls=ToolGuard,
        carpeta_imagenes=CARPETA_IMAGENES,
        get_user_chats_fn=_get_user_chats_cached,
        update_chat_title_fn=update_chat_title_db,
    )
