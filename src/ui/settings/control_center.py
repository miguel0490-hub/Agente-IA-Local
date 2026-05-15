"""Control center dialog content."""

from __future__ import annotations

import hashlib
from pathlib import Path

import streamlit as st

from src.core.i18n import get_language, t


def _load_control_center_guide() -> str:
    base = Path(__file__).resolve().parents[2] / "translations" / "guides"
    lang = get_language()
    for name in (f"control_center_guide_{lang}.md", "control_center_guide_en.md", "control_center_guide_es.md"):
        p = base / name
        if p.exists():
            return p.read_text(encoding="utf-8")
    return ""


def render_control_center_dialog(update_api_keys_fn) -> None:
    """Renders the control-center tabs (external models, keys, account)."""
    tab1, tab2, tab3 = st.tabs([t("settings_tab_external"), t("settings_tab_keys"), t("settings_tab_account")])

    with tab1:
        custom_models = st.session_state.api_keys.get("CUSTOM_MODELS", [])

        if custom_models:
            st.markdown(t("settings_connected_models"))
            for idx, cm in enumerate(custom_models):
                model_key = f"{cm.get('name', '')}|{cm.get('base_url', '')}|{cm.get('model_id', '')}"
                model_key_hash = hashlib.sha256(model_key.encode("utf-8")).hexdigest()[:12]
                with st.container(border=True):
                    col_info, col_del = st.columns([5, 1])
                    with col_info:
                        api_key_masked = f"{cm['api_key'][:4]}...{cm['api_key'][-4:]}" if len(cm["api_key"]) > 8 else "***"
                        st.markdown(f"**{cm['name']}**")
                        st.caption(f"🆔 `{cm['model_id']}` | 🔗 `{cm['base_url']}`")
                        st.caption(f"🔑 {api_key_masked}")
                    with col_del:
                        if st.button(
                            "🗑️",
                            key=f"del_custom_model_{idx}_{model_key_hash}",
                            help=t("settings_delete_model_help", name=cm["name"]),
                        ):
                            custom_models = [m for i, m in enumerate(custom_models) if i != idx]
                            updated_keys = {**st.session_state.api_keys, "CUSTOM_MODELS": custom_models}
                            update_api_keys_fn(st.session_state.user_id, updated_keys)
                            st.session_state.api_keys = updated_keys
                            st.rerun()
            st.divider()
        else:
            st.info(t("settings_no_custom_models"))

        with st.expander(t("settings_guide_title"), expanded=False):
            st.markdown(_load_control_center_guide())

        with st.form("custom_ai_form", clear_on_submit=True):
            st.markdown(t("settings_connect_new"))
            cm_name = st.text_input(t("settings_model_name"), placeholder=t("settings_model_name_placeholder"))
            cm_url = st.text_input(t("settings_base_url"), placeholder=t("settings_base_url_placeholder"))
            cm_key = st.text_input(t("settings_api_key"), type="password")
            cm_model = st.text_input(t("settings_model_id_label"), placeholder=t("settings_model_id_placeholder"))

            if st.form_submit_button(t("settings_connect_button"), use_container_width=True):
                if cm_name and cm_url and cm_key and cm_model:
                    from src.security.url_validator import validate_url
                    url_check = validate_url(cm_url.strip(), context="custom_model_save")
                    if not url_check.safe:
                        st.error(t("settings_url_blocked", reason=url_check.reason))
                    else:
                        new_model = {
                            "name": cm_name.strip(),
                            "base_url": cm_url.strip(),
                            "api_key": cm_key.strip(),
                            "model_id": cm_model.strip(),
                        }
                        updated_list = custom_models + [new_model]
                        updated_keys = {**st.session_state.api_keys, "CUSTOM_MODELS": updated_list}
                        update_api_keys_fn(st.session_state.user_id, updated_keys)
                        st.session_state.api_keys = updated_keys
                        st.success(t("settings_connected_success", name=cm_name))
                        st.rerun()
                else:
                    st.warning(t("settings_fill_all"))

    with tab2:
        st.markdown(t("settings_update_keys_info"))
        with st.form("base_keys_form"):
            keys = st.session_state.api_keys
            new_gemini = st.text_input(t("settings_key_gemini"), type="password", value=keys.get("GEMINI_API_KEY", ""))
            new_groq = st.text_input(t("settings_key_groq"), type="password", value=keys.get("GROQ_API_KEY", ""))
            new_or = st.text_input(t("settings_key_openrouter"), type="password", value=keys.get("OPENROUTER_API_KEY", ""))
            new_oai = st.text_input(t("settings_key_openai"), type="password", value=keys.get("OPENAI_API_KEY", ""))
            new_stab = st.text_input(t("settings_key_stability"), type="password", value=keys.get("STABILITY_API_KEY", ""))

            if st.form_submit_button(t("settings_save_changes"), use_container_width=True):
                updated_keys = {
                    **keys,
                    "GEMINI_API_KEY": new_gemini or keys.get("GEMINI_API_KEY", ""),
                    "GROQ_API_KEY": new_groq or keys.get("GROQ_API_KEY", ""),
                    "OPENROUTER_API_KEY": new_or or keys.get("OPENROUTER_API_KEY", ""),
                    "OPENAI_API_KEY": new_oai or keys.get("OPENAI_API_KEY", ""),
                    "STABILITY_API_KEY": new_stab or keys.get("STABILITY_API_KEY", ""),
                }
                update_api_keys_fn(st.session_state.user_id, updated_keys)
                st.session_state.api_keys = updated_keys
                st.success(t("settings_keys_updated"))
                st.rerun()

    with tab3:
        from src.database.database import get_user_profile, change_user_password

        perfil = get_user_profile(st.session_state.user_id)
        if perfil:
            st.markdown(f"{t('settings_name_label')} {perfil['first_name']} {perfil['last_name']}")
            st.markdown(f"{t('settings_username_label')} @{perfil['username']}")
            st.markdown(f"{t('settings_email_label')} {perfil['email']}")
            st.divider()

        st.markdown(t("settings_change_password"))
        with st.form("change_password_form"):
            old_pass = st.text_input(t("settings_current_password"), type="password")
            new_pass = st.text_input(t("settings_new_password"), type="password")
            confirm_pass = st.text_input(t("settings_confirm_new_password"), type="password")

            if st.form_submit_button(t("settings_update_password"), use_container_width=True):
                if not old_pass or not new_pass or not confirm_pass:
                    st.warning(t("settings_fill_all_password"))
                elif new_pass != confirm_pass:
                    st.error(t("settings_passwords_mismatch"))
                else:
                    success, msg = change_user_password(st.session_state.user_id, old_pass, new_pass)
                    if success:
                        st.success(f"✅ {t(msg)}")
                    else:
                        st.error(f"❌ {t(msg)}")
