"""Role selection and role-change side effects."""

from __future__ import annotations

import streamlit as st

# Orden del selector lateral (debe coincidir con CAPABILITY_PROFILES).
_ROLE_ORDER: tuple[str, ...] = (
    "tech_lead",
    "app_builder",
    "ui_designer",
    "security_engineer",
    "devops_engineer",
    "research_agent",
    "multimedia_agent",
)


def _fallback_prompt_for(
    role_key: str,
    prompt_tech_lead: str,
    prompt_app_builder: str,
    prompt_ui_designer: str,
) -> str:
    if role_key == "app_builder":
        return prompt_app_builder
    if role_key == "ui_designer":
        return prompt_ui_designer
    return prompt_tech_lead


@st.cache_data(show_spinner=False)
def get_roles(
    prompt_tech_lead: str,
    prompt_app_builder: str,
    prompt_ui_designer: str,
    language: str,
) -> dict:
    """Catálogo de roles: solo el prompt por modo de operación."""
    from src.agents.capabilities import CAPABILITY_PROFILES
    from src.agents.prompt_loader import load_role_prompt

    def _prompt_or_fallback(role_key_file: str, fallback: str) -> str:
        loaded = load_role_prompt(role_key_file)
        return loaded if loaded else fallback

    out: dict = {}
    for role_key in _ROLE_ORDER:
        profile = CAPABILITY_PROFILES[role_key]
        fb = _fallback_prompt_for(
            role_key, prompt_tech_lead, prompt_app_builder, prompt_ui_designer
        )
        prompt = _prompt_or_fallback(profile.prompt_profile, fb)
        out[role_key] = {"prompt": prompt}
    return out


def apply_role_change(guardar_memoria_fn) -> None:
    """Aplica efectos al cambiar de rol y persiste el evento en memoria del chat."""
    from src.core.i18n import t

    nuevo_rol = st.session_state.selector_rol
    if nuevo_rol != st.session_state.rol_activo:
        st.session_state.messages = []
        role_label = t(f"role_display_{nuevo_rol}")
        st.session_state.messages.append(
            {"role": "system", "content": t("role_change_system", role=role_label)}
        )
        from src.agents.capabilities import get_capability_profile
        from src.ui.sidebar.engine_options import (
            default_motor_index_for_preferred,
            motor_disponibles_labels,
        )

        profile = get_capability_profile(nuevo_rol)
        di = default_motor_index_for_preferred(profile.preferred_model)
        opts = motor_disponibles_labels(st.session_state.get("api_keys", {}))
        if di is not None and opts and 0 <= di < len(opts):
            st.session_state.motor_activo_idx = di
            st.session_state["motor_manual_selector"] = opts[di]

        if st.session_state.chat_id:
            guardar_memoria_fn(
                st.session_state.chat_id,
                st.session_state.messages,
                st.session_state.api_keys,
            )
        st.session_state.rol_activo = nuevo_rol
