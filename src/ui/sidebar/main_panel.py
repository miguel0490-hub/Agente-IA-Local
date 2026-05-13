"""Primary operation sidebar panel (role, engine, uploads, multimedia, clear actions)."""

from __future__ import annotations

import streamlit as st
from src.agents.capabilities import CAPABILITY_PROFILES
from src.core.security import check_scoped_rate_limit
from src.services.file_validator import get_upload_policy_summary
from src.core.i18n import t
from src.ui.sidebar.engine_options import motor_disponibles_labels


def _normalize_role_selector_value(raw: str | None, keys: list[str]) -> None:
    """Migra valores antiguos (nombre visible en español) a claves internas de rol."""
    if not keys:
        return
    if raw in keys:
        return
    for rk, prof in CAPABILITY_PROFILES.items():
        if prof.display_name == raw:
            st.session_state.selector_rol = rk
            return
        if raw and (raw in prof.display_name or prof.display_name in raw):
            st.session_state.selector_rol = rk
            return
    st.session_state.selector_rol = keys[0]


def render_main_sidebar_panel(
    get_roles_fn,
    cambiar_rol_fn,
    secure_upload_check_fn,
    render_multimedia_sidebar_tools_fn,
    panel_conversor_fn,
    get_groq_whisper_provider_fn,
    get_openai_tts_provider_fn,
    get_edge_tts_provider_fn,
    guardar_memoria_fn,
    limpiar_memoria_fn,
    delete_chat_fn,
) -> tuple[str, object, str]:
    """Renders main sidebar controls and returns selected engine, attachment and system prompt."""
    with st.sidebar:
        st.header(t("agent_role"))
        roles_map = get_roles_fn()
        role_keys = list(roles_map.keys())
        _normalize_role_selector_value(st.session_state.get("selector_rol"), role_keys)
        rol_seleccionado = st.selectbox(
            t("operation_mode"),
            role_keys,
            format_func=lambda k: t(f"role_display_{k}"),
            key="selector_rol",
            on_change=cambiar_rol_fn,
        )
        st.session_state.active_role = rol_seleccionado
        rol_config = roles_map[rol_seleccionado]
        system_instruction_activo = rol_config["prompt"]

        if rol_seleccionado == "app_builder":
            st.info(t("role_builder"))
        elif rol_seleccionado == "ui_designer":
            st.info(t("role_uiux"))
        elif rol_seleccionado == "multimedia_agent":
            st.info(t("role_multimedia"))
        elif rol_seleccionado == "security_engineer":
            st.info(t("role_security"))
        elif rol_seleccionado == "devops_engineer":
            st.info(t("role_devops"))
        elif rol_seleccionado == "research_agent":
            st.info(t("role_research"))
        else:
            st.caption(t("role_free_engine"))

        st.divider()

        st.markdown(t("engine_active"))
        motores_disponibles = motor_disponibles_labels(st.session_state.api_keys)
        idx = int(st.session_state.motor_activo_idx)
        if idx < 0 or idx >= len(motores_disponibles):
            idx = 0
            st.session_state.motor_activo_idx = 0
        motor = st.selectbox(
            t("engine_selector"),
            motores_disponibles,
            index=idx,
            key="motor_manual_selector",
        )
        if motor in motores_disponibles:
            st.session_state.motor_activo_idx = motores_disponibles.index(motor)

        st.divider()

        st.markdown(t("attach_file"))
        archivo = st.file_uploader(
            t("attach_label"),
            help=t("attach_help"),
            label_visibility="collapsed",
        )
        st.caption(get_upload_policy_summary())
        if archivo:
            if not check_scoped_rate_limit(str(st.session_state.user_id), scope="uploads"):
                st.error(t("upload_rate_limit"))
                archivo = None
            else:
                check = secure_upload_check_fn(archivo.name, archivo.getvalue())
                if not check.ok:
                    st.error(t("upload_blocked", reason=check.reason))
                    archivo = None

        st.divider()

        render_multimedia_sidebar_tools_fn(
            panel_conversor_fn=panel_conversor_fn,
            secure_upload_check_fn=secure_upload_check_fn,
            get_groq_whisper_provider_fn=get_groq_whisper_provider_fn,
            get_openai_tts_provider_fn=get_openai_tts_provider_fn,
            get_edge_tts_provider_fn=get_edge_tts_provider_fn,
            guardar_memoria_fn=guardar_memoria_fn,
        )

        st.divider()

        st.markdown('<div class="danger-btn">', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button(t("clear_messages"), use_container_width=True, key="btn_borrar_memoria"):
                limpiar_memoria_fn(st.session_state.chat_id)
                st.session_state.messages = []
                st.session_state.last_motor_selected = None
                st.session_state.form_clear_counter += 1
                st.rerun()
        with c2:
            if not st.session_state.get("confirm_delete_chat"):
                if st.button(t("delete_chat"), use_container_width=True, key="btn_eliminar_chat"):
                    st.session_state.confirm_delete_chat = True
                    st.rerun()
            else:
                st.warning(t("delete_confirm"))
                cd1, cd2 = st.columns(2)
                with cd1:
                    if st.button(t("confirm_button"), use_container_width=True, key="btn_confirmar_eliminar"):
                        delete_chat_fn(st.session_state.chat_id)
                        st.session_state.chat_id = None
                        st.session_state.messages = []
                        st.session_state.form_clear_counter += 1
                        st.session_state.confirm_delete_chat = False
                        st.rerun()
                with cd2:
                    if st.button(t("cancel_button"), use_container_width=True, key="btn_cancelar_eliminar"):
                        st.session_state.confirm_delete_chat = False
                        st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    return motor, archivo, system_instruction_activo
