import streamlit as st
import os
import sys
import json

st.set_page_config(page_title="SuperAgente IA Pro", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

from src.database import register_user, verify_login, update_api_keys, get_user_api_keys, create_chat, get_user_chats, delete_chat
from src.services.memory_service import cargar_memoria, guardar_memoria, limpiar_memoria
from src.core.config import PAGE_TITLE, PAGE_ICON, LAYOUT, CARPETA_IMAGENES, PROMPT_TECH_LEAD, PROMPT_APP_BUILDER, PROMPT_UI_DESIGNER, ESTILOS_CSS
from PIL import Image
from src.core.intent_parser import parse_intent
from src.core.ui_helpers import render_download_button

# --- INICIALIZACIÓN DE ESTADO ---
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "api_keys" not in st.session_state:
    st.session_state.api_keys = {}
if "chat_id" not in st.session_state:
    st.session_state.chat_id = None
if "onboarding_done" not in st.session_state:
    st.session_state.onboarding_done = False
if "messages" not in st.session_state:
    st.session_state.messages = []
if "rol_activo" not in st.session_state:
    st.session_state.rol_activo = "Asistente General (Tech Lead)"
if "motor_activo_idx" not in st.session_state:
    st.session_state.motor_activo_idx = 0

# --- ESTILOS ---
st.markdown(ESTILOS_CSS, unsafe_allow_html=True)

if not os.path.exists(CARPETA_IMAGENES):
    os.makedirs(CARPETA_IMAGENES)

# --- LOGIN Y REGISTRO ---
if not st.session_state.user_id:
    st.markdown("<h1 style='text-align: center; color: #00F2FE;'>⚡ SuperAgente IA Pro</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #A0AAB5;'>Acceso al Sistema</h3>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Iniciar Sesión", "Registrarse"])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Entrar", use_container_width=True)
            if submitted:
                if username and password:
                    success, result = verify_login(username, password)
                    if success:
                        st.session_state.user_id = result
                        # Cargar API keys
                        keys = get_user_api_keys(result)
                        st.session_state.api_keys = keys
                        if keys:
                            st.session_state.onboarding_done = True
                        st.rerun()
                    else:
                        st.error(result)
                else:
                    st.warning("Completa todos los campos.")
                    
    with tab2:
        with st.form("register_form"):
            new_username = st.text_input("Nuevo Usuario")
            new_password = st.text_input("Nueva Contraseña", type="password")
            reg_submitted = st.form_submit_button("Crear Cuenta", use_container_width=True)
            if reg_submitted:
                if new_username and new_password:
                    success, result = register_user(new_username, new_password)
                    if success:
                        st.success("Cuenta creada. Por favor, inicia sesión.")
                    else:
                        st.error(result)
                else:
                    st.warning("Completa todos los campos.")
    st.stop()

# --- ONBOARDING DE API KEYS ---
if not st.session_state.onboarding_done:
    st.markdown("<h2 style='text-align: center; color: #00F2FE;'>Configuración de Proveedores (Onboarding)</h2>", unsafe_allow_html=True)
    st.info("Configura tus API Keys. Si omites alguna, las funciones asociadas quedarán deshabilitadas en tu cuenta.")
    
    with st.form("onboarding_form"):
        gemini_key = st.text_input("Gemini API Key (Para razonamiento multimodal y arte)", type="password", help="Obténla en Google AI Studio")
        groq_key = st.text_input("Groq API Key (Para transcripción STT Whisper y Llama 3)", type="password", help="Obténla en Groq Console")
        openrouter_key = st.text_input("OpenRouter API Key", type="password", help="Obténla en OpenRouter")
        hf_key = st.text_input("Hugging Face API Key", type="password", help="Obténla en Hugging Face Tokens")
        openai_key = st.text_input("OpenAI API Key (Para TTS y DALL-E 3)", type="password", help="Obténla en platform.openai.com")
        stability_key = st.text_input("Stability AI API Key", type="password", help="Obténla en platform.stability.ai")
        
        submitted = st.form_submit_button("Guardar y Continuar", use_container_width=True)
        if submitted:
            keys = {}
            if gemini_key: keys["GEMINI_API_KEY"] = gemini_key
            if groq_key: keys["GROQ_API_KEY"] = groq_key
            if openrouter_key: keys["OPENROUTER_API_KEY"] = openrouter_key
            if hf_key: keys["HF_API_KEY"] = hf_key
            if openai_key: keys["OPENAI_API_KEY"] = openai_key
            if stability_key: keys["STABILITY_API_KEY"] = stability_key
            
            update_api_keys(st.session_state.user_id, keys)
            st.session_state.api_keys = keys
            st.session_state.onboarding_done = True
            st.rerun()
            
    if st.button("Omitir Onboarding (No recomendado)"):
        st.warning("Has omitido la configuración. No podrás usar modelos a menos que configures tus claves más tarde.")
        st.session_state.onboarding_done = True
        st.rerun()
        
    st.stop()


