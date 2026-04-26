import streamlit as st
import os
import sys

# Agregar el directorio raíz del proyecto al PYTHONPATH para que reconozca el módulo 'src'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
import requests
from src.services.llm_provider import GeminiProvider, GroqProvider, OllamaProvider
from dotenv import load_dotenv
from PIL import Image
import datetime

from src.core.config import (
    PAGE_TITLE, PAGE_ICON, LAYOUT, 
    CLAVE_GEMINI, CLAVE_GROQ, CARPETA_IMAGENES, 
    INSTRUCCIONES_SISTEMA, ESTILOS_CSS
)
from src.core.intent_parser import parse_intent
from src.core.ui_helpers import render_download_button
from src.services.memory_service import cargar_memoria, guardar_memoria, limpiar_memoria

# 1. CONFIGURACIÓN Y UI PREMIUM
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout=LAYOUT)
st.markdown(ESTILOS_CSS, unsafe_allow_html=True)

if not os.path.exists(CARPETA_IMAGENES):
    os.makedirs(CARPETA_IMAGENES)

# 2. PROCESADOR MAESTRO DE DOCUMENTOS (Multiformato)
from src.services.document_parser import extraer_texto_archivo

# 3. MOTORES LLM (Instanciados bajo demanda)
# 4. INTERFAZ
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
    ">⚡ Agente IA Pro v4.1</h1>
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

if "messages" not in st.session_state: st.session_state.messages = cargar_memoria()

# --- LÓGICA DE ENRUTAMIENTO (TECH LEAD) ---
if "motor_activo_idx" not in st.session_state: st.session_state.motor_activo_idx = 0
if "tech_lead_msg" not in st.session_state: st.session_state.tech_lead_msg = ""

def recomendar_motor():
    tarea = st.session_state.tarea_selector
    if "Arte visual" in tarea or "Analizar" in tarea:
        st.session_state.motor_activo_idx = 1
        st.session_state.motor_manual_selector = "Gemini 2.5 Pro (Análisis Multimedia y Arte)"
        if "Arte" in tarea:
            st.session_state.tech_lead_msg = "He asignado a **Gemini 2.5 Pro** porque tiene un motor de difusión nativo insuperable para generar arte visual."
        else:
            st.session_state.tech_lead_msg = "He asignado a **Gemini 2.5 Pro**. Su API nativa soporta la carga de vídeos enteros para analizarlos frame a frame."
    elif "Software" in tarea or "Documento" in tarea:
        st.session_state.motor_activo_idx = 0
        st.session_state.motor_manual_selector = "Groq Llama 3.3 (Lead Software Engineer / Creador)"
        if "Software" in tarea:
            st.session_state.tech_lead_msg = "He asignado a **Groq Llama 3.3**. Su velocidad y razonamiento lógico lo hacen el rey absoluto para picar código sin fallos."
        else:
            st.session_state.tech_lead_msg = "He asignado a **Groq Llama 3.3**. Es rapidísimo estructurando datos para crear archivos PDF o Excel."
    elif "Privada" in tarea:
        st.session_state.motor_activo_idx = 2
        st.session_state.motor_manual_selector = "Ollama Qwen (Desarrollo Local Zero-Trust)"
        st.session_state.tech_lead_msg = "He aislado el entorno hacia **Ollama Qwen**. Tu código e ideas no saldrán de esta máquina. (Zero-Trust)."
    else:
        st.session_state.tech_lead_msg = ""
# ------------------------------------------

with st.sidebar:
    st.header("👨‍💻 Asistente Tech Lead")
    st.selectbox(
        "¿Cuál es tu objetivo principal?",
        [
            "💡 Selecciona un objetivo...",
            "🎨 Generar una Imagen / Arte visual",
            "🎥 Analizar un Vídeo o Imagen (Gemini)",
            "💻 Desarrollar Software o Escribir Código",
            "📄 Generar un Documento (PDF, Excel, Word)",
            "🔒 Tarea Privada/Sensible (Local)"
        ],
        key="tarea_selector",
        on_change=recomendar_motor
    )
    
    if st.session_state.tech_lead_msg:
        st.success(st.session_state.tech_lead_msg)
        
    st.divider()
    
    st.header("⚙️ Configuración Manual")
    motor = st.selectbox("Cerebro Activo:", [
        "Groq Llama 3.3 (Lead Software Engineer / Creador)", 
        "Gemini 2.5 Pro (Análisis Multimedia y Arte)", 
        "Ollama Qwen (Desarrollo Local Zero-Trust)"
    ], index=st.session_state.motor_activo_idx, key="motor_manual_selector")
    
    st.info("💡 Pídele de forma natural que cree imágenes. Ej: *'Genera una imagen de un logo...'*")
    st.divider()
    archivo = st.file_uploader("📁 Adjuntar Documento, Imagen o Vídeo", 
                              type=['py','js','txt','pdf','docx','odt','xlsx','xls','ods','csv','pptx','odp','png','jpg','jpeg','mp4','mov','avi'])
    if st.button("🗑️ Borrar Memoria Completa", use_container_width=True):
        st.session_state.messages = []
        limpiar_memoria()
        st.rerun()

