import streamlit as st
import os
import json
import requests
from google import genai
from google.genai import types
from groq import Groq
from dotenv import load_dotenv

# 1. CONFIGURACIÓN DE PÁGINA Y SEGURIDAD
st.set_page_config(page_title="Agente IA Local v2.0", page_icon="🤖", layout="wide")
load_dotenv()

# Recuperar claves del .env
clave_gemini = os.getenv("GEMINI_API_KEY")
clave_groq = os.getenv("GROQ_API_KEY")

# 2. PROMPT MAESTRO
INSTRUCCIONES_SISTEMA = """
Actúa como un Senior Software Engineer y Tech Lead.
REGLAS: Análisis previo, Código limpio, Seguridad Zero-Trust y Explicación estratégica.
"""

# 3. LÓGICA DE LOS MOTORES (BACKEND)
def consultar_gemini(mensaje, historial_st):
    """Envía el mensaje a Gemini 2.5 Pro."""
    try:
        cliente = genai.Client(api_key=clave_gemini)
        config = types.GenerateContentConfig(system_instruction=INSTRUCCIONES_SISTEMA, temperature=0.7)
        chat = cliente.chats.create(model='gemini-2.5-pro', config=config)
        
        respuesta = chat.send_message_stream(mensaje)
        for fragmento in respuesta:
            yield fragmento.text
    except Exception as e:
        yield f"❌ Error Gemini: {e}"

def consultar_ollama(mensaje, historial_st):
    """Envía el mensaje al motor local de Ollama."""
    url = "http://localhost:11434/api/chat"
    mensajes_ollama = [{"role": "system", "content": INSTRUCCIONES_SISTEMA}]
    for m in historial_st:
        mensajes_ollama.append({"role": m["role"], "content": m["content"]})
    mensajes_ollama.append({"role": "user", "content": mensaje})

    try:
        res = requests.post(url, json={"model": "qwen2.5-coder:3b", "messages": mensajes_ollama, "stream": True}, stream=True)
        for linea in res.iter_lines():
            if linea:
                yield json.loads(linea)["message"]["content"]
    except Exception as e:
        yield f"❌ Error Ollama: {e}"

def consultar_groq(mensaje, historial_st):
    """Envía el mensaje a la API ultrarrápida de Groq usando Llama 3.3."""
    try:
        if not clave_groq:
            yield "❌ ERROR: No se encontró GROQ_API_KEY en el archivo .env"
            return
            
        cliente = Groq(api_key=clave_groq)
        mensajes_groq = [{"role": "system", "content": INSTRUCCIONES_SISTEMA}]
        for m in historial_st:
            mensajes_groq.append({"role": m["role"], "content": m["content"]})
        mensajes_groq.append({"role": "user", "content": mensaje})

        # Utilizamos el modelo actualizado y soportado por Groq
        stream = cliente.chat.completions.create(
            messages=mensajes_groq,
            model="llama-3.3-70b-versatile", 
            temperature=0.7,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"❌ Error Groq: {e}"

# 4. INTERFAZ DE USUARIO (FRONTEND)
st.title("🤖 Agente de IA Híbrido v2.0")

# Sidebar para configuración
with st.sidebar:
    st.header("Configuración")
    motor_elegido = st.selectbox("Elige el Cerebro:", [
        "Gemini 2.5 Pro (Cloud)", 
        "Groq Llama 3.3 (Ultra-rápido)",
        "Ollama Qwen (Local)"
    ])
    st.divider()
    archivo_subido = st.file_uploader("📁 Adjuntar archivo para analizar", type=['py', 'js', 'txt', 'html', 'css', 'env'])
    if st.button("Limpiar Chat"):
        st.session_state.messages = []
        st.rerun()

# Inicializar historial en la sesión
if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar mensajes previos
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# CAJA DE ENTRADA
if prompt := st.chat_input("¿En qué puedo ayudarte hoy?"):
    
    # Manejo de archivos adjuntos y adición al contexto
    contexto_archivo = ""
    if archivo_subido is not None:
        contenido = archivo_subido.read().decode("utf-8")
        contexto_archivo = f"\n\n[ARCHIVO ADJUNTO: {archivo_subido.name}]\n{contenido}\n"
    
    prompt_final = prompt + contexto_archivo

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        
        # Enrutamiento al motor seleccionado
        if "Gemini" in motor_elegido:
            generador = consultar_gemini(prompt_final, st.session_state.messages[:-1])
        elif "Groq" in motor_elegido:
            generador = consultar_groq(prompt_final, st.session_state.messages[:-1])
        else:
            generador = consultar_ollama(prompt_final, st.session_state.messages[:-1])
            
        # Imprimir en pantalla en tiempo real (streaming)
        for chunk in generador:
            full_response += chunk
            response_placeholder.markdown(full_response + "▌")
        
        response_placeholder.markdown(full_response)
    
    st.session_state.messages.append({"role": "assistant", "content": full_response})