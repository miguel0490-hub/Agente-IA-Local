"""
src/services/llm_provider.py — Capa de Abstracción de Proveedores LLM.

Implementa un patrón Wrapper/Adapter para desacoplar la UI de los SDKs
específicos de cada proveedor: Gemini, Groq, OpenRouter y endpoints
compatibles con la API de OpenAI. También incluye wrappers de audio
(Transcripción Whisper, Síntesis TTS).
"""
import base64
import binascii
import datetime
import os
import re

import requests

from src.core.config import CARPETA_IMAGENES
from src.core.system_prompts import PROMPT_TECH_LEAD
from src.core.i18n import t
from src.services.gemini_models import gemini_model_candidates, is_gemini_model_not_found_error


def _gemini_history_to_genai(historial: list | None) -> list[dict]:
    """Convierte mensajes {role, content} al historial de ``client.chats.create``."""
    out: list[dict] = []
    for m in historial or []:
        role = (m.get("role") or "").strip()
        if role == "assistant":
            role = "model"
        if role not in ("user", "model"):
            continue
        content = (m.get("content") or "").strip()
        if not content:
            continue
        out.append({"role": role, "parts": [{"text": content}]})
    return out


def _gemini_generation_config(
    system_instruction: str,
    *,
    max_tokens: int,
    temperature: float,
):
    from google.genai import types

    safety_settings = [
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
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
    return types.GenerateContentConfig(
        system_instruction=system_instruction,
        max_output_tokens=max_tokens,
        temperature=temperature,
        safety_settings=safety_settings,
    )


def _finish_reason_implies_truncation(finish_reason) -> bool:
    if finish_reason is None:
        return False
    s = str(finish_reason).upper()
    return "MAX" in s or "LENGTH" in s


def _imagen_via_rest(api_key: str, prompt: str) -> tuple[bytes | None, str | None]:
    """Imagen 4 vía REST (misma API pública que documenta Google AI); no requiere google-genai."""
    url = "https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict"
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1, "aspectRatio": "1:1"},
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code >= 400:
            return None, t("llm_art_error", error=f"HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            data = resp.json()
        except ValueError as e:
            return None, t("llm_art_error", error=e)
    except requests.RequestException as e:
        return None, t("llm_art_error", error=e)

    def _extract_b64(obj) -> str | None:
        if isinstance(obj, str) and len(obj) > 80:
            return obj
        if isinstance(obj, dict):
            for k in ("bytesBase64Encoded", "b64", "imageBytes", "image_base64"):
                v = obj.get(k)
                if isinstance(v, str) and len(v) > 80:
                    return v
            for v in obj.values():
                found = _extract_b64(v)
                if found:
                    return found
        if isinstance(obj, list):
            for item in obj:
                found = _extract_b64(item)
                if found:
                    return found
        return None

    b64 = _extract_b64(data.get("predictions") or data)
    if not b64:
        return None, t("llm_gemini_no_image")
    try:
        raw = base64.b64decode(b64, validate=False)
    except (binascii.Error, ValueError) as e:
        return None, t("llm_art_error", error=e)
    if not raw:
        return None, t("llm_gemini_no_image")
    return raw, None


def _lazy_groq():
    """Lazy import for Groq SDK."""
    from groq import Groq
    return Groq


def _lazy_openai():
    """Lazy import for OpenAI SDK."""
    from openai import OpenAI
    return OpenAI


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
    return t("llm_continuation_prompt")


def _clean_model_noise(text: str) -> str:
    if not text:
        return ""
    # Limpia prefijos de rol residuales frecuentes de modelos.
    return re.sub(r"(?im)^\s*(agt|agent|assistant|asistente)\s*:\s*", "", text)


# Sufijo añadido al compactar system prompts en APIs tipo OpenAI (Groq, OpenRouter,
# Ollama, endpoint personalizado). Sin esto, un recorte largo borra query_rag y el
# Cerebro RAG deja de usarse.
def _tool_calling_preserved_suffix() -> str:
    return t("llm_tool_preserved_suffix")


def compact_system_prompt_preserving_tool_docs(prompt: str, max_chars: int) -> str:
    """Recorta el system prompt conservando instrucciones de herramientas (RAG, web, archivos).

    Si ``max_chars`` es <= 0 o el texto ya cabe, no modifica nada. Usado por Groq por
    defecto y de forma opt-in en otros proveedores vía variables de entorno
    (p. ej. ``OPENROUTER_SYSTEM_PROMPT_MAX_CHARS``).
    """
    if max_chars <= 0 or len(prompt) <= max_chars:
        return prompt
    suffix = _tool_calling_preserved_suffix()
    budget = max(400, max_chars - len(suffix))
    cut_markers = [
        "=== REGLAS PARA GENERACIÓN DE DOCUMENTOS PDF",
        "=== REGLAS PARA GENERACIÓN DE TABLAS",
        "=== HERRAMIENTA: CONVERSOR",
        "=== HERRAMIENTA: EDITOR",
    ]
    trimmed = prompt
    for marker in cut_markers:
        idx = trimmed.find(marker)
        if idx != -1:
            trimmed = trimmed[:idx].rstrip()
    if len(trimmed) > budget:
        trimmed = trimmed[:budget].rsplit("\n", 1)[0]
    return trimmed + suffix


def _apply_optional_system_compact(system_instruction: str | None, env_name: str, default_max: int) -> str:
    """Aplica :func:`compact_system_prompt_preserving_tool_docs` según entorno (0 = desactivado)."""
    base = system_instruction or PROMPT_TECH_LEAD
    return compact_system_prompt_preserving_tool_docs(base, _env_int(env_name, default_max))


class LLMProvider:
    """Clase base (Wrapper) para proveedores de modelos de lenguaje."""

    def __init__(self, api_key=None):
        self.api_key = api_key

    def stream_chat(self, mensaje: str, historial: list, system_instruction: str = None):
        """Interfaz de streaming. Debe ser implementada por cada subclase."""
        raise NotImplementedError


class GeminiProvider(LLMProvider):
    """Proveedor Google Gemini (``google.genai``) con multimodal y streaming."""

    def _stream_with_model(
        self,
        client,
        model_name: str,
        carga_util,
        historial,
        system_instruction: str | None,
    ):
        """Generador interno: un modelo concreto y rondas de continuación."""
        sys_inst = system_instruction or PROMPT_TECH_LEAD
        max_tokens = _env_int("GEMINI_MAX_TOKENS", 65536)
        temperature = _env_float("GEMINI_TEMPERATURE", 0.2)
        max_rounds = max(1, _env_int("GEMINI_CONTINUATION_ROUNDS", 3))

        config = _gemini_generation_config(
            sys_inst,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        history = _gemini_history_to_genai(historial)
        chat = client.chats.create(
            model=model_name,
            config=config,
            history=history or None,
        )
        parts = carga_util if isinstance(carga_util, list) else [carga_util]

        for _round in range(max_rounds):
            streamed_parts = []
            trailing_finish = None
            for chunk in chat.send_message_stream(parts):
                txt = getattr(chunk, "text", None) or ""
                if txt:
                    streamed_parts.append(txt)
                    yield _clean_model_noise(txt)
                cands = getattr(chunk, "candidates", None) or []
                if cands:
                    c0 = cands[0]
                    fr = getattr(c0, "finish_reason", None)
                    if fr is not None:
                        trailing_finish = fr

            full_round = "".join(streamed_parts).strip()
            if not _finish_reason_implies_truncation(trailing_finish) or not full_round:
                return

            parts = [_continuation_prompt()]

    def stream_chat(self, carga_util, historial=None, system_instruction: str = None):
        if not self.api_key:
            yield t("llm_onboarding_missing_gemini")
            return

        from src.services.google_genai import get_genai_client

        client = get_genai_client(self.api_key)

        candidates = gemini_model_candidates()
        last_error: Exception | None = None

        for idx, model_name in enumerate(candidates):
            try:
                yield from self._stream_with_model(
                    client, model_name, carga_util, historial, system_instruction
                )
                return
            except Exception as exc:
                last_error = exc
                if is_gemini_model_not_found_error(exc) and idx < len(candidates) - 1:
                    continue
                raise

        if last_error:
            raise last_error

    def generar_imagen(self, prompt_artistico: str):
        if not self.api_key:
            return None, t("llm_onboarding_missing_gemini")
        try:
            image_bytes, err = _imagen_via_rest(self.api_key, prompt_artistico)
            if err or not image_bytes:
                return None, err or t("llm_gemini_no_image")

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"gen_{timestamp}.png"
            final_path = os.path.join(CARPETA_IMAGENES, filename)

            with open(final_path, "wb") as f:
                f.write(image_bytes)

            return final_path, None

        except Exception as e:
            return None, t("llm_art_error", error=e)


class GroqProvider(LLMProvider):
    """Proveedor Groq con soporte de streaming sobre modelos LLaMA de alta velocidad."""

    @staticmethod
    def _minimal_system_content() -> str:
        return t("groq_minimal_system_prompt")

    def __init__(self, api_key=None, model="llama-3.3-70b-versatile"):
        super().__init__(api_key)
        self.model = model

    @staticmethod
    def _trim_history(mensajes: list, keep_last: int = 4) -> list:
        """Keeps system message + last N user/assistant turns to reduce token count."""
        if len(mensajes) <= keep_last + 1:
            return mensajes
        system_msgs = [m for m in mensajes if m["role"] == "system"]
        non_system = [m for m in mensajes if m["role"] != "system"]
        return system_msgs + non_system[-keep_last:]

    @staticmethod
    def _groq_model_candidates(preferred: str, fallback: str) -> list[str]:
        """Modelos Groq a probar (sin añadir 8b por defecto: contexto/TPM muy bajo)."""
        candidates: list[str] = []
        for name in (preferred, fallback):
            if name and name not in candidates:
                candidates.append(name)
        extra = (os.getenv("GROQ_EXTRA_FALLBACK_MODEL") or "").strip()
        if extra and extra not in candidates:
            candidates.append(extra)
        return candidates or [preferred or "llama-3.3-70b-versatile"]

    def _prepare_groq_messages(
        self,
        mensajes: list,
        model_name: str,
        sys_prompt: str,
        *,
        aggressive: bool = False,
    ) -> list:
        """Ajusta historial y último mensaje de usuario al presupuesto del modelo."""
        from src.services.context_manager import truncate_text, trim_messages_to_budget

        msgs = [dict(m) for m in mensajes]
        if aggressive:
            msgs = self._trim_history(msgs, keep_last=2)
            if msgs:
                msgs[0] = {"role": "system", "content": self._minimal_system_content()}

        max_user_chars = _env_int(
            "GROQ_MAX_USER_CHARS_AGGRESSIVE" if aggressive else "GROQ_MAX_USER_CHARS",
            12_000 if aggressive else 28_000,
        )
        suffix = t("llm_context_truncated_suffix")
        for idx in range(len(msgs) - 1, -1, -1):
            if msgs[idx].get("role") == "user" and msgs[idx].get("content"):
                new_content, _ = truncate_text(str(msgs[idx]["content"]), max_user_chars, suffix=suffix)
                msgs[idx]["content"] = new_content
                break

        reserve = _env_int("GROQ_MAX_TOKENS", 8000) + 1024
        return trim_messages_to_budget(
            msgs,
            model_name,
            system_instruction=sys_prompt,
            reserve_tokens=reserve,
        )

    def _attempt_stream(self, cliente, model_name: str, mensajes: list,
                        max_tokens: int, temperature: float, max_rounds: int):
        """Single streaming attempt against one model, yields chunks."""
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
                    yield delta_content
                if getattr(choice, "finish_reason", None):
                    finish_reason = choice.finish_reason

            full_round = "".join(streamed_parts).strip()
            if finish_reason != "length" or not full_round:
                return

            convo_messages.append({"role": "assistant", "content": full_round})
            convo_messages.append({"role": "user", "content": _continuation_prompt()})

    def stream_chat(self, mensaje: str, historial: list, system_instruction: str = None):
        if not self.api_key:
            yield t("llm_onboarding_missing_groq")
            return

        try:
            Groq = _lazy_groq()
            cliente = Groq(api_key=self.api_key)
            sys_prompt = _apply_optional_system_compact(
                system_instruction, "GROQ_SYSTEM_PROMPT_MAX_CHARS", 3000
            )
            mensajes = [{"role": "system", "content": sys_prompt}]
            for m in historial:
                if m.get("content"):
                    mensajes.append({"role": m["role"], "content": m["content"]})
            mensajes.append({"role": "user", "content": mensaje})

            preferred_model = os.getenv("GROQ_MODEL", self.model)
            fallback_model = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.3-70b-versatile")
            candidate_models = self._groq_model_candidates(preferred_model, fallback_model)

            max_tokens = _env_int("GROQ_MAX_TOKENS", 8000)
            temperature = _env_float("GROQ_TEMPERATURE", 0.2)
            max_rounds = max(1, _env_int("GROQ_CONTINUATION_ROUNDS", 2))

            last_error = None
            for model_name in candidate_models:
                for attempt in range(2):
                    try:
                        aggressive = attempt > 0
                        msgs = self._prepare_groq_messages(
                            mensajes,
                            model_name,
                            sys_prompt,
                            aggressive=aggressive,
                        )
                        for chunk in self._attempt_stream(
                            cliente, model_name, msgs, max_tokens, temperature, max_rounds
                        ):
                            yield _clean_model_noise(chunk)
                        return
                    except Exception as inner_e:
                        err_str = str(inner_e)
                        is_recoverable = (
                            "413" in err_str
                            or "too large" in err_str.lower()
                            or "rate_limit" in err_str.lower()
                            or "tokens per minute" in err_str.lower()
                            or "request too large" in err_str.lower()
                        )
                        if attempt == 0 and is_recoverable:
                            continue
                        last_error = inner_e
                        break

            raise last_error if last_error else RuntimeError("No se pudo inicializar Groq.")
        except Exception:
            raise


class OpenRouterProvider(LLMProvider):
    """Proveedor OpenRouter: acceso unificado a múltiples LLMs vía API compatible con OpenAI."""
    def stream_chat(self, mensaje: str, historial: list, system_instruction: str = None):
        if not self.api_key:
            yield t("llm_onboarding_missing_openrouter")
            return

        try:
            OpenAI = _lazy_openai()
            cliente = OpenAI(
                api_key=self.api_key,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": "https://superagenteiapro.com",
                    "X-Title": "SuperAgente IA Pro"
                }
            )
            sys_content = _apply_optional_system_compact(
                system_instruction, "OPENROUTER_SYSTEM_PROMPT_MAX_CHARS", 0
            )
            mensajes = [{"role": "system", "content": sys_content}]
            for m in historial:
                if m.get("content"):
                    mensajes.append({"role": m["role"], "content": m["content"]})
            mensajes.append({"role": "user", "content": mensaje})

            # Modelo configurable + fallback robusto para evitar caídas por modelos retirados.
            preferred_model = os.getenv("OPENROUTER_MODEL", "openrouter/auto")
            max_tokens = _env_int("OPENROUTER_MAX_TOKENS", 16384)
            temperature = _env_float("OPENROUTER_TEMPERATURE", 0.2)
            max_rounds = max(1, _env_int("OPENROUTER_CONTINUATION_ROUNDS", 3))
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
            yield t("llm_openrouter_error", error=e)


class OllamaProvider(LLMProvider):
    """Compatibilidad legacy: proveedor para Ollama local."""

    def __init__(self, model_name: str | None = None, base_url: str | None = None):
        super().__init__(api_key=os.getenv("OLLAMA_API_KEY", "ollama-local"))
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "llama3.1")
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        if self.base_url and not os.getenv("OLLAMA_BASE_URL"):
            from src.security.url_validator import validate_url
            result = validate_url(self.base_url, context="ollama_base_url")
            if not result.safe:
                raise ValueError(t("error_ollama_url_blocked", reason=result.reason))

    def stream_chat(self, mensaje: str, historial: list, system_instruction: str = None):
        try:
            import httpx
            OpenAI = _lazy_openai()
            cliente = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
            )
            sys_content = _apply_optional_system_compact(
                system_instruction, "OLLAMA_SYSTEM_PROMPT_MAX_CHARS", 0
            )
            mensajes = [{"role": "system", "content": sys_content}]
            for m in historial:
                if m.get("content"):
                    mensajes.append({"role": m["role"], "content": m["content"]})
            mensajes.append({"role": "user", "content": mensaje})

            max_tokens = _env_int("OLLAMA_MAX_TOKENS", 32768)
            temperature = _env_float("OLLAMA_TEMPERATURE", 0.2)
            max_rounds = max(1, _env_int("OLLAMA_CONTINUATION_ROUNDS", 3))

            convo_messages = list(mensajes)
            for _ in range(max_rounds):
                streamed_parts = []
                finish_reason = None
                stream = cliente.chat.completions.create(
                    model=self.model_name,
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
        except Exception as e:
            yield t("llm_ollama_error", error=e)


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
        from src.security.url_validator import validate_url
        result = validate_url(self.base_url, context="custom_openai_base_url")
        if not result.safe:
            raise ValueError(t("error_url_blocked_ssrf", reason=result.reason))

    def stream_chat(self, mensaje: str, historial: list, system_instruction: str = None):
        if not self.api_key:
            yield t("llm_custom_no_api_key", model=self.model_name)
            return
        if not self.base_url:
            yield t("llm_custom_no_base_url", model=self.model_name)
            return

        try:
            import httpx
            OpenAI = _lazy_openai()
            cliente = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
            )
            sys_content = _apply_optional_system_compact(
                system_instruction, "CUSTOM_OPENAI_SYSTEM_PROMPT_MAX_CHARS", 0
            )
            mensajes = [{"role": "system", "content": sys_content}]
            for m in historial:
                if m.get("content"):
                    mensajes.append({"role": m["role"], "content": m["content"]})
            mensajes.append({"role": "user", "content": mensaje})

            temperature = _env_float("CUSTOM_OPENAI_TEMPERATURE", 0.2)
            max_rounds = max(1, _env_int("CUSTOM_OPENAI_CONTINUATION_ROUNDS", 3))
            max_tokens_override = os.getenv("CUSTOM_OPENAI_MAX_TOKENS")

            create_kwargs: dict = {
                "model": self.model_name,
                "messages": [],
                "stream": True,
                "temperature": temperature,
            }
            if max_tokens_override:
                create_kwargs["max_tokens"] = int(max_tokens_override)

            convo_messages = list(mensajes)
            for _ in range(max_rounds):
                streamed_parts = []
                finish_reason = None
                create_kwargs["messages"] = convo_messages
                stream = cliente.chat.completions.create(**create_kwargs)
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
        except Exception as e:
            error_str = str(e)
            if "402" in error_str or "Insufficient Balance" in error_str:
                yield t("llm_custom_402")
            else:
                yield t("llm_custom_error", model=self.model_name, error=e)


