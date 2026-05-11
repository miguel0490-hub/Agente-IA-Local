import os
import io
import tempfile
from pathlib import Path
from typing import Optional

_GROQ_STT_MODEL = "whisper-large-v3"
_OPENAI_TTS_MODEL = "tts-1"
_OPENAI_TTS_DEFAULT_VOICE = "alloy"  # Opciones: alloy, echo, fable, onyx, nova, shimmer
_AUDIO_OUTPUT_DIR = Path("generated_images")  # Reutilizamos carpeta de assets generados

def _polish_transcript_with_llm(raw_text: str, api_key: str) -> str:
    """Toma un texto en bruto (sin puntuación) y lo pulsa usando Llama 3."""
    if not raw_text.strip() or not api_key:
        return raw_text
    
    try:
        from groq import Groq
        cliente = Groq(api_key=api_key)
        
        system_prompt = (
            "Eres un editor experto en transcripciones. Tu única tarea es tomar el texto "
            "que te proporciono y añadirle la puntuación correcta (puntos, comas, signos de interrogación) "
            "y mayúsculas. IMPORTANTE: No resumas, no cambies las palabras del usuario y no añadidas comentarios. "
            "Solo devuelve el texto corregido."
        )
        
        estimated_tokens = max(256, len(raw_text) // 3 + 128)
        response = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Puntúa este texto: {raw_text}"}
            ],
            temperature=0,
            max_tokens=estimated_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return raw_text

def transcribe_audio_with_groq(audio_bytes: bytes, api_key: str, filename: str = "audio.webm") -> tuple[str, Optional[str]]:
    try:
        if not api_key:
            return "", "❌ Funcionalidad omitida durante el onboarding por falta de clave (Groq Whisper). Por favor, actualiza tu perfil."

        from groq import Groq
        cliente = Groq(api_key=api_key)
        audio_file_tuple = (filename, io.BytesIO(audio_bytes), _infer_mime_type(filename))
        prompt_estilo = "Puntuación: puntos, comas y mayúsculas correctamente aplicadas."

        transcription = cliente.audio.transcriptions.create(
            model=_GROQ_STT_MODEL,
            file=audio_file_tuple,
            prompt=prompt_estilo,
            temperature=0,
            response_format="text"
        )

        result_text = transcription if isinstance(transcription, str) else transcription.text
        
        if result_text.strip():
            result_text = _polish_transcript_with_llm(result_text, api_key)
            
        return result_text.strip(), None

    except Exception as api_error:
        return "", f"❌ Error en Groq Whisper STT: {api_error}"

def _infer_mime_type(filename: str) -> str:
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

def synthesize_speech_with_openai(
    text: str,
    api_key: str,
    voice: str = _OPENAI_TTS_DEFAULT_VOICE,
    output_filename: Optional[str] = None
) -> tuple[Optional[bytes], Optional[str], Optional[str]]:
    try:
        if not api_key:
            return None, None, "❌ Funcionalidad omitida durante el onboarding por falta de clave (OpenAI TTS). Por favor, actualiza tu perfil."

        _TTS_CHAR_LIMIT = 4096
        if len(text) > _TTS_CHAR_LIMIT:
            import logging
            logging.getLogger(__name__).warning(
                "TTS text truncated from %d to %d characters", len(text), _TTS_CHAR_LIMIT
            )
            text = text[:_TTS_CHAR_LIMIT]

        from openai import OpenAI
        cliente = OpenAI(api_key=api_key)

        response = cliente.audio.speech.create(
            model=_OPENAI_TTS_MODEL,
            voice=voice,
            input=text,
            response_format="mp3"
        )

        audio_bytes = response.content
        _AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        if not output_filename:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"tts_{timestamp}.mp3"

        saved_path = _AUDIO_OUTPUT_DIR / output_filename
        saved_path.write_bytes(audio_bytes)

        return audio_bytes, str(saved_path), None

    except Exception as api_error:
        return None, None, f"❌ Error en OpenAI TTS: {api_error}"

def synthesize_speech_with_edge(
    text: str,
    voice: str = "es-ES-AlvaroNeural",
    output_filename: Optional[str] = None
) -> tuple[Optional[bytes], Optional[str], Optional[str]]:
    try:
        import asyncio
        import edge_tts
        
        _AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        if not output_filename:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"tts_edge_{timestamp}.mp3"
            
        saved_path = _AUDIO_OUTPUT_DIR / output_filename
        
        async def _run_edge():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(saved_path))
            
        asyncio.run(_run_edge())
        
        audio_bytes = saved_path.read_bytes()
        return audio_bytes, str(saved_path), None
        
    except Exception as e:
        return None, None, f"❌ Error en Edge TTS: {e}"

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
