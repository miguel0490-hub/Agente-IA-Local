"""Control center dialog content."""

from __future__ import annotations

import streamlit as st


def render_control_center_dialog(update_api_keys_fn) -> None:
    """Renders the control-center tabs (external models, keys, account)."""
    tab1, tab2, tab3 = st.tabs(["🤖 IAs Externas", "🔑 Claves Base", "👤 Cuenta"])

    with tab1:
        custom_models = st.session_state.api_keys.get("CUSTOM_MODELS", [])

        if custom_models:
            st.markdown("**Modelos conectados:**")
            for cm in custom_models:
                with st.container(border=True):
                    col_info, col_del = st.columns([5, 1])
                    with col_info:
                        api_key_masked = f"{cm['api_key'][:4]}...{cm['api_key'][-4:]}" if len(cm["api_key"]) > 8 else "***"
                        st.markdown(f"**{cm['name']}**")
                        st.caption(f"🆔 `{cm['model_id']}` | 🔗 `{cm['base_url']}`")
                        st.caption(f"🔑 {api_key_masked}")
                    with col_del:
                        if st.button("🗑️", key=f"del_{cm['name']}", help=f"Eliminar {cm['name']}"):
                            custom_models = [m for m in custom_models if m["name"] != cm["name"]]
                            updated_keys = {**st.session_state.api_keys, "CUSTOM_MODELS": custom_models}
                            update_api_keys_fn(st.session_state.user_id, updated_keys)
                            st.session_state.api_keys = updated_keys
                            st.rerun()
            st.divider()
        else:
            st.info("📡 No tienes ninguna IA personalizada conectada todavía.")

        with st.expander("📖 Guía Completa: Directorio de IAs y Túneles", expanded=False):
            st.markdown(
                """
            <div style="background: rgba(15,23,42,0.6); padding: 20px; border-radius: 12px; border: 1px solid #00E1D9; color: #CBD5E0; line-height: 1.5; font-family: sans-serif;">
                <h3 style="color: #00E1D9; margin-top: 0; margin-bottom: 10px; font-weight: 800; font-size: 18px;">📚 Directorio Universal de IAs</h3>
                <p style="font-size: 13px; margin-bottom: 20px;">Tu SuperAgente se conecta mediante el <b>estándar universal de OpenAI</b>. Puedes conectar literalmente cualquier modelo del mundo usando estas configuraciones:</p>
                <h4 style="color: #F8FAFC; margin-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px; font-size: 15px;">☁️ Proveedores Cloud (La Nube)</h4>
                <div style="background: rgba(0,0,0,0.3); padding: 12px; border-radius: 8px; margin-bottom: 12px; border-left: 3px solid #00F2FE;">
                    <b style="color: #FFFFFF; font-size: 14px;">🔹 DeepSeek V4</b><br>
                    <span style="font-size: 12px;">• <b>API Keys:</b> <a href="https://platform.deepseek.com/api_keys" target="_blank" style="color: #38BDF8; text-decoration: none;">platform.deepseek.com</a></span><br>
                    <span style="font-size: 12px;">• <b>Base URL:</b> <code style="color: #00F2FE; background: #0F172A; padding: 2px 5px; border-radius: 4px;">https://api.deepseek.com</code></span><br>
                    <span style="font-size: 12px;">• <b>Model ID:</b> <code>deepseek-v4-flash</code> | <code>deepseek-v4-pro</code></span>
                </div>
                <div style="background: rgba(0,0,0,0.3); padding: 12px; border-radius: 8px; margin-bottom: 12px; border-left: 3px solid #00F2FE;">
                    <b style="color: #FFFFFF; font-size: 14px;">🔹 Grok (xAI 4.x)</b><br>
                    <span style="font-size: 12px;">• <b>API Keys:</b> <a href="https://console.x.ai/" target="_blank" style="color: #38BDF8; text-decoration: none;">console.x.ai</a></span><br>
                    <span style="font-size: 12px;">• <b>Base URL:</b> <code style="color: #00F2FE; background: #0F172A; padding: 2px 5px; border-radius: 4px;">https://api.x.ai/v1</code></span><br>
                    <span style="font-size: 12px;">• <b>Model ID:</b> <code>grok-4.3</code> | <code>grok-4.20-reasoning</code></span>
                </div>
                <div style="background: rgba(0,0,0,0.3); padding: 12px; border-radius: 8px; margin-bottom: 12px; border-left: 3px solid #00F2FE;">
                    <b style="color: #FFFFFF; font-size: 14px;">🔹 Together AI / Mistral / OpenRouter</b><br>
                    <span style="font-size: 12px;">• <b>Base URLs:</b> <code>https://api.together.xyz/v1</code> | <code>https://openrouter.ai/api/v1</code></span><br>
                    <span style="font-size: 12px;">• <b>Model ID:</b> Revisa la documentación de tu proveedor para el nombre exacto.</span>
                </div>
                <h4 style="color: #F8FAFC; margin-top: 25px; margin-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px; font-size: 15px;">🖥️ Proveedores Locales (LM Studio / Ollama)</h4>
                <div style="background: rgba(16, 185, 129, 0.1); padding: 15px; border-radius: 8px; border: 1px dashed #10B981; margin-bottom: 15px;">
                    <b style="color: #10B981; font-size: 13px;">⚠️ AVISO IMPORTANTE SOBRE REDES:</b>
                    <p style="font-size: 12px; margin-top: 5px; margin-bottom: 5px; color: #E2E8F0;">Si estás usando esta aplicación en la nube (ej. superagenteiapro.com), <code>localhost</code> no funcionará porque hace referencia al servidor en la nube, no a tu ordenador de casa.</p>
                    <p style="font-size: 12px; margin-top: 0; color: #E2E8F0;">Para conectar tu IA local a esta web, expón el puerto de tu LM Studio/Ollama a internet usando un túnel gratuito como <b><a href="https://ngrok.com/" target="_blank" style="color: #38BDF8;">Ngrok</a></b> o <b>Cloudflare Tunnels</b>, y pega la URL pública generada en el campo <i>Base URL</i>.</p>
                </div>
                <div style="background: rgba(0,0,0,0.3); padding: 12px; border-radius: 8px; margin-bottom: 12px; border-left: 3px solid #10B981;">
                    <b style="color: #FFFFFF; font-size: 14px;">🔹 LM Studio</b><br>
                    <span style="font-size: 12px;">• <b>Base URL (Si app es local):</b> <code style="color: #10B981; background: #0F172A; padding: 2px 5px; border-radius: 4px;">http://localhost:1234/v1</code></span><br>
                    <span style="font-size: 12px;">• <b>Base URL (Si app está online):</b> URL pública de tu Ngrok + <code>/v1</code></span><br>
                    <span style="font-size: 12px;">• <b>API Key:</b> <code>lm-studio</code></span>
                </div>
                <div style="background: rgba(0,0,0,0.3); padding: 12px; border-radius: 8px; margin-bottom: 12px; border-left: 3px solid #10B981;">
                    <b style="color: #FFFFFF; font-size: 14px;">🔹 Ollama (Modo API)</b><br>
                    <span style="font-size: 12px;">• <b>Base URL (Si app es local):</b> <code style="color: #10B981; background: #0F172A; padding: 2px 5px; border-radius: 4px;">http://localhost:11434/v1</code></span><br>
                    <span style="font-size: 12px;">• <b>Model ID:</b> <code>llama3</code> | <code>qwen2.5-coder:3b</code></span>
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )

        with st.form("custom_ai_form", clear_on_submit=True):
            st.markdown("**Conectar nuevo modelo:**")
            cm_name = st.text_input("Nombre descriptivo", placeholder="Ej: Mi DeepSeek Coder")
            cm_url = st.text_input("Base URL del Endpoint", placeholder="Ej: https://api.deepseek.com/v1")
            cm_key = st.text_input("API Key del proveedor", type="password")
            cm_model = st.text_input("Model ID", placeholder="Ej: deepseek-chat")

            if st.form_submit_button("➕ Conectar Modelo", type="primary", use_container_width=True):
                if cm_name and cm_url and cm_key and cm_model:
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
                    st.success(f"✅ '{cm_name}' conectado con éxito.")
                    st.rerun()
                else:
                    st.warning("⚠️ Completa todos los campos para conectar el modelo.")

    with tab2:
        st.markdown("Actualiza tus claves de acceso. Los campos vacíos conservan la clave guardada.")
        with st.form("base_keys_form"):
            keys = st.session_state.api_keys
            new_gemini = st.text_input("Gemini API Key", type="password", value=keys.get("GEMINI_API_KEY", ""))
            new_groq = st.text_input("Groq API Key", type="password", value=keys.get("GROQ_API_KEY", ""))
            new_or = st.text_input("OpenRouter API Key", type="password", value=keys.get("OPENROUTER_API_KEY", ""))
            new_oai = st.text_input("OpenAI API Key", type="password", value=keys.get("OPENAI_API_KEY", ""))
            new_stab = st.text_input("Stability AI API Key", type="password", value=keys.get("STABILITY_API_KEY", ""))

            if st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True):
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
                st.success("✅ Claves actualizadas correctamente.")
                st.rerun()

    with tab3:
        from src.database.database import get_user_profile, change_user_password

        perfil = get_user_profile(st.session_state.user_id)
        if perfil:
            st.markdown(f"**Nombre:** {perfil['first_name']} {perfil['last_name']}")
            st.markdown(f"**Usuario:** @{perfil['username']}")
            st.markdown(f"**Email:** {perfil['email']}")
            st.divider()

        st.markdown("**Cambiar Contraseña**")
        with st.form("change_password_form"):
            old_pass = st.text_input("Contraseña Actual", type="password")
            new_pass = st.text_input("Nueva Contraseña", type="password")
            confirm_pass = st.text_input("Confirmar Nueva Contraseña", type="password")

            if st.form_submit_button("Actualizar Contraseña", type="primary", use_container_width=True):
                if not old_pass or not new_pass or not confirm_pass:
                    st.warning("⚠️ Completa todos los campos.")
                elif new_pass != confirm_pass:
                    st.error("❌ Las nuevas contraseñas no coinciden.")
                else:
                    success, msg = change_user_password(st.session_state.user_id, old_pass, new_pass)
                    if success:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")
