import os
import json
import requests
import datetime
import google.genai as ggenai 
from google.genai import types
from groq import Groq

from src.core.config import (
    CLAVE_GEMINI, CLAVE_GROQ, CLAVE_OPENROUTER, CLAVE_OPENAI,
    CARPETA_IMAGENES, PROMPT_TECH_LEAD
)
from openai import OpenAI

class LLMProvider:
    """Clase base (Wrapper) para proveedores de modelos de lenguaje."""
    def stream_chat(self, mensaje: str, historial: list, system_instruction: str = None):
        raise NotImplementedError

class GeminiProvider(LLMProvider):
    def stream_chat(self, carga_util, historial=None, system_instruction: str = None):
        try:
            cliente = ggenai.Client(api_key=CLAVE_GEMINI)
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
        try:
            if not CLAVE_GEMINI: return None, "❌ Falta Gemini API Key."
            
            cliente = ggenai.Client(api_key=CLAVE_GEMINI)
            
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
    def __init__(self, model="llama-3.3-70b-versatile"):
        self.model = model

    def stream_chat(self, mensaje: str, historial: list, system_instruction: str = None):
        try:
            cliente = Groq(api_key=CLAVE_GROQ)
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

class OllamaProvider(LLMProvider):
    def stream_chat(self, mensaje: str, historial: list, system_instruction: str = None):
        url = "http://localhost:11434/api/chat"
        mensajes = [{"role": "system", "content": system_instruction or PROMPT_TECH_LEAD}]
        for m in historial:
            if m.get("content"):
                mensajes.append({"role": m["role"], "content": m["content"]})
        mensajes.append({"role": "user", "content": mensaje})
        try:
            res = requests.post(url, json={"model": "qwen2.5-coder:3b", "messages": mensajes, "stream": True}, stream=True)
            for linea in res.iter_lines():
                if linea: yield json.loads(linea)["message"]["content"]
        except Exception as e: 
            yield f"\n\n❌ Error Ollama: {e}"

class OpenRouterProvider(LLMProvider):
    def stream_chat(self, mensaje: str, historial: list, system_instruction: str = None):
        try:
            import os
            from dotenv import load_dotenv
            load_dotenv(override=True)
            clave_actual = os.getenv("OPENROUTER_API_KEY")
            
            if not clave_actual:
                yield "❌ Error: No se ha encontrado OPENROUTER_API_KEY en el archivo .env"
                return
                
            cliente = OpenAI(
                api_key=clave_actual,
                base_url="https://openrouter.ai/api/v1",
            )
            mensajes = [{"role": "system", "content": system_instruction or PROMPT_TECH_LEAD}]
            for m in historial: 
                if m.get("content"):
                    mensajes.append({"role": m["role"], "content": m["content"]})
            mensajes.append({"role": "user", "content": mensaje})
            stream = cliente.chat.completions.create(
                model="qwen/qwen3-coder:free",
                messages=mensajes,
                stream=True
            )
            for chunk in stream:
                if chunk.choices[0].delta.content: yield chunk.choices[0].delta.content
        except Exception as e: 
            yield f"\n\n❌ Error OpenRouter: {e}"


class GroqWhisperProvider:
    """
    Wrapper de Groq Whisper para STT (Speech-to-Text).
    Delega completamente en audio_service.transcribe_audio_with_groq.
    Expone un método `transcribe` en lugar de `stream_chat` porque el
    contrato de audio es fundamentalmente diferente al de chat.
    """

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> tuple[str, str | None]:
        """
        Transcribe audio a texto.

        Args:
            audio_bytes: Contenido binario del archivo de audio.
            filename: Nombre del archivo para que la API infiera el formato.

        Returns:
            Tuple (texto_transcrito, error_message). error_message es None si éxito.
        """
        from src.services.audio_service import transcribe_audio_with_groq
        return transcribe_audio_with_groq(audio_bytes, filename)


class OpenAITTSProvider:
    """
    Wrapper de OpenAI TTS para síntesis de voz (Text-to-Speech).
    Delega completamente en audio_service.synthesize_speech_with_openai.
    """

    VOCES_DISPONIBLES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

    def __init__(self, voice: str = "alloy"):
        # Validación defensiva: si la voz no es válida, usamos el default
        self.voice = voice if voice in self.VOCES_DISPONIBLES else "alloy"

    def synthesize(self, text: str) -> tuple[bytes | None, str | None, str | None]:
        """
        Sintetiza texto a audio MP3.

        Args:
            text: El texto a convertir en voz (máx. 4096 caracteres).

        Returns:
            Tuple (audio_bytes, saved_filepath, error_message).
            audio_bytes: Bytes del MP3 (para reproducción directa en Streamlit).
            saved_filepath: Ruta del archivo guardado en disco.
            error_message: None si éxito, descripción del error en caso contrario.
        """
        from src.services.audio_service import synthesize_speech_with_openai
        return synthesize_speech_with_openai(text, voice=self.voice)


class EdgeTTSProvider:
    """
    Wrapper de Edge TTS (Microsoft Edge) para síntesis de voz gratuita.
    No requiere API Key.
    """
    def __init__(self, voice: str = "es-ES-AlvaroNeural"):
        self.voice = voice

    def synthesize(self, text: str) -> tuple[bytes | None, str | None, str | None]:
        from src.services.audio_service import synthesize_speech_with_edge
        return synthesize_speech_with_edge(text, voice=self.voice)