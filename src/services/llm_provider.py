"""
src/services/llm_provider.py — Capa de Abstracción de Proveedores LLM.

Implementa un patrón Wrapper/Adapter para desacoplar la UI de los SDKs
específicos de cada proveedor: Gemini, Groq, OpenRouter y endpoints
compatibles con la API de OpenAI. También incluye wrappers de audio
(Transcripción Whisper, Síntesis TTS).
"""
import os
import datetime
import json
import re

import requests
import google.genai as ggenai
from google.genai import types
from groq import Groq
from openai import OpenAI

from src.core.config import CARPETA_IMAGENES, PROMPT_TECH_LEAD


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def _continuation_prompt() -> str:
    return (
        "Continúa exactamente desde donde te quedaste, sin repetir contenido, "
        "manteniendo formato y contexto."
    )


def _clean_model_noise(text: str) -> str:
    if not text:
        return ""
    # Limpia prefijos de rol residuales frecuentes de modelos.
    return re.sub(r"(?im)^\s*(agt|agent|assistant|asistente)\s*:\s*", "", text)


class LLMProvider:
    """Clase base (Wrapper) para proveedores de modelos de lenguaje."""

    def __init__(self, api_key=None):
        self.api_key = api_key

    def stream_chat(self, mensaje: str, historial: list, system_instruction: str = None):
        """Interfaz de streaming. Debe ser implementada por cada subclase."""
        raise NotImplementedError


class GeminiProvider(LLMProvider):
    """Proveedor Google Gemini con soporte multimodal (texto + imagen) y streaming."""
    def stream_chat(self, carga_util, historial=None, system_instruction: str = None):
        if not self.api_key:
            yield "❌ Funcionalidad omitida durante el onboarding por falta de clave (Gemini). Por favor, actualiza tu perfil."
            return
            
        try:
            cliente = ggenai.Client(api_key=self.api_key)
            model_name = 'gemini-2.5-pro'

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
                temperature=_env_float("GEMINI_TEMPERATURE", 0.2),
                max_output_tokens=_env_int("GEMINI_MAX_TOKENS", 8192),
                safety_settings=safety_settings
            )

            chat = cliente.chats.create(model=model_name, config=config)
            for frag in chat.send_message_stream(carga_util):
                if frag.text is not None:
                    yield _clean_model_noise(frag.text)
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
    """Proveedor Groq con soporte de streaming sobre modelos LLaMA de alta velocidad."""

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
            preferred_model = os.getenv("GROQ_MODEL", self.model)
            fallback_model = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-70b-versatile")
            candidate_models = [preferred_model]
            if fallback_model and fallback_model != preferred_model:
                candidate_models.append(fallback_model)

            max_tokens = _env_int("GROQ_MAX_TOKENS", 8192)
            temperature = _env_float("GROQ_TEMPERATURE", 0.2)
            max_rounds = max(1, _env_int("GROQ_CONTINUATION_ROUNDS", 2))

            last_error = None
            for model_name in candidate_models:
                try:
                    convo_messages = list(mensajes)
                    for _ in range(max_rounds):
                        streamed_parts = []
                        finish_reason = None
                        stream = cliente.chat.completions.create(
                            model=model_name,
                            messages=convo_messages,
                            stream=True,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        )
                        for chunk in stream:
                            choice = chunk.choices[0]
                            delta_content = choice.delta.content
                            if delta_content:
                                streamed_parts.append(delta_content)
                                yield _clean_model_noise(delta_content)
                            if getattr(choice, "finish_reason", None):
                                finish_reason = choice.finish_reason

                        full_round = "".join(streamed_parts).strip()
                        if finish_reason != "length" or not full_round:
                            return

                        convo_messages.append({"role": "assistant", "content": full_round})
                        convo_messages.append({"role": "user", "content": _continuation_prompt()})
                    return
                except Exception as inner_e:
                    last_error = inner_e
                    continue
            raise last_error if last_error else RuntimeError("No se pudo inicializar Groq.")
        except Exception as e:
            raise


class OpenRouterProvider(LLMProvider):
    """Proveedor OpenRouter: acceso unificado a múltiples LLMs vía API compatible con OpenAI."""
    def stream_chat(self, mensaje: str, historial: list, system_instruction: str = None):
        if not self.api_key:
            yield "❌ Funcionalidad omitida durante el onboarding por falta de clave (OpenRouter). Por favor, actualiza tu perfil."
            return

        try:
            cliente = OpenAI(
                api_key=self.api_key,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": "https://superagenteiapro.com",
                    "X-Title": "SuperAgente IA Pro"
                }
            )
            mensajes = [{"role": "system", "content": system_instruction or PROMPT_TECH_LEAD}]
            for m in historial:
                if m.get("content"):
                    mensajes.append({"role": m["role"], "content": m["content"]})
            mensajes.append({"role": "user", "content": mensaje})

            # Modelo configurable + fallback robusto para evitar caídas por modelos retirados.
            preferred_model = os.getenv("OPENROUTER_MODEL", "openrouter/auto")
            max_tokens = _env_int("OPENROUTER_MAX_TOKENS", 8192)
            temperature = _env_float("OPENROUTER_TEMPERATURE", 0.2)
            max_rounds = max(1, _env_int("OPENROUTER_CONTINUATION_ROUNDS", 2))
            candidate_models = [preferred_model]
            if preferred_model != "openrouter/auto":
                candidate_models.append("openrouter/auto")

            last_error = None
            for model_name in candidate_models:
                try:
                    convo_messages = list(mensajes)
                    for _ in range(max_rounds):
                        streamed_parts = []
                        finish_reason = None
                        stream = cliente.chat.completions.create(
                            model=model_name,
                            messages=convo_messages,
                            stream=True,
                            max_tokens=max_tokens,
                            temperature=temperature
                        )
                        for chunk in stream:
                            choice = chunk.choices[0]
                            if choice.delta.content:
                                streamed_parts.append(choice.delta.content)
                                yield _clean_model_noise(choice.delta.content)
                            if getattr(choice, "finish_reason", None):
                                finish_reason = choice.finish_reason

                        full_round = "".join(streamed_parts).strip()
                        if finish_reason != "length" or not full_round:
                            return

                        convo_messages.append({"role": "assistant", "content": full_round})
                        convo_messages.append({"role": "user", "content": _continuation_prompt()})
                    return
                except Exception as inner_e:
                    last_error = inner_e
                    continue

            raise last_error if last_error else RuntimeError("No se pudo inicializar OpenRouter.")
        except Exception as e:
            yield f"\n\n❌ Error OpenRouter: {e}"