for msg in st.session_state.messages:
    avatar = "🧑‍💻" if msg["role"]=="user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        if msg.get("content"):
            st.markdown(msg["content"])
        if msg.get("image_path") and os.path.exists(msg["image_path"]):
            filepath = msg["image_path"]
            img = Image.open(filepath)
            st.image(img, caption="Obra generada", use_container_width=True)
            render_download_button(filepath)
            
        # Soporte futuro para cualquier otro tipo de archivo
        if msg.get("file_paths"):
            for fp in msg.get("file_paths"):
                render_download_button(fp)

if prompt := st.chat_input("Escribe tu consulta o pídele que genere una imagen..."):
    
    es_comando_imagen, prompt_artistico = parse_intent(prompt)
    
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
                provider = GeminiProvider()
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
        guardar_memoria(st.session_state.messages)

    else:
        texto_extraido = ""
        imagen_adjunta = None
        video_adjunto_path = None

        if archivo:
            if archivo.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                imagen_adjunta = Image.open(archivo)
                texto_extraido = f"\n*(Adjuntada imagen para análisis: {archivo.name})*"
            elif archivo.name.lower().endswith(('.mp4', '.mov', '.avi')):
                import uuid
                safe_filename = f"video_analisis_{uuid.uuid4().hex[:8]}{os.path.splitext(archivo.name)[1]}"
                video_adjunto_path = os.path.join(CARPETA_IMAGENES, safe_filename)
                with open(video_adjunto_path, "wb") as f:
                    f.write(archivo.getbuffer())
                texto_extraido = f"\n*(Adjuntado vídeo para análisis: {archivo.name})*"
            else:
                texto_extraido = f"\n\n[CONTENIDO DE {archivo.name.upper()}]:\n{extraer_texto_archivo(archivo)}\n"

        prompt_final = prompt + texto_extraido
        st.session_state.messages.append({"role": "user", "content": prompt_final})
        with st.chat_message("user", avatar="🧑‍💻"): st.markdown(prompt_final)

        with st.chat_message("assistant", avatar="🤖"):
            res_placeholder = st.empty()
            full_res = ""
            
            if "Gemini" in motor:
                carga_util = [prompt_final]
                if imagen_adjunta: carga_util.append(imagen_adjunta)
                if video_adjunto_path:
                    import google.genai as ggenai
                    import time
                    with st.spinner("Subiendo y procesando vídeo en los servidores de Gemini... esto puede tardar un minuto."):
                        cliente_g = ggenai.Client(api_key=CLAVE_GEMINI)
                        video_file = cliente_g.files.upload(file=video_adjunto_path)
                        while video_file.state.name == "PROCESSING":
                            time.sleep(2)
                            video_file = cliente_g.files.get(name=video_file.name)
                        if video_file.state.name == "FAILED":
                            st.error("Error al procesar el vídeo en Google.")
                            st.stop()
                    carga_util.append(video_file)
                provider = GeminiProvider()
                gen = provider.stream_chat(carga_util, st.session_state.messages[:-1])
            elif "Groq" in motor:
                if imagen_adjunta: st.warning("⚠️ Este motor ignora imágenes locales.")
                provider = GroqProvider()
                gen = provider.stream_chat(prompt_final, st.session_state.messages[:-1])
            else:
                if imagen_adjunta: st.warning("⚠️ Ollama ignora imágenes locales.")
                provider = OllamaProvider()
                gen = provider.stream_chat(prompt_final, st.session_state.messages[:-1])
                
            for chunk in gen:
                full_res += chunk
                res_placeholder.markdown(full_res + "▌")
                
            # Post-procesamiento de herramientas universales
            from src.core.agent_tools import parse_tool_calls
            from src.services.file_factory import FileFactory
            
            clean_res, tools = parse_tool_calls(full_res)
            res_placeholder.markdown(clean_res)
            
            file_paths = []
            if tools:
                factory = FileFactory(output_dir=CARPETA_IMAGENES)
                for tool in tools:
                    path = factory.execute_tool(tool)
                    if path:
                        file_paths.append(path)
                        render_download_button(path)
                    else:
                        st.error(f"❌ La herramienta `{tool.get('action')}` falló internamente al generar el archivo. (Comprueba la consola para más detalles).")
        
        st.session_state.messages.append({"role": "assistant", "content": clean_res, "file_paths": file_paths})
        guardar_memoria(st.session_state.messages)