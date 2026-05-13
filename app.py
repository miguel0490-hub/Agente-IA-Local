"""
SuperAgente IA Pro — aplicación Streamlit (entrada principal).

Orquesta autenticación, estado de sesión, sidebar, chat y herramientas multimedia.
La lógica de negocio pesada vive en `src/`; este módulo solo compone la UI y delega.
"""

import os

import streamlit as st

from src.core.i18n import set_language, t
from src.core.logger import get_logger

_logger = get_logger(__name__)

if "app_language" in st.session_state:
    set_language(st.session_state.app_language)

st.set_page_config(page_title=t("app_title"), page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

if not os.getenv("APP_URL"):
    os.environ["STREAMLIT_SERVER_PORT"] = str(st.get_option("server.port"))

from src.core.observability import init_observability
init_observability()

from src.database.database import (
    register_user,
    verify_login,
    update_api_keys,
    get_user_api_keys,
    update_remember_token,
    clear_remember_token,
    verify_remember_token,
    verify_user_token,
    update_password_with_token,
)
from src.core.config import ESTILOS_CSS
from src.ui.auth.auth_gate import render_auth_gate
from src.ui.auth.query_params_gate import handle_auth_query_params
from src.core.session_manager import init_cookie_manager, check_idle_timeout, try_auto_login

# --- INICIALIZACIÓN (DB + sesión + GC + directorios) ---
from src.core.bootstrap import bootstrap_app
bootstrap_app()

# --- SESIÓN: cookie manager, idle timeout, auto-login ---
cookie_manager = init_cookie_manager()
check_idle_timeout(cookie_manager, clear_remember_token_fn=clear_remember_token)

# --- ESTILOS ---
st.markdown(ESTILOS_CSS, unsafe_allow_html=True)

from src.ui.pwa import inject_pwa_meta
inject_pwa_meta()

# --- AUTO-LOGIN POR COOKIE (Remember Me) ---
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

# --- LOGIN Y REGISTRO ---
render_auth_gate(
    cookie_manager=cookie_manager,
    verify_login_fn=verify_login,
    get_user_api_keys_fn=get_user_api_keys,
    update_remember_token_fn=update_remember_token,
    clear_remember_token_fn=clear_remember_token,
    register_user_fn=register_user,
)

# --- IMPORTS DIFERIDOS (solo se cargan tras autenticación exitosa) ---
from src.database.database import (
    create_chat,
    get_user_chats,
    delete_chat,
    get_user_profile,
    update_chat_title as update_chat_title_db,
    search_chat_messages,
    is_user_admin,
)
from src.services.converter_service import run_conversion
from src.services.memory_service import cargar_memoria, guardar_memoria, limpiar_memoria
from src.core.config import CARPETA_IMAGENES, PROMPT_TECH_LEAD, PROMPT_APP_BUILDER, PROMPT_UI_DESIGNER
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
from src.ui.chat.composer_hub import render_chat_composer_hub
from src.ui.chat.runtime import handle_chat_interaction
from src.ui.chat.provider_greetings import maybe_inject_provider_greeting
from src.ui.sidebar.mobile_behavior import apply_mobile_sidebar_autoclose, apply_mobile_sidebar_default_closed
from src.ui.dialogs import create_dialogs
from src.services.provider_factory import (
    get_gemini_provider,
    get_groq_whisper_provider,
    get_openai_tts_provider,
    get_edge_tts_provider,
)

# --- ONBOARDING DE API KEYS ---
render_onboarding_gate(update_api_keys_fn=update_api_keys)

# --- DIÁLOGOS Y ROLES ---
dialogs = create_dialogs(
    update_api_keys_fn=update_api_keys,
    carpeta_imagenes=CARPETA_IMAGENES,
    secure_upload_check_fn=secure_upload_check,
    run_conversion_fn=run_conversion,
    guardar_memoria_fn=guardar_memoria,
    prompt_tech_lead=PROMPT_TECH_LEAD,
    prompt_app_builder=PROMPT_APP_BUILDER,
    prompt_ui_designer=PROMPT_UI_DESIGNER,
)

# --- SIDEBAR ---
with st.sidebar:
    render_sidebar_profile(
        get_user_profile_fn=get_user_profile,
        cookie_manager=cookie_manager,
        clear_remember_token_fn=clear_remember_token,
        is_admin=is_user_admin(st.session_state.user_id),
        panel_admin_fn=dialogs.panel_admin,
        panel_contacto_fn=dialogs.panel_contacto,
        panel_ajustes_fn=dialogs.panel_ajustes,
    )

    render_chat_management(
        create_chat_fn=create_chat,
        get_user_chats_fn=get_user_chats,
        cargar_memoria_fn=cargar_memoria,
        search_chat_messages_fn=search_chat_messages,
        update_chat_title_fn=update_chat_title_db,
    )

apply_mobile_sidebar_autoclose()
apply_mobile_sidebar_default_closed()

# --- INTERFAZ PRINCIPAL ---
render_main_header()

motor, system_instruction_activo = render_main_sidebar_panel(
    get_roles_fn=dialogs.get_roles,
    cambiar_rol_fn=dialogs.cambiar_rol,
    limpiar_memoria_fn=limpiar_memoria,
    delete_chat_fn=delete_chat,
)

maybe_inject_provider_greeting(motor, guardar_memoria)

render_chat_messages(st.session_state.messages, render_download_button)

render_chat_composer_hub(
    secure_upload_check_fn=secure_upload_check,
    panel_conversor_fn=dialogs.panel_conversor,
    get_groq_whisper_provider_fn=get_groq_whisper_provider,
    get_openai_tts_provider_fn=get_openai_tts_provider,
    get_edge_tts_provider_fn=get_edge_tts_provider,
    guardar_memoria_fn=guardar_memoria,
)

handle_chat_interaction(
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
    get_user_chats_fn=get_user_chats,
    update_chat_title_fn=update_chat_title_db,
)
