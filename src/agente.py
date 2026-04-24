import os
import sys
import json
import requests
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 1. INICIALIZAR SEGURIDAD Y CLAVES
load_dotenv()
clave_gemini = os.getenv("GEMINI_API_KEY")

# 2. EL PROMPT MAESTRO
INSTRUCCIONES_SISTEMA = """
Actúa como un Senior Software Engineer, Experto en Ciberseguridad y Tech Lead personal.
Tu misión es ser mi asistente diario para resolver problemas de código, diseñar arquitecturas y crear scripts desde cero en cualquier lenguaje o framework que necesite.

REGLAS INQUEBRANTABLES:
1. ANÁLISIS PREVIO: Antes de escribir código, analiza el problema paso a paso y determina la mejor solución técnica.
2. CÓDIGO LIMPIO Y ESCALABLE: Aplica principios de código limpio, divide la lógica en funciones pequeñas y usa una nomenclatura clara y autodescriptiva.
3. SEGURIDAD "ZERO-TRUST": Jamás expongas, solicites o simules contraseñas, API Keys, URLs de bases de datos o tokens. Todo dato confidencial debe manejarse siempre mediante variables de entorno.
4. EXPLICACIÓN ESTRATÉGICA: Comenta el código para explicar el "por qué" de lógicas complejas, no lo evidente.
5. VERSATILIDAD: Adapta tus soluciones al lenguaje, framework o entorno específico que te solicite en cada momento.

ESTRUCTURA DE TU RESPUESTA:
- 💡 Análisis: [Tu diagnóstico o enfoque técnico]
- 🛠️ Código: [Bloque de código formateado, modular y listo para usar]
- 🛡️ Notas: [Breves indicaciones sobre dependencias, seguridad o ejecución]
"""

# Variable global para mantener viva la conexión con la API de Google
cliente_gemini = None

# 3. FUNCIONES DE CONEXIÓN A LOS MOTORES
def iniciar_gemini():
    """Configura y devuelve una sesión de chat con el SDK de Gemini."""
    global cliente_gemini 
    
    if not clave_gemini:
        print("❌ ERROR: No se encontró GEMINI_API_KEY en el archivo .env")
        sys.exit()
    
    # Inicializamos el cliente oficial de Google
    cliente_gemini = genai.Client(api_key=clave_gemini)
    
    configuracion = types.GenerateContentConfig(
        system_instruction=INSTRUCCIONES_SISTEMA,
        temperature=0.7
    )
    
    # Endpoint oficial y estable acordado: Gemini 2.5 Pro
    return cliente_gemini.chats.create(model='gemini-2.5-pro', config=configuracion)

def consultar_gemini(chat_session, mensaje_usuario):
    """Envía el mensaje a Gemini y lo imprime en tiempo real (streaming)."""
    try:
        respuesta = chat_session.send_message_stream(mensaje_usuario)
        for fragmento in respuesta:
            print(fragmento.text, end="", flush=True)
        print("\n")
    except Exception as error:
        print(f"\n❌ Error crítico al conectar con Gemini: {error}")

def consultar_ollama(historial, mensaje_usuario):
    """Envía el mensaje al motor local de Ollama y lo imprime en tiempo real."""
    url_local = "http://localhost:11434/api/chat"
    historial.append({"role": "user", "content": mensaje_usuario})
    
    paquete_datos = {
        "model": "qwen2.5-coder:3b", 
        "messages": historial,
        "stream": True 
    }
    
    respuesta_completa = ""
    try:
        respuesta = requests.post(url_local, json=paquete_datos, stream=True)
        respuesta.raise_for_status()
        
        for linea in respuesta.iter_lines():
            if linea:
                texto = json.loads(linea)["message"]["content"]
                print(texto, end="", flush=True)
                respuesta_completa += texto
                
        print("\n")
        historial.append({"role": "assistant", "content": respuesta_completa})
        
    except requests.exceptions.RequestException as error:
        print(f"\n❌ Error crítico al conectar con el motor local: {error}")
        historial.pop() 

# 4. INTERFAZ DE TERMINAL Y MENÚ DE SELECCIÓN
if __name__ == "__main__":
    print("===================================================")
    print("        🤖 AGENTE DE IA HÍBRIDO INICIADO           ")
    print("===================================================")
    print(" Selecciona el motor para esta sesión de código:   ")
    print("  1. Modo Local (Ollama - Privado y sin internet)  ")
    print("  2. Modo Cloud (Gemini 2.5 Pro - Potencia Máxima) ")
    print("===================================================\n")
    
    modo = input("Elige una opción (1 o 2): ").strip()
    
    if modo == "1":
        print("\n🟢 Iniciando motor local (Qwen 3B)...")
        motor_actual = "local"
        historial_local = [{"role": "system", "content": INSTRUCCIONES_SISTEMA}]
    elif modo == "2":
        print("\n🔵 Conectando con servidores de Google (Gemini 2.5 Pro)...")
        motor_actual = "gemini"
        chat_gemini = iniciar_gemini()
    else:
        print("Opción no válida. Cerrando los protocolos del agente.")
        sys.exit()

    print("\n--- Sistema listo. Escribe tu mensaje, pulsa Enter y luego escribe 'ENVIAR' en una nueva línea para procesar. Escribe 'salir' para terminar. ---\n")

    while True:
        print("Tú > ")
        lineas_usuario = []
        
        while True:
            linea = input()
            if linea.strip() == 'ENVIAR':
                break
            lineas_usuario.append(linea)
            
        usuario = "\n".join(lineas_usuario)
        
        if usuario.strip().lower() in ['salir', 'exit', 'quit']:
            print("Cerrando los protocolos del agente. ¡Buen código!")
            sys.exit()
            
        if usuario.strip() == "":
            continue
            
        print("\nAgente > ", end="")
        
        if motor_actual == "local":
            consultar_ollama(historial_local, usuario)
        else:
            consultar_gemini(chat_gemini, usuario)