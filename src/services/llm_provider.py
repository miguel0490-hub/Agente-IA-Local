import os
import json
import requests
import datetime
import google.genai as ggenai 
from google.genai import types
from groq import Groq

from src.core.config import CARPETA_IMAGENES, PROMPT_TECH_LEAD
from openai import OpenAI

class LLMProvider:
    """Clase base (Wrapper) para proveedores de modelos de lenguaje."""
    def __init__(self, api_key=None):
        self.api_key = api_key

    def stream_chat(self, mensaje: str, historial: list, system_instruction: str = None):
        raise NotImplementedError

class GeminiProvider(LLMProvider):
    def stream_chat(self, carga_util, historial=None, system_instruction: str = None):
        if not self.api_key:
            yield "❌ Funcionalidad omitida durante el onboarding por falta de clave (Gemini). Por favor, actualiza tu perfil."
            return
            
        try:
            cliente = ggenai.Client(api_key=self.api_key)
            model_name = 'gemini-2.5-pro'
            
            # Configuramos los filtros de seguridad al mínimo para evitar que corte el código fuente generado
            safety_settings = [
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
            ]

            config = types.GenerateContentConfig(
                system_instruction=system_instruction or PROMPT_TECH_LEAD, 
                temperature=0.2, # Reducido a 0.2 para código más preciso y menos propenso a errores de formato
                max_output_tokens=8192,
                safety_settings=safety_settings
            )
            
            chat = cliente.chats.create(model=model_name, config=config)
            for frag in chat.send_message_stream(carga_util):
                # Gemini Vision puede emitir fragmentos con text=None durante el procesamiento
                if frag.text is not None:
                    yield frag.text
        except Exception as e: 
            raise
            
    def generar_imagen(self, prompt_artistico: str):
        if not self.api_key: return None, "❌ Funcionalidad omitida durante el onboarding por falta de clave (Gemini). Por favor, actualiza tu perfil."
        try:
            cliente = ggenai.Client(api_key=self.api_key)
            
            resultado = cliente.models.generate_images(
                model='imagen-4.0-generate-001',
                prompt=prompt_artistico,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    output_mime_type="image/png",
                    aspect_ratio="1:1"
                )
            )
            
            if resultado.generated_images:
                image_bytes = resultado.generated_images[0].image.image_bytes
                
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"gen_{timestamp}.png"
                final_path = os.path.join(CARPETA_IMAGENES, filename)
                
                with open(final_path, "wb") as f:
                    f.write(image_bytes)
                    
                return final_path, None 
            else:
                return None, "⚠️ La IA no devolvió una imagen."
                
        except Exception as e:
            return None, f"❌ Error crítico en Generador de Arte: {e}"

class GroqProvider(LLMProvider):
    def __init__(self, api_key=None, model="llama-3.3-70b-versatile"):
        super().__init__(api_key)
        self.model = model

    def stream_chat(self, mensaje: str, historial: list, system_instruction: str = None):
        if not self.api_key:
            yield "❌ Funcionalidad omitida durante el onboarding por falta de clave (Groq). Por favor, actualiza tu perfil."
            return
            
        try:
            cliente = Groq(api_key=self.api_key)
            mensajes = [{"role": "system", "content": system_instruction or PROMPT_TECH_LEAD}]
            for m in historial: 
                if m.get("content"):
                    mensajes.append({"role": m["role"], "content": m["content"]})
            mensajes.append({"role": "user", "content": mensaje})
            stream = cliente.chat.completions.create(
                model=self.model, 
                messages=mensajes, 
                stream=True,
                max_tokens=8192,
                temperature=0.2 # Reducido para mayor precisión en código
            )
            for chunk in stream:
                if chunk.choices[0].delta.content: yield chunk.choices[0].delta.content
        except Exception as e: 
            raise

