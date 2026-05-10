"""Role selection and role-change side effects."""

from __future__ import annotations

import streamlit as st


@st.cache_data(show_spinner=False)
def get_roles(prompt_tech_lead: str, prompt_app_builder: str, prompt_ui_designer: str) -> dict:
    """Returns static role catalog for sidebar selector."""
    return {
        "🧠 Asistente General (Tech Lead)": {
            "prompt": prompt_tech_lead,
            "motor_forzado": None,
        },
        "🏗️ Arquitecto de Software (App Builder)": {
            "prompt": prompt_app_builder,
            "motor_forzado": "Groq Llama 3.3 (Lead Software Engineer / Creador)",
        },
        "🎨 Diseñador Frontend UI/UX (Vision)": {
            "prompt": prompt_ui_designer,
            "motor_forzado": "Gemini 2.5 Pro (Análisis Multimedia y Arte)",
        },
    }


def apply_role_change(guardar_memoria_fn) -> None:
    """Applies role switch effects and persists role event in chat memory."""
    nuevo_rol = st.session_state.selector_rol
    if nuevo_rol != st.session_state.rol_activo:
        st.session_state.messages = []
        st.session_state.messages.append({"role": "system", "content": f"El usuario ha cambiado el rol del agente a: {nuevo_rol}."})
        if "App Builder" in nuevo_rol:
            st.session_state.motor_activo_idx = 0
        elif "UI/UX" in nuevo_rol:
            st.session_state.motor_activo_idx = 1
        if st.session_state.chat_id:
            guardar_memoria_fn(st.session_state.chat_id, st.session_state.messages, st.session_state.api_keys)
        st.session_state.rol_activo = nuevo_rol
