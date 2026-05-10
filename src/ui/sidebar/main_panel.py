"""Primary operation sidebar panel (role, engine, uploads, multimedia, clear actions)."""

from __future__ import annotations

import streamlit as st
from src.core.security import check_scoped_rate_limit
from src.services.file_validator import get_upload_policy_summary


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
        st.header("🎭 Rol del Agente")
        rol_seleccionado = st.selectbox(
            "Modo de operación:",
            list(get_roles_fn().keys()),
            key="selector_rol",
            on_change=cambiar_rol_fn,
        )
        rol_config = get_roles_fn()[rol_seleccionado]
        system_instruction_activo = rol_config["prompt"]
        motor_forzado = rol_config["motor_forzado"]

        if "App Builder" in rol_seleccionado:
            st.info("🏗️ Motor: **Groq** (Velocidad máx.) — Bloqueado para este rol.")
        elif "UI/UX" in rol_seleccionado:
            st.info("🎨 Motor: **Gemini Vision** (Multimodal) — Bloqueado para este rol.")
        else:
            st.caption("Motor libre — selecciona abajo.")

        st.divider()

        st.markdown("**⚙️ Motor Activo**")
        motores_disponibles = [
            "Groq Llama 3.3 (Lead Software Engineer / Creador)",
            "Gemini 2.5 Pro (Análisis Multimedia y Arte)",
            "OpenRouter (Modelos Gratuitos y de Pago)",
            "Groq Whisper (Oídos: Transcripción STT)",
            "OpenAI TTS (Voz: Text-to-Speech)",
            "Generador de Assets (Manos: Texto a Imagen)",
        ]
        for cm in st.session_state.api_keys.get("CUSTOM_MODELS", []):
            motores_disponibles.append(f"🤖 {cm['name']}")
        if motor_forzado:
            motor = motor_forzado
            st.selectbox("Cerebro Activo:", [motor_forzado], index=0, disabled=True, key="motor_manual_selector")
        else:
            motor = st.selectbox("Cerebro Activo:", motores_disponibles, index=st.session_state.motor_activo_idx, key="motor_manual_selector")

        st.divider()

        st.markdown("**📁 Adjuntar Archivo**")
        archivo = st.file_uploader(
            "Código, docs, imágenes, datos…",
            help="Formatos soportados: texto, código, PDF, Word, Excel, imágenes, JSON, YAML, logs y más.",
            label_visibility="collapsed",
        )
        st.caption(get_upload_policy_summary())
        if archivo:
            if not check_scoped_rate_limit(str(st.session_state.user_id), scope="uploads"):
                st.error("⏳ Has alcanzado el límite temporal de subidas. Espera un momento e inténtalo de nuevo.")
                archivo = None
            else:
                check = secure_upload_check_fn(archivo.name, archivo.getvalue())
                if not check.ok:
                    st.error(f"⛔ Upload bloqueado: {check.reason}")
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
            if st.button("🧹 Limpiar mensajes", use_container_width=True, key="btn_borrar_memoria"):
                limpiar_memoria_fn(st.session_state.chat_id)
                st.session_state.messages = []
                st.session_state.last_motor_selected = None
                st.session_state.form_clear_counter += 1
                st.rerun()
        with c2:
            if st.button("🗑️ Borrar este Chat", use_container_width=True, key="btn_eliminar_chat"):
                delete_chat_fn(st.session_state.chat_id)
                st.session_state.chat_id = None
                st.session_state.messages = []
                st.session_state.form_clear_counter += 1
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    return motor, archivo, system_instruction_activo
