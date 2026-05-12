"""Primary operation sidebar panel (role, engine, uploads, multimedia, clear actions)."""

from __future__ import annotations

import streamlit as st
from src.core.security import check_scoped_rate_limit
from src.services.file_validator import get_upload_policy_summary
from src.core.i18n import t


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
        rol_seleccionado = st.selectbox(
            t("operation_mode"),
            list(get_roles_fn().keys()),
            key="selector_rol",
            on_change=cambiar_rol_fn,
        )
        rol_config = get_roles_fn()[rol_seleccionado]
        system_instruction_activo = rol_config["prompt"]
        motor_forzado = rol_config["motor_forzado"]

        if "App Builder" in rol_seleccionado:
            st.info(t("role_builder"))
        elif "UI/UX" in rol_seleccionado:
            st.info(t("role_uiux"))
        elif "Multimedia" in rol_seleccionado:
            st.info(t("role_multimedia"))
        elif "Seguridad" in rol_seleccionado:
            st.caption(t("role_security"))
        elif "DevOps" in rol_seleccionado:
            st.caption(t("role_devops"))
        elif "Investigación" in rol_seleccionado:
            st.caption(t("role_research"))
        else:
            st.caption(t("role_free_engine"))

        st.divider()

        st.markdown(t("engine_active"))
        motores_disponibles = [
            t("engine_groq"),
            t("engine_gemini"),
            t("engine_openrouter"),
            t("engine_whisper"),
            t("engine_tts"),
            t("engine_image"),
        ]
        for cm in st.session_state.api_keys.get("CUSTOM_MODELS", []):
            motores_disponibles.append(f"🤖 {cm['name']}")
        if motor_forzado:
            motor = motor_forzado
            st.selectbox(t("engine_selector"), [motor_forzado], index=0, disabled=True, key="motor_manual_selector")
        else:
            motor = st.selectbox(t("engine_selector"), motores_disponibles, index=st.session_state.motor_activo_idx, key="motor_manual_selector")

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
