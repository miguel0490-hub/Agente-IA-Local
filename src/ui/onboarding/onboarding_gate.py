"""Onboarding wizard for provider API keys."""

from __future__ import annotations

import streamlit as st


def render_onboarding_gate(update_api_keys_fn) -> None:
    """Renders onboarding steps and persists provider configuration."""
    if st.session_state.onboarding_done:
        return

    col_left, central_col, col_right = st.columns([1, 2, 1])
    with central_col:
        st.markdown("<h2 style='text-align: center; color: #00F2FE;'>Configuración de Proveedores</h2>", unsafe_allow_html=True)

        step = st.session_state.onboarding_step

        if step < 6:
            st.progress(step / 6.0)
            st.caption(f"Paso {step + 1} de 6")

        if step == 0:
            st.markdown("### Paso 1: Configurar Gemini")
            st.markdown("Motor principal para razonamiento, visión y agentes complejos. [Obtener mi API Key aquí](https://aistudio.google.com/app/apikey)")
            key = st.text_input("Gemini API Key", type="password", key="gemini_input")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Guardar y Siguiente", type="primary", key="gemini_save", use_container_width=True):
                    st.session_state.temp_keys["GEMINI_API_KEY"] = key
                    st.session_state.onboarding_step += 1
                    st.rerun()
            with c2:
                if st.button("Omitir esta IA", type="secondary", key="gemini_skip", use_container_width=True):
                    st.session_state.temp_keys["GEMINI_API_KEY"] = ""
                    st.toast("Has omitido Gemini. Las funciones de agente y visión estarán desactivadas.", icon="⚠️")
                    st.session_state.onboarding_step += 1
                    st.rerun()

        elif step == 1:
            st.markdown("### Paso 2: Configurar Groq")
            st.markdown("Motor ultrarrápido para transcripción STT (Whisper) y Llama 3. [Obtener mi API Key aquí](https://console.groq.com/keys)")
            key = st.text_input("Groq API Key", type="password", key="groq_input")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Guardar y Siguiente", type="primary", key="groq_save", use_container_width=True):
                    st.session_state.temp_keys["GROQ_API_KEY"] = key
                    st.session_state.onboarding_step += 1
                    st.rerun()
            with c2:
                if st.button("Omitir esta IA", type="secondary", key="groq_skip", use_container_width=True):
                    st.session_state.temp_keys["GROQ_API_KEY"] = ""
                    st.toast("Has omitido Groq. Transcripción y Llama 3 no estarán disponibles.", icon="⚠️")
                    st.session_state.onboarding_step += 1
                    st.rerun()

        elif step == 2:
            st.markdown("### Paso 3: Configurar OpenRouter")
            st.markdown("Acceso a múltiples modelos potentes (Claude, Mistral, etc). [Obtener mi API Key aquí](https://openrouter.ai/keys)")
            key = st.text_input("OpenRouter API Key", type="password", key="or_input")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Guardar y Siguiente", type="primary", key="or_save", use_container_width=True):
                    st.session_state.temp_keys["OPENROUTER_API_KEY"] = key
                    st.session_state.onboarding_step += 1
                    st.rerun()
            with c2:
                if st.button("Omitir esta IA", type="secondary", key="or_skip", use_container_width=True):
                    st.session_state.temp_keys["OPENROUTER_API_KEY"] = ""
                    st.toast("Has omitido OpenRouter. Los modelos de terceros no estarán disponibles.", icon="⚠️")
                    st.session_state.onboarding_step += 1
                    st.rerun()

        elif step == 3:
            st.markdown("### Paso 4: Configurar OpenAI")
            st.markdown("Necesario para generación de voz (TTS) y DALL-E 3. [Obtener mi API Key aquí](https://platform.openai.com/api-keys)")
            key = st.text_input("OpenAI API Key", type="password", key="oai_input")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Guardar y Siguiente", type="primary", key="oai_save", use_container_width=True):
                    st.session_state.temp_keys["OPENAI_API_KEY"] = key
                    st.session_state.onboarding_step += 1
                    st.rerun()
            with c2:
                if st.button("Omitir esta IA", type="secondary", key="oai_skip", use_container_width=True):
                    st.session_state.temp_keys["OPENAI_API_KEY"] = ""
                    st.toast("Has omitido OpenAI. Generación de voz y DALL-E 3 estarán inactivos.", icon="⚠️")
                    st.session_state.onboarding_step += 1
                    st.rerun()

        elif step == 4:
            st.markdown("### Paso 5: Configurar Stability AI")
            st.markdown("Generación de imágenes de alta resolución (SD3). [Obtener mi API Key aquí](https://platform.stability.ai/account/keys)")
            key = st.text_input("Stability AI API Key", type="password", key="stab_input")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Guardar y Siguiente", type="primary", key="stab_save", use_container_width=True):
                    st.session_state.temp_keys["STABILITY_API_KEY"] = key
                    st.session_state.onboarding_step += 1
                    st.rerun()
            with c2:
                if st.button("Omitir", type="secondary", key="stab_skip", use_container_width=True):
                    st.session_state.temp_keys["STABILITY_API_KEY"] = ""
                    st.toast("Has omitido Stability AI. Generación SD3 inactiva.", icon="⚠️")
                    st.session_state.onboarding_step += 1
                    st.rerun()

        elif step == 5:
            st.markdown("### Paso 6: Añadir IA Personalizada (Opcional)")
            st.markdown(
                "Conecta cualquier IA con una API compatible con OpenAI — "
                "DeepSeek, Mistral, Together AI, LM Studio, vLLM, etc.\n\n"
                "Todos los modelos que añadas heredarán el System Prompt completo "
                "y podrán usar herramientas (crear archivos, buscar en web, ejecutar código)."
            )

            if st.session_state.temp_custom_models:
                st.markdown("**Modelos registrados en este onboarding:**")
                for cm in st.session_state.temp_custom_models:
                    st.success(f"✅ {cm['name']} — `{cm['model_id']}` en `{cm['base_url']}`")
                st.divider()

            with st.form("custom_model_form", clear_on_submit=True):
                cm_name = st.text_input("Nombre en el menú", placeholder="Ej: Mi DeepSeek Coder", key="cm_name_input")
                cm_url = st.text_input("URL Base del Endpoint", placeholder="Ej: https://api.deepseek.com/v1", key="cm_url_input")
                cm_key = st.text_input("API Key del proveedor", type="password", key="cm_key_input")
                cm_model = st.text_input("ID del Modelo", placeholder="Ej: deepseek-chat", key="cm_model_input")
                if st.form_submit_button("➕ Guardar este Modelo", use_container_width=True):
                    if cm_name and cm_url and cm_key and cm_model:
                        st.session_state.temp_custom_models.append(
                            {
                                "name": cm_name.strip(),
                                "base_url": cm_url.strip(),
                                "api_key": cm_key.strip(),
                                "model_id": cm_model.strip(),
                            }
                        )
                        st.toast(f"✅ '{cm_name}' guardado. Añade otro o finaliza.", icon="⚙️")
                        st.rerun()
                    else:
                        st.warning("⚠️ Completa todos los campos antes de guardar el modelo.")

            if st.button("✅ Finalizar Onboarding", type="primary", key="finish_onboarding", use_container_width=True):
                st.session_state.temp_keys["CUSTOM_MODELS"] = st.session_state.temp_custom_models
                st.session_state.onboarding_step += 1
                st.rerun()

        elif step == 6:
            final_keys = {k: v for k, v in st.session_state.temp_keys.items() if v}
            update_api_keys_fn(st.session_state.user_id, final_keys)
            st.session_state.api_keys = final_keys
            st.session_state.onboarding_done = True
            st.success("¡Onboarding completado! Tu entorno está listo.")
            st.rerun()

    st.stop()
