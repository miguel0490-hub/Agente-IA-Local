"""
SuperAgente IA Pro — aplicación Streamlit (entrada principal).

Orquesta autenticación, estado de sesión, sidebar, chat y herramientas multimedia.
La lógica de negocio pesada vive en `src/`; este módulo solo compone la UI y delega.
"""

import datetime
import os
import time
import uuid

import streamlit as st

from src.core.logger import get_logger

_logger = get_logger(__name__)

st.set_page_config(page_title="SuperAgente IA Pro", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

# Publica el puerto actual para servicios que generan URLs externas (emails, callbacks).
# APP_URL tiene prioridad si está definido explícitamente para producción.
if not os.getenv("APP_URL"):
    os.environ["STREAMLIT_SERVER_PORT"] = str(st.get_option("server.port"))

from src.core.observability import init_observability
init_observability()

from src.database.database import (
    register_user,
    verify_login,
    update_api_keys,
    get_user_api_keys,
    create_chat,
    get_user_chats,
    delete_chat,
    update_remember_token,
    clear_remember_token,
    verify_remember_token,
    cleanup_expired_tokens,
    verify_user_token,
    update_password_with_token,
    get_user_profile,
    update_chat_title as update_chat_title_db,
    init_db,
    is_user_admin,
)
from src.services.converter_service import run_conversion
from src.services.memory_service import cargar_memoria, guardar_memoria, limpiar_memoria
from src.core.config import CARPETA_IMAGENES, PROMPT_TECH_LEAD, PROMPT_APP_BUILDER, PROMPT_UI_DESIGNER, ESTILOS_CSS
from src.core.session_state import initialize_session_state
from src.core.auth_cookies import set_auth_cookie
from src.core.intent_parser import parse_intent
from src.core.ui_helpers import render_download_button
import extra_streamlit_components as stx
from src.security.tool_guard import ToolGuard
from src.services.upload_security import secure_upload_check
from src.ui.sidebar.roles import get_roles as get_ui_roles, apply_role_change
from src.ui.sidebar.chat_management import render_chat_management
from src.ui.sidebar.main_panel import render_main_sidebar_panel
from src.ui.sidebar.profile import render_sidebar_profile
from src.ui.auth.auth_gate import render_auth_gate
from src.ui.auth.query_params_gate import handle_auth_query_params
from src.ui.onboarding.onboarding_gate import render_onboarding_gate
from src.ui.settings.control_center import render_control_center_dialog
from src.ui.admin.admin_panel import render_admin_panel
from src.ui.contact.contact_form import render_contact_form
from src.ui.multimedia.converter_dialog import render_converter_dialog
from src.ui.multimedia.sidebar_tools import render_multimedia_sidebar_tools
from src.ui.components.chat_messages import render_chat_messages
from src.ui.components.header import render_main_header
from src.ui.chat.runtime import handle_chat_interaction
from src.ui.chat.provider_greetings import maybe_inject_provider_greeting
from src.ui.sidebar.mobile_behavior import apply_mobile_sidebar_autoclose
from src.services.provider_factory import (
    get_gemini_provider,
    get_groq_whisper_provider,
    get_openai_tts_provider,
    get_edge_tts_provider,
)
# --- INICIALIZACIÓN DE DB Y GARBAGE COLLECTOR ---


@st.cache_resource(show_spinner=False)
def start_database():
    """Ejecuta la verificación de tablas de la DB solo 1 vez por ciclo de vida del servidor."""
    init_db()
    cleanup_expired_tokens()

start_database()

def run_garbage_collector():
    """Elimina archivos temporales generados hace más de 24 horas."""
    now = time.time()
    for directory in [CARPETA_IMAGENES, "data/temp"]:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                if os.path.isfile(filepath) and os.stat(filepath).st_mtime < now - 86400:
                    try:
                        os.remove(filepath)
                    except OSError as exc:
                        _logger.warning("No se pudo eliminar temporal %s: %s", filepath, exc)

if "gc_run" not in st.session_state:
    run_garbage_collector()
    st.session_state.gc_run = True

# CookieManager en session_state para evitar CachedWidgetWarning en Streamlit moderno.
if "cookie_manager" not in st.session_state:
    st.session_state.cookie_manager = stx.CookieManager(key="global_cookie_manager")
cookie_manager = st.session_state.cookie_manager

# --- INICIALIZACIÓN DE ESTADO ---
initialize_session_state()

# --- EXPIRACIÓN DE SESIÓN POR INACTIVIDAD ---
if st.session_state.user_id:
    idle_timeout_min = int((os.getenv("SESSION_IDLE_TIMEOUT_MINUTES") or "120").strip() or "120")
    idle_timeout_sec = max(5, idle_timeout_min) * 60
    now_ts = time.time()
    last_ts = float(st.session_state.get("last_activity_ts", now_ts))
    if now_ts - last_ts > idle_timeout_sec:
        cookie_manager.delete("auth_token")
        clear_remember_token(st.session_state.user_id)
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.warning("Tu sesión ha expirado por inactividad. Inicia sesión nuevamente.")
        st.rerun()
    st.session_state.last_activity_ts = now_ts

# --- ESTILOS ---
st.markdown(ESTILOS_CSS, unsafe_allow_html=True)

if not os.path.exists(CARPETA_IMAGENES):
    os.makedirs(CARPETA_IMAGENES)

# --- AUTO-LOGIN POR COOKIE (Remember Me) ---
# Se ejecuta antes del bloque de login para restaurar la sesión sin interacción del usuario.
if not st.session_state.user_id:
    cookies = cookie_manager.get_all()
    _auth_cookie = cookies.get("auth_token") if isinstance(cookies, dict) else cookie_manager.get("auth_token")
    if _auth_cookie:
        _remembered_user_id = verify_remember_token(_auth_cookie)
        if _remembered_user_id:
            st.session_state.user_id = _remembered_user_id
            _keys = get_user_api_keys(_remembered_user_id)
            st.session_state.api_keys = _keys
            if _keys:
                st.session_state.onboarding_done = True
            # Rotación de token persistente en cada restauración de sesión.
            _new_token = uuid.uuid4().hex
            remember_days = int((os.getenv("REMEMBER_ME_DAYS") or "7").strip() or "7")
            _expires = datetime.datetime.now() + datetime.timedelta(days=max(1, remember_days))
            update_remember_token(_remembered_user_id, _new_token, _expires)
            set_auth_cookie(cookie_manager, _new_token, _expires, key="refresh_auth_cookie")
            st.rerun()
        else:
            cookie_manager.delete("auth_token")  # Limpia token corrupto o expirado

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

# --- ONBOARDING DE API KEYS ---
render_onboarding_gate(update_api_keys_fn=update_api_keys)


# --- CENTRO DE CONTROL (Dialog Premium) ---
# DEBE definirse ANTES del bloque with st.sidebar: para evitar NameError.
@st.dialog("⚙️ Centro de Control")
def panel_ajustes():
    """
    Panel de ajustes post-onboarding: gestiona IAs personalizadas,
    claves base y cierre de sesión segura con limpieza de cookie.
    """
    render_control_center_dialog(update_api_keys_fn=update_api_keys)


@st.dialog("🛡️ Panel de Administración", width="large")
def panel_admin():
    render_admin_panel()


@st.dialog("📩 Contactar al Administrador")
def panel_contacto():
    render_contact_form()


# --- CONFIGURACIÓN DE CHATS EN SIDEBAR ---
with st.sidebar:
    render_sidebar_profile(
        get_user_profile_fn=get_user_profile,
        cookie_manager=cookie_manager,
        clear_remember_token_fn=clear_remember_token,
    )

    if is_user_admin(st.session_state.user_id):
        if st.button("🛡️ Panel de Administración", key="btn_admin", use_container_width=True):
            st.session_state.show_admin = True
            st.rerun()
        if st.session_state.get("show_admin"):
            st.session_state.show_admin = False
            panel_admin()
        st.divider()

    if st.button("📩 Contactar al Administrador", key="btn_contact", use_container_width=True):
        st.session_state.show_contact = True
        st.rerun()
    if st.session_state.get("show_contact"):
        st.session_state.show_contact = False
        panel_contacto()
    st.divider()

    render_chat_management(
        create_chat_fn=create_chat,
        get_user_chats_fn=get_user_chats,
        cargar_memoria_fn=cargar_memoria,
        panel_ajustes_fn=panel_ajustes,
    )


def get_roles():
    """Shim para catálogo de roles desacoplado en módulo UI."""
    return get_ui_roles(PROMPT_TECH_LEAD, PROMPT_APP_BUILDER, PROMPT_UI_DESIGNER)


def cambiar_rol():
    """Shim para cambio de rol desacoplado en módulo UI."""
    apply_role_change(guardar_memoria)

# --- PANEL DE CONVERSIÓN (DIALOG) ---


@st.dialog("🔄 Estudio de Conversión Universal")
def panel_conversor():
    """Renderiza el estudio de conversión y publica resultados directamente en el chat."""
    render_converter_dialog(CARPETA_IMAGENES, secure_upload_check, run_conversion, guardar_memoria)

apply_mobile_sidebar_autoclose()

# --- INTERFAZ PRINCIPAL ---
render_main_header()


motor, archivo, system_instruction_activo = render_main_sidebar_panel(
    get_roles_fn=get_roles,
    cambiar_rol_fn=cambiar_rol,
    secure_upload_check_fn=secure_upload_check,
    render_multimedia_sidebar_tools_fn=render_multimedia_sidebar_tools,
    panel_conversor_fn=panel_conversor,
    get_groq_whisper_provider_fn=get_groq_whisper_provider,
    get_openai_tts_provider_fn=get_openai_tts_provider,
    get_edge_tts_provider_fn=get_edge_tts_provider,
    guardar_memoria_fn=guardar_memoria,
    limpiar_memoria_fn=limpiar_memoria,
    delete_chat_fn=delete_chat,
)

maybe_inject_provider_greeting(motor, guardar_memoria)

render_chat_messages(st.session_state.messages, render_download_button)

handle_chat_interaction(
    motor=motor,
    archivo=archivo,
    system_instruction_activo=system_instruction_activo,
    parse_intent_fn=parse_intent,
    get_gemini_provider_fn=get_gemini_provider,
    panel_conversor_fn=panel_conversor,
    render_download_button_fn=render_download_button,
    guardar_memoria_fn=guardar_memoria,
    tool_guard_cls=ToolGuard,
    carpeta_imagenes=CARPETA_IMAGENES,
    get_user_chats_fn=get_user_chats,
    update_chat_title_fn=update_chat_title_db,
)