# --- PROVEEDORES LLM ---
def get_gemini_provider():
    from src.services.llm_provider import GeminiProvider
    return GeminiProvider(api_key=st.session_state.api_keys.get("GEMINI_API_KEY"))

def get_groq_provider():
    from src.services.llm_provider import GroqProvider
    return GroqProvider(api_key=st.session_state.api_keys.get("GROQ_API_KEY"))

def get_ollama_provider():
    from src.services.llm_provider import OllamaProvider
    return OllamaProvider()

def get_openrouter_provider():
    from src.services.llm_provider import OpenRouterProvider
    return OpenRouterProvider(api_key=st.session_state.api_keys.get("OPENROUTER_API_KEY"))

def get_groq_whisper_provider():
    from src.services.llm_provider import GroqWhisperProvider
    return GroqWhisperProvider(api_key=st.session_state.api_keys.get("GROQ_API_KEY"))

def get_openai_tts_provider(voice="alloy"):
    from src.services.llm_provider import OpenAITTSProvider
    return OpenAITTSProvider(voice=voice, api_key=st.session_state.api_keys.get("OPENAI_API_KEY"))

def get_edge_tts_provider(voice):
    from src.services.llm_provider import EdgeTTSProvider
    return EdgeTTSProvider(voice=voice)


# --- CONFIGURACIÓN DE CHATS EN SIDEBAR ---
with st.sidebar:
    st.header("💬 Mis Chats")
    
    if st.button("➕ Nuevo Chat", use_container_width=True):
        nuevo_id = create_chat(st.session_state.user_id, "Nuevo Chat")
        st.session_state.chat_id = nuevo_id
        st.session_state.messages = []
        st.rerun()
        
    chats = get_user_chats(st.session_state.user_id)
    if chats:
        opciones_chat = {c['id']: c['title'] for c in chats}
        
        if not st.session_state.chat_id and opciones_chat:
            st.session_state.chat_id = list(opciones_chat.keys())[0]
            st.session_state.messages = cargar_memoria(st.session_state.chat_id)
            
        chat_seleccionado = st.selectbox(
            "Seleccionar chat:", 
            options=list(opciones_chat.keys()), 
            format_func=lambda x: opciones_chat[x],
            index=list(opciones_chat.keys()).index(st.session_state.chat_id) if st.session_state.chat_id in opciones_chat else 0
        )
        
        if chat_seleccionado != st.session_state.chat_id:
            st.session_state.chat_id = chat_seleccionado
            st.session_state.messages = cargar_memoria(st.session_state.chat_id)
            st.rerun()
    else:
        st.info("No tienes chats.")
        if not st.session_state.chat_id:
            nuevo_id = create_chat(st.session_state.user_id, "Nuevo Chat")
            st.session_state.chat_id = nuevo_id
            st.session_state.messages = []
            st.rerun()

    st.divider()


# Mapa de Roles
ROLES = {
    "🧠 Asistente General (Tech Lead)": {
        "prompt": PROMPT_TECH_LEAD,
        "motor_forzado": None,
    },
    "🏗️ Arquitecto de Software (App Builder)": {
        "prompt": PROMPT_APP_BUILDER,
        "motor_forzado": "Groq Llama 3.3 (Lead Software Engineer / Creador)",
    },
    "🎨 Diseñador Frontend UI/UX (Vision)": {
        "prompt": PROMPT_UI_DESIGNER,
        "motor_forzado": "Gemini 2.5 Pro (Análisis Multimedia y Arte)",
    },
}