class OpenRouterProvider(LLMProvider):
    def stream_chat(self, mensaje: str, historial: list, system_instruction: str = None):
        if not self.api_key:
            yield "❌ Funcionalidad omitida durante el onboarding por falta de clave (OpenRouter). Por favor, actualiza tu perfil."
            return

        try:
            cliente = OpenAI(
                api_key=self.api_key,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": "https://superagenteiapro.com",  # Dominio de producción
                    "X-Title": "SuperAgente IA Pro"
                }
            )
            mensajes = [{"role": "system", "content": system_instruction or PROMPT_TECH_LEAD}]
            for m in historial:
                if m.get("content"):
                    mensajes.append({"role": m["role"], "content": m["content"]})
            mensajes.append({"role": "user", "content": mensaje})

            stream = cliente.chat.completions.create(
                model="meta-llama/llama-3-8b-instruct:free",  # Modelo gratuito muy estable
                messages=mensajes,
                stream=True,
                temperature=0.2
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"\n\n❌ Error OpenRouter: {e}"


class CustomOpenAIProvider(LLMProvider):
    """
    Proveedor genérico para cualquier endpoint compatible con la API de OpenAI
    (DeepSeek, LM Studio, vLLM, Mistral AI, Together AI, etc.).

    CRÍTICO: El system_instruction se inyecta SIEMPRE como el primer mensaje
    con rol 'system', garantizando que el modelo reciba las instrucciones de
    uso de herramientas (Tool Calling vía JSON Parsing) igual que los
    proveedores nativos.
    """

    def __init__(self, base_url: str, api_key: str, model_name: str):
        super().__init__(api_key=api_key)
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name

    def stream_chat(self, mensaje: str, historial: list, system_instruction: str = None):
        if not self.api_key:
            yield f"❌ No se configuró API Key para el modelo personalizado '{self.model_name}'."
            return
        if not self.base_url:
            yield f"❌ No se configuró URL Base para el modelo personalizado '{self.model_name}'."
            return

        try:
            cliente = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
            # El system prompt es el primero — esto es lo que activa el tool calling
            mensajes = [{"role": "system", "content": system_instruction or PROMPT_TECH_LEAD}]
            for m in historial:
                if m.get("content"):
                    mensajes.append({"role": m["role"], "content": m["content"]})
            mensajes.append({"role": "user", "content": mensaje})

            stream = cliente.chat.completions.create(
                model=self.model_name,
                messages=mensajes,
                stream=True,
                temperature=0.2,
            )
            for chunk in stream:
                delta_content = chunk.choices[0].delta.content
                if delta_content:
                    yield delta_content
        except Exception as e:
            error_str = str(e)
            if "402" in error_str or "Insufficient Balance" in error_str:
                yield f"\n\n⚠️ Error 402: No tienes saldo suficiente en este proveedor. Por favor, recarga tu cuenta en su sitio oficial."
            else:
                yield f"\n\n❌ Error en modelo personalizado '{self.model_name}': {e}"


class GroqWhisperProvider:
    def __init__(self, api_key=None):
        self.api_key = api_key

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> tuple[str, str | None]:
        if not self.api_key:
            return "", "❌ Funcionalidad omitida durante el onboarding por falta de clave (Groq Whisper). Por favor, actualiza tu perfil."
        from src.services.audio_service import transcribe_audio_with_groq
        return transcribe_audio_with_groq(audio_bytes, self.api_key, filename)


class OpenAITTSProvider:
    VOCES_DISPONIBLES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

    def __init__(self, voice: str = "alloy", api_key=None):
        self.voice = voice if voice in self.VOCES_DISPONIBLES else "alloy"
        self.api_key = api_key

    def synthesize(self, text: str) -> tuple[bytes | None, str | None, str | None]:
        if not self.api_key:
            return None, None, "❌ Funcionalidad omitida durante el onboarding por falta de clave (OpenAI TTS). Por favor, actualiza tu perfil."
        from src.services.audio_service import synthesize_speech_with_openai
        return synthesize_speech_with_openai(text, self.api_key, voice=self.voice)


class EdgeTTSProvider:
    def __init__(self, voice: str = "es-ES-AlvaroNeural"):
        self.voice = voice

    def synthesize(self, text: str) -> tuple[bytes | None, str | None, str | None]:
        from src.services.audio_service import synthesize_speech_with_edge
        return synthesize_speech_with_edge(text, voice=self.voice)