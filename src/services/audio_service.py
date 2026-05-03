"""
audio_service.py
================
Capa de servicios para capacidades de Audio del Agente.

Responsabilidades:
  - STT (Speech-to-Text): Groq Whisper API → whisper-large-v3
  - TTS (Text-to-Speech): OpenAI TTS API → tts-1

Principio de diseño:
  Cada función es autónoma y delega ÚNICAMENTE a su API externa.
  El caller (app.py) NO debe conocer detalles de implementación de HTTP.
"""

import os
import io
import tempfile
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(override=True)

# ─── Constantes de Configuración ───────────────────────────────────────────────
_GROQ_STT_MODEL = "whisper-large-v3"
_OPENAI_TTS_MODEL = "tts-1"
_OPENAI_TTS_DEFAULT_VOICE = "alloy"  # Opciones: alloy, echo, fable, onyx, nova, shimmer
_AUDIO_OUTPUT_DIR = Path("generated_images")  # Reutilizamos carpeta de assets generados


# ─── Helpers privados ──────────────────────────────────────────────────────────

def _polish_transcript_with_llm(raw_text: str, api_key: str) -> str:
    """
    Toma un texto en bruto (sin puntuación) y lo pulsa usando Llama 3.
    """
    if not raw_text.strip():
        return ""
    
    try:
        from groq import Groq
        cliente = Groq(api_key=api_key)
        
        system_prompt = (
            "Eres un editor experto en transcripciones. Tu única tarea es tomar el texto "
            "que te proporciono y añadirle la puntuación correcta (puntos, comas, signos de interrogación) "
            "y mayúsculas. IMPORTANTE: No resumas, no cambies las palabras del usuario y no añadidas comentarios. "
            "Solo devuelve el texto corregido."
        )
        
        response = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile", # Usamos el modelo más potente para precisión
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Puntúa este texto: {raw_text}"}
            ],
            temperature=0,
            max_tokens=len(raw_text) + 100
        )
        return response.choices[0].message.content.strip()
    except Exception:
        # Si falla el pulido, devolvemos el original para no perder datos
        return raw_text


def _require_env_key(var_name: str) -> str:
    """Valida y retorna una variable de entorno. Lanza ValueError si no existe."""
    value = os.getenv(var_name)
    if not value:
        raise ValueError(
            f"❌ Variable de entorno '{var_name}' no encontrada. "
            f"Añádela a tu archivo .env para usar esta funcionalidad."
        )
    return value


# ─── Servicio STT: Groq Whisper ────────────────────────────────────────────────

def transcribe_audio_with_groq(audio_bytes: bytes, filename: str = "audio.webm") -> tuple[str, Optional[str]]:
    """
    Transcribe un archivo de audio a texto usando la API de Groq (Whisper Large v3).

    Args:
        audio_bytes: Contenido binario del archivo de audio.
        filename: Nombre original del archivo (para que la API infiera el formato).

    Returns:
        Tuple (transcription_text, error_message).
        Si hay éxito, error_message es None.
        Si hay error, transcription_text es "" y error_message contiene la descripción.
    """
    try:
        clave_groq = _require_env_key("GROQ_API_KEY")

        from groq import Groq
        cliente = Groq(api_key=clave_groq)

        # La API de Groq espera un objeto tipo archivo con nombre
        audio_file_tuple = (filename, io.BytesIO(audio_bytes), _infer_mime_type(filename))

        # Prompt de estilo: Whisper usa esto para entender el FORMATO, no como instrucción.
        # Al poner un texto con puntuación, le obligamos a seguir ese patrón.
        prompt_estilo = "Puntuación: puntos, comas y mayúsculas correctamente aplicadas."

        transcription = cliente.audio.transcriptions.create(
            model=_GROQ_STT_MODEL,
            file=audio_file_tuple,
            prompt=prompt_estilo,      # Prompt corto y estilístico
            temperature=0,             # Temperatura 0 para evitar alucinaciones
            response_format="text"
        )

        # groq SDK devuelve el texto directamente cuando response_format="text"
        result_text = transcription if isinstance(transcription, str) else transcription.text
        
        # [NUEVO] Paso de pulido con LLM para asegurar puntuación perfecta
        if result_text.strip():
            result_text = _polish_transcript_with_llm(result_text, clave_groq)
            
        return result_text.strip(), None

    except ValueError as config_error:
        return "", str(config_error)
    except Exception as api_error:
        return "", f"❌ Error en Groq Whisper STT: {api_error}"


