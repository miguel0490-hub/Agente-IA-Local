import os
import json
import threading
from src.database import get_chat_messages, save_chat_messages, delete_chat

# Tokens/Límites de Seguridad (Aprox. 4 chars por token)
MAX_HISTORIAL_MENSAJES = 20
MENSAJES_A_MANTENER_INTACTOS = 8 

def cargar_memoria(chat_id: int) -> list:
    """Carga el historial de chat desde la base de datos."""
    if not chat_id:
        return []
    try:
        return get_chat_messages(chat_id)
    except Exception as e: 
        print(f"Error cargando memoria de DB: {e}")
        return []

def guardar_memoria(chat_id: int, mensajes: list, api_keys: dict = None):
    """Guarda el historial de chat en la base de datos de forma asíncrona."""
    if not chat_id:
        return

    # Hacemos una copia profunda superficial para evitar race conditions en Streamlit
    mensajes_copy = list(mensajes)
    
    def _guardar_background(c_id, msgs, keys):
        mensajes_optimizados = _optimizar_ventana_deslizante(msgs, keys)
        try:
            save_chat_messages(c_id, mensajes_optimizados)
        except Exception as e:
            print(f"Error guardando memoria en DB: {e}")
            
    threading.Thread(target=_guardar_background, args=(chat_id, mensajes_copy, api_keys), daemon=True).start()

def limpiar_memoria(chat_id: int):
    """Borra el chat de la base de datos."""
    if chat_id:
        try:
            # Eliminar todos los mensajes del chat
            save_chat_messages(chat_id, [])
        except Exception as e:
            print(f"Error limpiando chat: {e}")

def _optimizar_ventana_deslizante(mensajes: list, api_keys: dict) -> list:
    """
    Mecanismo de 'Context Window Protection' (SoC):
    Si el número de mensajes excede el límite, extrae los más antiguos,
    usa Groq para comprimirlos en un solo bloque de resumen y mantiene los recientes.
    """
    if not mensajes or len(mensajes) <= MAX_HISTORIAL_MENSAJES:
        return mensajes

    # 1. Separar un posible resumen previo
    resumen_anterior = ""
    idx_inicio = 0

    if mensajes[0].get("role") == "system" and "CONTEXTO HISTÓRICO:" in mensajes[0].get("content", ""):
        resumen_anterior = mensajes[0]["content"]
        idx_inicio = 1

    # 2. Dividir la ventana: Qué se queda y qué se resume
    mensajes_recientes = mensajes[-MENSAJES_A_MANTENER_INTACTOS:]
    mensajes_para_resumir = mensajes[idx_inicio:-MENSAJES_A_MANTENER_INTACTOS]
    
    if not mensajes_para_resumir:
        return mensajes

    # 3. Preparar el payload de compresión (truncando archivos gigantes)
    texto_a_resumir = f"{resumen_anterior}\n" if resumen_anterior else ""
    for msg in mensajes_para_resumir:
        rol = msg.get("role", "unknown")
        # Extraemos máximo 1500 caracteres por mensaje para no saturar al resumidor
        contenido = msg.get("content", "")[:1500] 
        texto_a_resumir += f"[{rol.upper()}]: {contenido}\n"

    prompt_compresion = (
        "Actúa como un procesador de memoria de estado. "
        "Resume la siguiente conversación pasada en un solo párrafo extremadamente denso y conciso. "
        "Conserva SOLO información crítica: decisiones de código, contexto de negocio, y tecnologías mencionadas.\n\n"
        f"CONVERSACIÓN A COMPRIMIR:\n{texto_a_resumir}"
    )

    try:
        from src.services.llm_provider import GroqProvider
        groq_key = api_keys.get("GROQ_API_KEY") if api_keys else None
        if not groq_key:
            raise ValueError("Sin Groq API Key para comprimir memoria")
            
        provider = GroqProvider(api_key=groq_key)
        
        # Llamada síncrona al stream de Groq
        generador = provider.stream_chat(prompt_compresion, [])
        nuevo_resumen = "".join([chunk for chunk in generador if chunk])
        
        if "❌" in nuevo_resumen or not nuevo_resumen.strip():
            raise ValueError("El LLM falló al resumir.")

        mensaje_resumen = {
            "role": "system",
            "content": f"CONTEXTO HISTÓRICO: {nuevo_resumen.strip()}"
        }

        # 4. Retornar el Estado Inmutable (Resumen + Recientes)
        return [mensaje_resumen] + mensajes_recientes

    except Exception as e_groq:
        print(f"[ALERTA DE SISTEMA] Fallo en Groq ({e_groq}). Iniciando failover a Gemini...")
        try:
            from src.services.llm_provider import GeminiProvider
            gemini_key = api_keys.get("GEMINI_API_KEY") if api_keys else None
            if not gemini_key:
                raise ValueError("Sin Gemini API Key para comprimir memoria")
                
            provider_gemini = GeminiProvider(api_key=gemini_key)
            
            generador_gemini = provider_gemini.stream_chat(prompt_compresion, [])
            nuevo_resumen_gemini = "".join([chunk for chunk in generador_gemini if chunk])
            
            if "❌" in nuevo_resumen_gemini or not nuevo_resumen_gemini.strip():
                raise ValueError("Gemini falló al resumir.")

            mensaje_resumen = {
                "role": "system",
                "content": f"CONTEXTO HISTÓRICO: {nuevo_resumen_gemini.strip()}"
            }
            return [mensaje_resumen] + mensajes_recientes
            
        except Exception as e_gemini:
            print(f"[CRÍTICO] Fallo total en LLMs (Groq y Gemini). Ejecutando poda en crudo. Error: {e_gemini}")
            # Degradación Elegante: Ambos motores caídos, podamos el array.
            return mensajes[-MAX_HISTORIAL_MENSAJES:]