def cambiar_rol():
    nuevo_rol = st.session_state.selector_rol
    if nuevo_rol != st.session_state.rol_activo:
        provider = get_groq_provider()
        historial_texto = "\\n".join([f"{m['role']}: {m.get('content', '')}" for m in st.session_state.messages])
        
        if len(historial_texto.strip()) > 0 and st.session_state.api_keys.get("GROQ_API_KEY"):
            prompt_resumen = f"Resume este historial de chat en un solo párrafo conciso para darle contexto al siguiente agente de IA sobre qué está construyendo o discutiendo el usuario. Historial:\\n{historial_texto}"
            try:
                resumen_chunks = list(provider.stream_chat(prompt_resumen, []))
                resumen = "".join(resumen_chunks)
                if "❌" in resumen:
                    resumen = "El usuario cambió de rol para continuar el proyecto."
            except:
                resumen = "El usuario cambió de rol."
                
            st.session_state.messages = []
            st.session_state.messages.append({"role": "user", "content": f"*(Contexto transferido del rol anterior):* {resumen}"})
        else:
            st.session_state.messages = []
            
        if "App Builder" in nuevo_rol:
            st.session_state.motor_activo_idx = 0 
        elif "UI/UX" in nuevo_rol:
            st.session_state.motor_activo_idx = 1 
            
        if st.session_state.chat_id:
            guardar_memoria(st.session_state.chat_id, st.session_state.messages, st.session_state.api_keys)
        st.session_state.rol_activo = nuevo_rol

# --- PANEL DE CONVERSIÓN (DIALOG) ---
from src.services.converter_service import run_conversion

@st.dialog("🔄 Estudio de Conversión Universal")
def panel_conversor():
    st.write("Sube cualquier archivo (video, audio, imagen, documento) y conviértelo al instante.")
    archivo_conv = st.file_uploader("📥 Arrastra tu archivo aquí", key="uploader_conv")
    
    if archivo_conv:
        st.info(f"Archivo detectado: {archivo_conv.name}")
        formato_destino = st.text_input("Formato de destino (ej: mp3, pdf, docx, png)", value=st.session_state.get("suggested_format", ""))
        
        if st.button("🚀 Convertir", use_container_width=True):
            if formato_destino:
                formato_destino = formato_destino.strip().replace(".", "")
                with st.spinner(f"Convirtiendo a .{formato_destino} (Aceleración Local)..."):
                    import uuid
                    os.makedirs("data/temp", exist_ok=True)
                    input_ext = os.path.splitext(archivo_conv.name)[1]
                    temp_input = f"data/temp/in_{uuid.uuid4().hex[:8]}{input_ext}"
                    with open(temp_input, "wb") as f:
                        f.write(archivo_conv.getbuffer())
                    
                    output_name = f"conv_{uuid.uuid4().hex[:8]}.{formato_destino}"
                    temp_output = os.path.join(CARPETA_IMAGENES, output_name)
                    
                    exito = run_conversion(temp_input, temp_output)
                    
                    if exito:
                        st.session_state.conv_result_path = temp_output
                        st.session_state.conv_result_name = output_name
                        st.success("✅ ¡Conversión Exitosa!")
                    else:
                        st.error("❌ Falló la conversión. Asegúrate de tener FFmpeg / Pandoc instalados localmente.")
                    
                    if os.path.exists(temp_input):
                        os.remove(temp_input)

    if "conv_result_path" in st.session_state and st.session_state.conv_result_path:
        with open(st.session_state.conv_result_path, "rb") as f:
            st.download_button(
                label=f"⬇️ Descargar {st.session_state.conv_result_name}",
                data=f,
                file_name=st.session_state.conv_result_name,
                use_container_width=True,
                key="btn_dl_conv"
            )

# --- INTERFAZ PRINCIPAL ---
st.markdown("""
<div style="text-align: center; margin-top: -30px; margin-bottom: 30px;">
    <h1 style="
        font-family: 'Outfit', 'Inter', sans-serif;
        font-size: 3.8rem;
        font-weight: 800;
        background: linear-gradient(90deg, #00F2FE, #4FACFE, #00F2FE);
        background-size: 200% auto;
        color: transparent;
        -webkit-background-clip: text;
        background-clip: text;
        animation: shineTitle 3s linear infinite;
        text-shadow: 0 0 20px rgba(0, 242, 254, 0.4);
        margin-bottom: 0px;
        line-height: 1.2;
    ">⚡ SuperAgente IA Pro</h1>
    <p style="
        font-size: 1.1rem;
        color: #A0AAB5;
        font-weight: 300;
        letter-spacing: 3px;
        text-transform: uppercase;
        margin-top: 5px;
    ">Sistema Experto con Multimodalidad Total</p>
</div>
""", unsafe_allow_html=True)