def _infer_mime_type(filename: str) -> str:
    """Infiere el MIME type a partir de la extensión del archivo de audio."""
    extension_to_mime = {
        ".mp3": "audio/mpeg",
        ".mp4": "audio/mp4",
        ".wav": "audio/wav",
        ".webm": "audio/webm",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
    }
    ext = Path(filename).suffix.lower()
    return extension_to_mime.get(ext, "audio/mpeg")


# ─── Servicio TTS: OpenAI ──────────────────────────────────────────────────────

def synthesize_speech_with_openai(
    text: str,
    voice: str = _OPENAI_TTS_DEFAULT_VOICE,
    output_filename: Optional[str] = None
) -> tuple[Optional[bytes], Optional[str], Optional[str]]:
    """
    Convierte texto a voz usando la API de OpenAI TTS (modelo tts-1).

    Args:
        text: El texto que se va a sintetizar (máx. 4096 caracteres por request).
        voice: Voz a usar. Opciones: alloy, echo, fable, onyx, nova, shimmer.
        output_filename: Nombre de archivo para persistir el audio. Si es None,
                         se genera uno automático.

    Returns:
        Tuple (audio_bytes, saved_filepath, error_message).
        - audio_bytes: Bytes del MP3 generado (para streaming/descarga directa).
        - saved_filepath: Ruta donde se guardó el archivo (string o None).
        - error_message: Descripción del error si falló, None si tuvo éxito.
    """
    try:
        clave_openai = _require_env_key("OPENAI_API_KEY")

        # Límite de caracteres del modelo tts-1
        if len(text) > 4096:
            text = text[:4096]

        from openai import OpenAI
        cliente = OpenAI(api_key=clave_openai)

        response = cliente.audio.speech.create(
            model=_OPENAI_TTS_MODEL,
            voice=voice,
            input=text,
            response_format="mp3"
        )

        audio_bytes = response.content

        # Persistir el archivo en disco para permitir descarga posterior
        _AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        if not output_filename:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"tts_{timestamp}.mp3"

        saved_path = _AUDIO_OUTPUT_DIR / output_filename
        saved_path.write_bytes(audio_bytes)

        return audio_bytes, str(saved_path), None

    except ValueError as config_error:
        return None, None, str(config_error)
    except Exception as api_error:
        return None, None, f"❌ Error en OpenAI TTS: {api_error}"


# ─── Servicio TTS: Edge TTS (GRATUITO) ──────────────────────────────────────────

def synthesize_speech_with_edge(
    text: str,
    voice: str = "es-ES-AlvaroNeural", # Voces: es-ES-AlvaroNeural, es-MX-DaliaNeural, es-AR-ElenaNeural
    output_filename: Optional[str] = None
) -> tuple[Optional[bytes], Optional[str], Optional[str]]:
    """
    Convierte texto a voz usando Edge-TTS (Gratuito, sin API Key).
    """
    try:
        import asyncio
        import edge_tts
        
        _AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        if not output_filename:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"tts_edge_{timestamp}.mp3"
            
        saved_path = _AUDIO_OUTPUT_DIR / output_filename
        
        # Ejecutar async en un entorno síncrono
        async def _run_edge():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(saved_path))
            
        asyncio.run(_run_edge())
        
        audio_bytes = saved_path.read_bytes()
        return audio_bytes, str(saved_path), None
        
    except Exception as e:
        return None, None, f"❌ Error en Edge TTS: {e}"


# ─── Constantes públicas para el frontend ─────────────────────────────────────

AVAILABLE_TTS_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
AVAILABLE_EDGE_VOICES = {
    "🇪🇸 Álvaro (España)": "es-ES-AlvaroNeural",
    "🇪🇸 Elvira (España)": "es-ES-ElviraNeural",
    "🇲🇽 Dalia (México)": "es-MX-DaliaNeural",
    "🇲🇽 Jorge (México)": "es-MX-JorgeNeural",
    "🇦🇷 Elena (Argentina)": "es-AR-ElenaNeural",
    "🇦🇷 Tomas (Argentina)": "es-AR-TomasNeural",
}
SUPPORTED_AUDIO_FORMATS = [".mp3", ".mp4", ".wav", ".webm", ".ogg", ".flac", ".m4a"]
