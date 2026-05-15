"""Session-state bootstrap utilities."""

from __future__ import annotations

import time
import streamlit as st


def initialize_session_state() -> None:
    """Initializes required keys with safe defaults once per session."""
    defaults = {
        "user_id": None,
        "api_keys": {},
        "chat_id": None,
        "onboarding_done": False,
        "messages": [],
        "rol_activo": "tech_lead",
        "motor_activo_idx": 0,
        "selector_rol": "tech_lead",
        "onboarding_step": 0,
        "temp_keys": {},
        "auto_close_sidebar": False,
        "temp_custom_models": [],
        "show_settings": False,
        "show_contact": False,
        "form_clear_counter": 0,
        "security_events": [],
        "last_activity_ts": time.time(),
        "staged_attachments": [],
        "attachment_hub_uploader_inc": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