with st.sidebar:
    st.header("🎭 Rol del Agente")
    rol_seleccionado = st.selectbox(
        "Modo de operación:",
        list(ROLES.keys()),
        key="selector_rol",
        on_change=cambiar_rol
    )
    rol_config = ROLES[rol_seleccionado]
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
        "Ollama Qwen (Desarrollo Local Zero-Trust)",
        "Groq Whisper (Oídos: Transcripción STT)",
        "OpenAI TTS (Voz: Text-to-Speech)",
        "Generador de Assets (Manos: Texto a Imagen)",
    ]
    if motor_forzado:
        motor = motor_forzado
        st.selectbox("Cerebro Activo:", [motor_forzado], index=0, disabled=True, key="motor_manual_selector")
    else:
        motor = st.selectbox("Cerebro Activo:", motores_disponibles,
                             index=st.session_state.motor_activo_idx, key="motor_manual_selector")

    st.divider()

    st.markdown("**📁 Adjuntar Archivo**")
    archivo = st.file_uploader(
        "Código, docs, imágenes, datos…",
        type=None,
        help="Formatos soportados: texto, código, PDF, Word, Excel, imágenes, JSON, YAML, logs y más.",
        label_visibility="collapsed"
    )

    st.divider()

    with st.expander("🛠️ Herramientas Multimedia", expanded=False):

        if st.button("🔄 Estudio de Conversión", use_container_width=True):
            st.session_state["suggested_format"] = ""
            panel_conversor()

        st.markdown("---")

        st.markdown("**🎙️ Transcripción STT — Groq Whisper**")
        st.caption("Transcribe audio a texto con Whisper Large v3.")
        audio_stt = st.file_uploader(
            "Audio (mp3, wav, webm, ogg, flac, m4a)",
            type=["mp3", "wav", "webm", "ogg", "flac", "m4a", "mp4"],
            key="uploader_stt"
        )
        
        if audio_stt:
            st.audio(audio_stt, format=f"audio/{audio_stt.name.split('.')[-1]}")
            if st.button("🎤 Transcribir", use_container_width=True, key="btn_stt"):
                with st.spinner("Enviando a Groq Whisper… ⚡"):
                    proveedor_stt = get_groq_whisper_provider()
                    texto_transcrito, error_stt = proveedor_stt.transcribe(
                        audio_bytes=audio_stt.getvalue(),
                        filename=audio_stt.name
                    )
                if error_stt:
                    st.error(error_stt)
                else:
                    st.session_state.stt_result_text = texto_transcrito
                    st.success("✅ Transcripción completada")
        
        if "stt_result_text" in st.session_state and st.session_state.stt_result_text:
            st.text_area("Texto transcrito:", value=st.session_state.stt_result_text, height=120, key="stt_result_area")
            if st.button("💬 Enviar al chat", use_container_width=True, key="btn_stt_inject"):
                st.session_state.messages.append({"role": "user", "content": st.session_state.stt_result_text})
                guardar_memoria(st.session_state.chat_id, st.session_state.messages, st.session_state.api_keys)
                st.rerun()

        st.markdown("---")

        st.markdown("**🔊 Síntesis de Voz — TTS**")
        st.caption("Convierte texto a voz natural.")
        
        col_prov, col_voice = st.columns([1, 1])
        with col_prov:
            prov_tts_sel = st.selectbox("Proveedor:", ["Edge TTS (Gratis)", "OpenAI TTS (Pago)"], key="tts_provider_sel")
        
        with col_voice:
            if prov_tts_sel == "OpenAI TTS (Pago)":
                voz_seleccionada = st.selectbox(
                    "Voz:",
                    ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                    index=0,
                    key="tts_voice_selector"
                )
            else:
                from src.services.audio_service import AVAILABLE_EDGE_VOICES
                voz_alias = st.selectbox("Voz (Regional):", list(AVAILABLE_EDGE_VOICES.keys()), key="edge_voice_selector")
                voz_seleccionada = AVAILABLE_EDGE_VOICES[voz_alias]

        texto_para_tts = st.text_area(
            "Texto a sintetizar:",
            placeholder="Escribe aquí el texto que quieres escuchar…",
            height=100,
            max_chars=4096,
            key="tts_input_text"
        )
        if st.button("🔊 Generar Audio", use_container_width=True, key="btn_tts"):
            if not texto_para_tts.strip():
                st.warning("⚠️ Escribe algo antes de sintetizar.")
            else:
                with st.spinner(f"Sintetizando con {prov_tts_sel}…"):
                    if prov_tts_sel == "OpenAI TTS (Pago)":
                        proveedor_tts = get_openai_tts_provider(voice=voz_seleccionada)
                    else:
                        proveedor_tts = get_edge_tts_provider(voice=voz_seleccionada)
                        
                    audio_bytes_out, audio_filepath, error_tts = proveedor_tts.synthesize(texto_para_tts)
                if error_tts:
                    st.error(error_tts)
                else:
                    st.session_state.tts_result_path = audio_filepath
                    st.session_state.tts_result_bytes = audio_bytes_out
                    st.success("✅ ¡Audio generado!")

        if "tts_result_path" in st.session_state and st.session_state.tts_result_path:
            st.audio(st.session_state.tts_result_bytes, format="audio/mp3")
            render_download_button(st.session_state.tts_result_path)

        st.markdown("---")

        st.markdown("**🎨 Generador de Assets — Texto a Imagen**")
        st.caption("Genera imágenes con DALL-E 3 o Stability AI.")
        proveedor_imagen_sel = st.radio(
            "Proveedor:",
            ["OpenAI DALL-E 3", "Stability AI"],
            horizontal=True,
            key="img_provider_radio"
        )
        prompt_imagen_gen = st.text_area(
            "Prompt:",
            placeholder="Ej: A futuristic robot reading a book…",
            height=80,
            key="img_gen_prompt"
        )
        if proveedor_imagen_sel == "OpenAI DALL-E 3":
            col_size, col_quality = st.columns(2)
            with col_size:
                dalle_size = st.selectbox("Resolución:", ["1024x1024", "1792x1024", "1024x1792"], key="dalle_size")
            with col_quality:
                dalle_quality = st.selectbox("Calidad:", ["standard", "hd"], key="dalle_quality")
        else:
            stability_aspect = st.selectbox(
                "Proporción:", ["1:1", "16:9", "9:16", "3:2", "2:3", "4:5", "5:4"], key="stability_aspect"
            )
            stability_negative = st.text_input(
                "Prompt negativo (opcional):",
                placeholder="Ej: blurry, low quality",
                key="stability_negative"
            )
        if st.button("🎨 Generar Imagen", use_container_width=True, key="btn_img_gen"):
            if not prompt_imagen_gen.strip():
                st.warning("⚠️ Escribe un prompt antes de generar.")
            else:
                with st.spinner(f"Generando con {proveedor_imagen_sel}…"):
                    from src.services.image_gen_service import generate_image
                    if proveedor_imagen_sel == "OpenAI DALL-E 3":
                        filepath_gen, error_gen = generate_image(
                            prompt=prompt_imagen_gen,
                            provider="openai_dalle3",
                            api_key=st.session_state.api_keys.get("OPENAI_API_KEY"),
                            size=st.session_state.get("dalle_size", "1024x1024"),
                            quality=st.session_state.get("dalle_quality", "standard")
                        )
                    else:
                        filepath_gen, error_gen = generate_image(
                            prompt=prompt_imagen_gen,
                            provider="stability_ai",
                            api_key=st.session_state.api_keys.get("STABILITY_API_KEY"),
                            groq_api_key=st.session_state.api_keys.get("GROQ_API_KEY"),
                            aspect_ratio=st.session_state.get("stability_aspect", "1:1"),
                            negative_prompt=st.session_state.get("stability_negative", "")
                        )
                if error_gen:
                    st.error(error_gen)
                else:
                    st.session_state.img_result_path = filepath_gen
                    st.session_state.img_result_prompt = prompt_imagen_gen
                    st.session_state.img_result_provider = proveedor_imagen_sel
                    st.success("✅ ¡Imagen generada!")
                    
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"🎨 *Asset generado con {proveedor_imagen_sel}:* '{prompt_imagen_gen}'",
                        "image_path": filepath_gen
                    })
                    guardar_memoria(st.session_state.chat_id, st.session_state.messages, st.session_state.api_keys)

        if "img_result_path" in st.session_state and st.session_state.img_result_path:
            from PIL import Image
            img_gen = Image.open(st.session_state.img_result_path)
            st.image(img_gen, caption=st.session_state.img_result_prompt[:60], use_container_width=True)
            render_download_button(st.session_state.img_result_path)

    st.divider()

    st.markdown('<div class="danger-btn">', unsafe_allow_html=True)
    if st.button("🗑️ Eliminar historial actual", use_container_width=True, key="btn_borrar_memoria"):
        limpiar_memoria(st.session_state.chat_id)
        st.session_state.messages = []
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


