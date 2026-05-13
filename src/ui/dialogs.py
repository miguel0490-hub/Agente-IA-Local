"""Streamlit dialog definitions and role shims for app.py."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import streamlit as st

from src.core.i18n import t
from src.ui.settings.control_center import render_control_center_dialog
from src.ui.admin.admin_panel import render_admin_panel
from src.ui.contact.contact_form import render_contact_form
from src.ui.multimedia.converter_dialog import render_converter_dialog
from src.ui.sidebar.roles import get_roles as get_ui_roles, apply_role_change


@dataclass
class AppDialogs:
    """Container for all dialog functions and role helpers used by the main app."""
    panel_ajustes: Callable
    panel_admin: Callable
    panel_contacto: Callable
    panel_conversor: Callable
    get_roles: Callable
    cambiar_rol: Callable


def create_dialogs(
    *,
    update_api_keys_fn,
    carpeta_imagenes: str,
    secure_upload_check_fn,
    run_conversion_fn,
    guardar_memoria_fn,
    prompt_tech_lead: str,
    prompt_app_builder: str,
    prompt_ui_designer: str,
) -> AppDialogs:
    """Factory that wires dependencies and returns all dialog/role callables."""

    @st.dialog(t("dialog_settings"))
    def panel_ajustes():
        render_control_center_dialog(update_api_keys_fn=update_api_keys_fn)

    @st.dialog(t("dialog_admin"), width="large")
    def panel_admin():
        render_admin_panel()

    @st.dialog(t("dialog_contact"))
    def panel_contacto():
        render_contact_form()

    @st.dialog(t("dialog_converter"))
    def panel_conversor():
        render_converter_dialog(carpeta_imagenes, secure_upload_check_fn, run_conversion_fn, guardar_memoria_fn)

    def get_roles():
        from src.core.i18n import get_language

        return get_ui_roles(
            prompt_tech_lead,
            prompt_app_builder,
            prompt_ui_designer,
            get_language(),
        )

    def cambiar_rol():
        apply_role_change(guardar_memoria_fn)

    return AppDialogs(
        panel_ajustes=panel_ajustes,
        panel_admin=panel_admin,
        panel_contacto=panel_contacto,
        panel_conversor=panel_conversor,
        get_roles=get_roles,
        cambiar_rol=cambiar_rol,
    )
