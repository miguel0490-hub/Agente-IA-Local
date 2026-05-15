"""Onboarding wizard for provider API keys."""

from __future__ import annotations

import streamlit as st

from src.core.i18n import t


def render_onboarding_gate(update_api_keys_fn) -> None:
    """Renders onboarding steps and persists provider configuration."""
    if st.session_state.onboarding_done:
        return

    col_left, central_col, col_right = st.columns([1, 2, 1])
    with central_col:
        st.markdown(f"<h2 style='text-align: center; color: #00F2FE;'>{t('onboarding_title')}</h2>", unsafe_allow_html=True)

        step = st.session_state.onboarding_step

        if step < 6:
            st.progress(step / 6.0)
            st.caption(t("onboarding_step_of", step=step + 1))
            if st.button(t("onboarding_skip_all"), key="skip_all_onboarding", use_container_width=True):
                st.session_state.onboarding_step = 6
                st.rerun()

        if step == 0:
            st.markdown(t("onboarding_step1_title"))
            st.markdown(t("onboarding_step1_desc"))
            st.caption(t("onboarding_step1_caption"))
            key = st.text_input(t("onboarding_api_gemini"), type="password", key="gemini_input")
            c1, c2 = st.columns(2)
            with c1:
                if st.button(t("onboarding_save_next"), key="gemini_save", use_container_width=True):
                    st.session_state.temp_keys["GEMINI_API_KEY"] = key
                    st.session_state.onboarding_step += 1
                    st.rerun()
            with c2:
                if st.button(t("onboarding_skip_this"), key="gemini_skip", use_container_width=True):
                    st.session_state.temp_keys["GEMINI_API_KEY"] = ""
                    st.toast(t("onboarding_toast_gemini_skip"), icon="⚠️")
                    st.session_state.onboarding_step += 1
                    st.rerun()

        elif step == 1:
            st.markdown(t("onboarding_step2_title"))
            st.markdown(t("onboarding_step2_desc"))
            st.caption(t("onboarding_step2_caption"))
            key = st.text_input(t("onboarding_api_groq"), type="password", key="groq_input")
            c1, c2 = st.columns(2)
            with c1:
                if st.button(t("onboarding_save_next"), key="groq_save", use_container_width=True):
                    st.session_state.temp_keys["GROQ_API_KEY"] = key
                    st.session_state.onboarding_step += 1
                    st.rerun()
            with c2:
                if st.button(t("onboarding_skip_this"), key="groq_skip", use_container_width=True):
                    st.session_state.temp_keys["GROQ_API_KEY"] = ""
                    st.toast(t("onboarding_toast_groq_skip"), icon="⚠️")
                    st.session_state.onboarding_step += 1
                    st.rerun()

        elif step == 2:
            st.markdown(t("onboarding_step3_title"))
            st.markdown(t("onboarding_step3_desc"))
            st.caption(t("onboarding_step3_caption"))
            key = st.text_input(t("onboarding_api_openrouter"), type="password", key="or_input")
            c1, c2 = st.columns(2)
            with c1:
                if st.button(t("onboarding_save_next"), key="or_save", use_container_width=True):
                    st.session_state.temp_keys["OPENROUTER_API_KEY"] = key
                    st.session_state.onboarding_step += 1
                    st.rerun()
            with c2:
                if st.button(t("onboarding_skip_this"), key="or_skip", use_container_width=True):
                    st.session_state.temp_keys["OPENROUTER_API_KEY"] = ""
                    st.toast(t("onboarding_toast_or_skip"), icon="⚠️")
                    st.session_state.onboarding_step += 1
                    st.rerun()

        elif step == 3:
            st.markdown(t("onboarding_step4_title"))
            st.markdown(t("onboarding_step4_desc"))
            st.caption(t("onboarding_step4_caption"))
            key = st.text_input(t("onboarding_api_openai"), type="password", key="oai_input")
            c1, c2 = st.columns(2)
            with c1:
                if st.button(t("onboarding_save_next"), key="oai_save", use_container_width=True):
                    st.session_state.temp_keys["OPENAI_API_KEY"] = key
                    st.session_state.onboarding_step += 1
                    st.rerun()
            with c2:
                if st.button(t("onboarding_skip_this"), key="oai_skip", use_container_width=True):
                    st.session_state.temp_keys["OPENAI_API_KEY"] = ""
                    st.toast(t("onboarding_toast_oai_skip"), icon="⚠️")
                    st.session_state.onboarding_step += 1
                    st.rerun()

        elif step == 4:
            st.markdown(t("onboarding_step5_title"))
            st.markdown(t("onboarding_step5_desc"))
            st.caption(t("onboarding_step5_caption"))
            key = st.text_input(t("onboarding_api_stability"), type="password", key="stab_input")
            c1, c2 = st.columns(2)
            with c1:
                if st.button(t("onboarding_save_next"), key="stab_save", use_container_width=True):
                    st.session_state.temp_keys["STABILITY_API_KEY"] = key
                    st.session_state.onboarding_step += 1
                    st.rerun()
            with c2:
                if st.button(t("onboarding_skip"), key="stab_skip", use_container_width=True):
                    st.session_state.temp_keys["STABILITY_API_KEY"] = ""
                    st.toast(t("onboarding_toast_stab_skip"), icon="⚠️")
                    st.session_state.onboarding_step += 1
                    st.rerun()

        elif step == 5:
            st.markdown(t("onboarding_step6_title"))
            st.markdown(t("onboarding_step6_desc"))

            if st.session_state.temp_custom_models:
                st.markdown(t("onboarding_models_registered"))
                for cm in st.session_state.temp_custom_models:
                    st.success(
                        t(
                            "onboarding_model_registered_line",
                            name=cm["name"],
                            model_id=cm["model_id"],
                            base_url=cm["base_url"],
                        )
                    )
                st.divider()

            with st.form("custom_model_form", clear_on_submit=True):
                cm_name = st.text_input(t("onboarding_menu_name"), placeholder=t("onboarding_menu_name_placeholder"), key="cm_name_input")
                cm_url = st.text_input(t("onboarding_base_url"), placeholder=t("onboarding_base_url_placeholder"), key="cm_url_input")
                cm_key = st.text_input(t("onboarding_api_key"), type="password", key="cm_key_input")
                cm_model = st.text_input(t("onboarding_model_id"), placeholder=t("onboarding_model_id_placeholder"), key="cm_model_input")
                if st.form_submit_button(t("onboarding_save_model"), use_container_width=True):
                    if cm_name and cm_url and cm_key and cm_model:
                        from src.security.url_validator import validate_url
                        url_check = validate_url(cm_url.strip(), context="onboarding_custom_model")
                        if not url_check.safe:
                            st.error(t("onboarding_url_blocked", reason=url_check.reason))
                        else:
                            st.session_state.temp_custom_models.append(
                                {
                                    "name": cm_name.strip(),
                                    "base_url": cm_url.strip(),
                                    "api_key": cm_key.strip(),
                                    "model_id": cm_model.strip(),
                                }
                            )
                            st.toast(t("onboarding_model_saved", name=cm_name), icon="⚙️")
                            st.rerun()
                    else:
                        st.warning(t("onboarding_fill_all"))

            if st.button(t("onboarding_finish"), key="finish_onboarding", use_container_width=True):
                st.session_state.temp_keys["CUSTOM_MODELS"] = st.session_state.temp_custom_models
                st.session_state.onboarding_step += 1
                st.rerun()

        elif step == 6:
            st.markdown(t("onboarding_complete_title"))
            st.markdown(t("onboarding_complete_guide"))
            if st.button(t("onboarding_start_button"), key="start_app", use_container_width=True):
                final_keys = {k: v for k, v in st.session_state.temp_keys.items() if v}
                update_api_keys_fn(st.session_state.user_id, final_keys)
                st.session_state.api_keys = final_keys
                st.session_state.onboarding_done = True
                st.rerun()

    st.stop()