for msg in st.session_state.messages:
    if msg.get("role") == "system": continue
    avatar = "🧑‍💻" if msg["role"]=="user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        if msg.get("content"):
            st.markdown(msg["content"])
        if msg.get("image_path") and os.path.exists(msg.get("image_path")):
            filepath = msg["image_path"]
            img = Image.open(filepath)
            st.image(img, caption="Obra generada", use_container_width=True)
            render_download_button(filepath)
            
        if msg.get("file_paths"):
            for fp in msg.get("file_paths"):
                render_download_button(fp)

if prompt := st.chat_input("Escribe tu consulta o pídele que genere una imagen..."):
    
    es_comando_imagen, prompt_artistico = parse_intent(prompt)

    MOTORES_HERRAMIENTA = {
        "Groq Whisper (Oídos: Transcripción STT)",
        "OpenAI TTS (Voz: Text-to-Speech)",
        "Generador de Assets (Manos: Texto a Imagen)",
    }
    if motor in MOTORES_HERRAMIENTA:
        _guias = {
            "Groq Whisper (Oídos: Transcripción STT)":
                "🎙️ **Modo STT activo.** Sube un archivo de audio en el panel **'Groq Whisper'** del sidebar y pulsa *'Transcribir'*.",
            "OpenAI TTS (Voz: Text-to-Speech)":
                "🔊 **Modo TTS activo.** Escribe el texto en el panel **'OpenAI TTS'** del sidebar y pulsa *'Generar Audio'*.",
            "Generador de Assets (Manos: Texto a Imagen)":
                "🎨 **Modo Imagen activo.** Escribe tu prompt en el panel **'Generador de Assets'** del sidebar y pulsa *'Generar Imagen'*.",
        }
        st.info(_guias[motor])
        st.stop()

    if es_comando_imagen:
        if "Gemini" not in motor:
            st.warning("⚠️ La generación de arte requiere seleccionar el motor **Gemini** en el panel de control.")
            st.stop()

        if not prompt_artistico:
            st.error("❌ Te ha faltado decirme qué quieres que dibuje.")
            st.stop()

        prompt_visibilidad = f"🎨 *Has pedido crear:* {prompt_artistico}"
        st.session_state.messages.append({"role": "user", "content": prompt_visibilidad})
        with st.chat_message("user", avatar="🧑‍💻"): st.markdown(prompt_visibilidad)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Conectando con el estudio de arte de Gemini..."):
                provider = get_gemini_provider()
                filepath, error = provider.generar_imagen(prompt_artistico)

            if error:
                st.error(error)
                st.session_state.messages.append({"role": "assistant", "content": error})
            else:
                img = Image.open(filepath)
                st.image(img, caption=f"Obra: {prompt_artistico}", use_container_width=True)
                render_download_button(filepath)

                response_text = f"Aquí tienes la imagen generada: '{prompt_artistico}'"
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_text,
                    "image_path": filepath
                })
        guardar_memoria(st.session_state.chat_id, st.session_state.messages, st.session_state.api_keys)

    else:
        from src.services.document_parser import extraer_texto_archivo
        texto_extraido = ""
        imagen_adjunta = None
        video_adjunto_path = None

        if archivo:
            from pathlib import Path as _Path
            _ext = _Path(archivo.name.lower()).suffix
            _EXTS_IMAGEN = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tiff', '.ico'}
            _EXTS_VIDEO  = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv'}

            if _ext in _EXTS_IMAGEN:
                imagen_adjunta = Image.open(archivo)
                texto_extraido = f"\\n*(Adjuntada imagen para análisis visual: {archivo.name})*"
            elif _ext in _EXTS_VIDEO:
                import uuid
                safe_filename = f"video_analisis_{uuid.uuid4().hex[:8]}{_ext}"
                video_adjunto_path = os.path.join(CARPETA_IMAGENES, safe_filename)
                with open(video_adjunto_path, "wb") as f:
                    f.write(archivo.getbuffer())
                texto_extraido = f"\\n*(Adjuntado vídeo para análisis: {archivo.name})*"
            else:
                contenido_extraido = extraer_texto_archivo(archivo)
                if contenido_extraido.startswith("⛔"):
                    st.warning(contenido_extraido)
                    texto_extraido = f"\\n\\n[ARCHIVO: {archivo.name}]\\n{contenido_extraido}\\n"
                else:
                    texto_extraido = f"\\n\\n[CONTENIDO DE {archivo.name.upper()}]:\\n{contenido_extraido}\\n"

        prompt_final = prompt + texto_extraido
        st.session_state.messages.append({"role": "user", "content": prompt_final})
        with st.chat_message("user", avatar="🧑‍💻"): st.markdown(prompt_final)

        with st.chat_message("assistant", avatar="🤖"):
            res_placeholder = st.empty()
            
            if "Gemini" in motor:
                carga_util = [prompt_final]
                if imagen_adjunta: carga_util.append(imagen_adjunta)
                if video_adjunto_path:
                    import google.genai as ggenai
                    import time
                    try:
                        with st.status("🎬 Inicializando procesamiento de vídeo...", expanded=True) as status:
                            st.write("📤 Subiendo archivo seguro a Gemini...")
                            gemini_key = st.session_state.api_keys.get("GEMINI_API_KEY")
                            if not gemini_key:
                                st.error("❌ Falta la clave de Gemini para procesar vídeo.")
                                st.stop()
                            cliente_g = ggenai.Client(api_key=gemini_key)
                            video_file = cliente_g.files.upload(file=video_adjunto_path)
                            
                            start_time = time.time()
                            while video_file.state.name == "PROCESSING":
                                elapsed = int(time.time() - start_time)
                                status.update(label=f"🎬 Analizando vídeo en la nube... (⏳ {elapsed}s transcurridos)", state="running")
                                time.sleep(2)
                                video_file = cliente_g.files.get(name=video_file.name)
                                
                            if video_file.state.name == "FAILED":
                                status.update(label="❌ Error crítico de procesamiento", state="error", expanded=True)
                                st.error("Fallo interno en los servidores de Google GenAI al decodificar el vídeo.")
                                st.stop()
                                
                            status.update(label=f"✅ Vídeo procesado con éxito en {int(time.time() - start_time)}s", state="complete", expanded=False)
                        carga_util.append(video_file)
                    finally:
                        if os.path.exists(video_adjunto_path):
                            os.remove(video_adjunto_path)

                provider = get_gemini_provider()
            elif "Groq" in motor:
                if imagen_adjunta: st.warning("⚠️ Este motor ignora imágenes locales.")
                provider = get_groq_provider()
            else:
                if imagen_adjunta: st.warning("⚠️ Ollama ignora imágenes locales.")
                provider = get_ollama_provider()

            clean_res = ""
            file_paths = []
            max_iteraciones = 2
            iteracion = 0
            
            while iteracion < max_iteraciones:
                iteracion += 1
                full_res = ""
                
                try:
                    if "Gemini" in motor:
                        gen = provider.stream_chat(carga_util, st.session_state.messages[:-1], system_instruction=system_instruction_activo)
                    else:
                        gen = provider.stream_chat(prompt_final, st.session_state.messages[:-1], system_instruction=system_instruction_activo)
                        
                    for chunk in gen:
                        if chunk: 
                            full_res += chunk
                            res_placeholder.markdown(full_res + "▌")
                            
                except Exception as e:
                    if "Groq" in motor:
                        res_placeholder.empty()
                        st.warning(f"⚠️ El motor primario (Groq) falló ({str(e)}). Redirigiendo a Gemini...")
                        provider_backup = get_gemini_provider()
                        carga_util = [prompt_final]
                        if imagen_adjunta: carga_util.append(imagen_adjunta)
                        
                        full_res = ""
                        try:
                            gen_backup = provider_backup.stream_chat(carga_util, st.session_state.messages[:-1], system_instruction=system_instruction_activo)
                            for chunk in gen_backup:
                                if chunk:
                                    full_res += chunk
                                    res_placeholder.markdown(full_res + "▌")
                        except Exception as e_backup:
                            st.error(f"❌ Fallo crítico en el sistema de respaldo: {e_backup}")
                            break
                    else:
                        st.error(f"❌ Error en la generación ({motor}): {e}")
                        break

                from src.core.agent_tools import parse_tool_calls
                from src.services.file_factory import FileFactory
                
                clean_res, tools = parse_tool_calls(full_res)
                res_placeholder.markdown(clean_res)
                
                execute_tool = next((t for t in tools if t.get("action") == "execute_code"), None)
                if execute_tool:
                    codigo = execute_tool.get("code", "")
                    with st.spinner("Ejecutando código Python en sandbox local..."):
                        from src.services.execution_service import CodeExecutionService
                        exec_service = CodeExecutionService()
                        resultado_ejecucion = exec_service.execute_python(codigo)
                        
                    st.info("💻 Ejecución de código local completada.")
                    st.session_state.messages.append({"role": "assistant", "content": clean_res})
                    msg_sistema = f"RESULTADO DE LA EJECUCIÓN (STDOUT/STDERR):\\n{resultado_ejecucion}\\n\\nPor favor, usa esta salida para responder al usuario o continuar tu tarea."
                    st.session_state.messages.append({"role": "user", "content": msg_sistema})
                    
                    if "Gemini" in motor: carga_util = [msg_sistema]
                    else: prompt_final = msg_sistema
                    res_placeholder = st.empty()
                    continue
                    
                rag_tool = next((t for t in tools if t.get("action") == "query_rag"), None)
                if rag_tool:
                    query = rag_tool.get("query", "")
                    with st.spinner(f"Consultando Cerebro RAG para: '{query}'..."):
                        from src.services.rag_service import RAGService
                        rag_service = RAGService()
                        resultados = rag_service.query(query)
                        
                    st.info(f"🧠 Consulta RAG completada: {len(resultados)} fragmentos encontrados.")
                    st.session_state.messages.append({"role": "assistant", "content": clean_res})
                    if resultados:
                        res_texto = "\\n\\n".join([f"📄 {r['filename']}:\\n{r['content']}..." for r in resultados])
                        msg_sistema = f"RESULTADOS DEL CEREBRO RAG PARA '{query}':\\n{res_texto}\\n\\nUsa esta información parcial para responder."
                    else:
                        msg_sistema = f"El Cerebro RAG no encontró resultados relevantes para '{query}'."
                        
                    st.session_state.messages.append({"role": "user", "content": msg_sistema})
                    if "Gemini" in motor: carga_util = [msg_sistema]
                    else: prompt_final = msg_sistema
                    res_placeholder = st.empty()
                    continue
                
                search_tool = next((t for t in tools if t.get("action") == "search_web"), None)
                if search_tool:
                    query = search_tool.get("query", "")
                    with st.spinner(f"Buscando en la web: '{query}'..."):
                        from src.services.web_search import search_web
                        resultados_web = search_web(query)
                        
                    st.info(f"🌐 Búsqueda web completada: {query}")
                    st.session_state.messages.append({"role": "assistant", "content": clean_res})
                    msg_sistema = f"RESULTADOS DE BÚSQUEDA PARA '{query}':\\n{resultados_web}\\n\\nPor favor, usa esta información para generar la respuesta definitiva o el documento."
                    st.session_state.messages.append({"role": "user", "content": msg_sistema})
                    
                    if "Gemini" in motor: carga_util = [msg_sistema]
                    else: prompt_final = msg_sistema
                    res_placeholder = st.empty()
                    continue 
                else:
                    break 
            
            file_paths = []
            if tools:
                factory = FileFactory(output_dir=CARPETA_IMAGENES)
                for tool in tools:
                    if tool.get("action") == "search_web": continue
                    if tool.get("action") == "open_converter":
                        st.session_state["suggested_format"] = tool.get("suggested_format", "")
                        st.success(f"🤖 ¡Abriendo panel de conversión para ti (Formato: {st.session_state['suggested_format']})!")
                        panel_conversor()
                        continue
                    
                    path = factory.execute_tool(tool)
                    if path:
                        file_paths.append(path)
                        render_download_button(path)
                    else:
                        st.error(f"❌ La herramienta `{tool.get('action')}` falló internamente.")
        
        st.session_state.messages.append({"role": "assistant", "content": clean_res, "file_paths": file_paths})
        guardar_memoria(st.session_state.chat_id, st.session_state.messages, st.session_state.api_keys)