class GroqWhisperProvider:
    """Wrapper de transcripción de audio usando Groq Whisper v3."""

    def __init__(self, api_key=None):
        self.api_key = api_key

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> tuple[str, str | None]:
        if not self.api_key:
            return "", t("llm_whisper_no_key")
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
            return None, None, t("llm_tts_no_key")
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
            return GeminiProvider(api_key=api_keys.get("GEMINI_API_KEY"))
            
        elif "Groq" in motor_name and "Whisper" not in motor_name:
            return GroqProvider(api_key=api_keys.get("GROQ_API_KEY"))
            
        elif "OpenRouter" in motor_name:
            return OpenRouterProvider(api_key=api_keys.get("OPENROUTER_API_KEY"))

        elif "Ollama" in motor_name:
            return OllamaProvider()
            
        else:
            custom_models = api_keys.get("CUSTOM_MODELS", [])
            matched_custom = next((cm for cm in custom_models if f"🤖 {cm['name']}" == motor_name), None)
            
            if matched_custom:
                return CustomOpenAIProvider(
                    base_url=matched_custom["base_url"],
                    api_key=matched_custom["api_key"],
                    model_name=matched_custom["model_id"],
                )
            
            return OpenRouterProvider(api_key=api_keys.get("OPENROUTER_API_KEY"))