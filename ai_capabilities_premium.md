## IA Capability Matrix (Premium)

- `Gemini 2.5 Pro`: chat multimodal (texto/imagen/video), generación de imagen (`imagen-4.0`), max tokens configurable (`GEMINI_MAX_TOKENS`), temperatura configurable.
- `Groq Llama`: chat texto de baja latencia, fallback de modelo configurable (`GROQ_FALLBACK_MODEL`), continuación automática si corta por longitud.
- `OpenRouter`: chat multiproveedor con fallback a `openrouter/auto`, `max_tokens` configurable, continuación automática por cortes.
- `Custom OpenAI-compatible`: chat para endpoints privados (vLLM, LM Studio, etc.), `max_tokens` y temperatura configurables.
- `Ollama local`: chat on-prem/local, `max_tokens` configurable, limpieza de artefactos de salida.
- `Groq Whisper`: transcripción STT de audio.
- `OpenAI TTS`: síntesis de voz neural premium.
- `Edge TTS`: síntesis de voz sin API key (fallback gratuito).

## Entrenamiento/Hardening Aplicado

- Limpieza de artefactos de rol en salida (`agt:`, `assistant:` y variantes).
- Protección anti-respuesta truncada en motores textuales críticos:
  - OpenRouter: continuación automática (`OPENROUTER_CONTINUATION_ROUNDS`)
  - Groq: continuación automática (`GROQ_CONTINUATION_ROUNDS`)
- Estandarización de parámetros premium:
  - `max_tokens` configurable para todos los motores de texto.
  - temperatura configurable para consistencia de estilo.
- Fallbacks robustos por proveedor para evitar degradación funcional.

## Objetivo de Operación Premium

- Respuestas completas y no truncadas.
- Menor ruido de formato en chat.
- Comportamiento homogéneo entre proveedores.
- Configuración centralizada por entorno vía `.env`.