class OllamaProvider(LLMProvider):
    """Compatibilidad legacy: proveedor para Ollama local."""

    def __init__(self, model_name: str | None = None, base_url: str | None = None):
        super().__init__(api_key=os.getenv("OLLAMA_API_KEY", "ollama-local"))
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "llama3.1")
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

    def stream_chat(self, mensaje: str, historial: list, system_instruction: str = None):
        try:
            cliente = OpenAI(api_key=self.api_key, base_url=self.base_url)
            mensajes = [{"role": "system", "content": system_instruction or PROMPT_TECH_LEAD}]
            for m in historial:
                if m.get("content"):
                    mensajes.append({"role": m["role"], "content": m["content"]})
            mensajes.append({"role": "user", "content": mensaje})

            stream = cliente.chat.completions.create(
                model=self.model_name,
                messages=mensajes,
                stream=True,
                max_tokens=_env_int("OLLAMA_MAX_TOKENS", 8192),
                temperature=_env_float("OLLAMA_TEMPERATURE", 0.2),
            )
            for chunk in stream:
                delta_content = chunk.choices[0].delta.content
                if delta_content:
                    yield _clean_model_noise(delta_content)
        except Exception as e:
            yield f"\n\n❌ Error Ollama: {e}"


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
            mensajes = [{"role": "system", "content": system_instruction or PROMPT_TECH_LEAD}]
            for m in historial:
                if m.get("content"):
                    mensajes.append({"role": m["role"], "content": m["content"]})
            mensajes.append({"role": "user", "content": mensaje})

            stream = cliente.chat.completions.create(
                model=self.model_name,
                messages=mensajes,
                stream=True,
                max_tokens=_env_int("CUSTOM_OPENAI_MAX_TOKENS", 8192),
                temperature=_env_float("CUSTOM_OPENAI_TEMPERATURE", 0.2),
            )
            for chunk in stream:
                delta_content = chunk.choices[0].delta.content
                if delta_content:
                    yield _clean_model_noise(delta_content)
        except Exception as e:
            error_str = str(e)
            if "402" in error_str or "Insufficient Balance" in error_str:
                yield f"\n\n⚠️ Error 402: No tienes saldo suficiente en este proveedor. Por favor, recarga tu cuenta en su sitio oficial."
            else:
                yield f"\n\n❌ Error en modelo personalizado '{self.model_name}': {e}"


class GroqWhisperProvider:
    """Wrapper de transcripción de audio usando Groq Whisper v3."""

    def __init__(self, api_key=None):
        self.api_key = api_key

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> tuple[str, str | None]:
        if not self.api_key:
            return "", "❌ Funcionalidad omitida durante el onboarding por falta de clave (Groq Whisper). Por favor, actualiza tu perfil."
        from src.services.audio_service import transcribe_audio_with_groq
        return transcribe_audio_with_groq(audio_bytes, self.api_key, filename)


class OpenAITTSProvider:
    """Sintetizador de voz usando la API Text-to-Speech de OpenAI."""

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
    """Sintetizador de voz gratuito usando Microsoft Edge TTS (sin API key)."""

    def __init__(self, voice: str = "es-ES-AlvaroNeural"):
        self.voice = voice

    def synthesize(self, text: str) -> tuple[bytes | None, str | None, str | None]:
        from src.services.audio_service import synthesize_speech_with_edge
        return synthesize_speech_with_edge(text, voice=self.voice)


class LLMFactory:
    """Factoría centralizada para instanciar proveedores LLM."""
    
    @staticmethod
    def get_provider(motor_name: str, api_keys: dict):
        if "Gemini" in motor_name:
            from src.services.llm_provider import GeminiProvider
            return GeminiProvider(api_key=api_keys.get("GEMINI_API_KEY"))
            
        elif "Groq" in motor_name and "Whisper" not in motor_name:
            from src.services.llm_provider import GroqProvider
            return GroqProvider(api_key=api_keys.get("GROQ_API_KEY"))
            
        elif "OpenRouter" in motor_name:
            from src.services.llm_provider import OpenRouterProvider
            return OpenRouterProvider(api_key=api_keys.get("OPENROUTER_API_KEY"))
            
        else:
            custom_models = api_keys.get("CUSTOM_MODELS", [])
            matched_custom = next((cm for cm in custom_models if f"🤖 {cm['name']}" == motor_name), None)
            
            if matched_custom:
                from src.services.llm_provider import CustomOpenAIProvider
                return CustomOpenAIProvider(
                    base_url=matched_custom["base_url"],
                    api_key=matched_custom["api_key"],
                    model_name=matched_custom["model_id"],
                )
            
            from src.services.llm_provider import OpenRouterProvider
            return OpenRouterProvider(api_key=api_keys.get("OPENROUTER_API_KEY"))