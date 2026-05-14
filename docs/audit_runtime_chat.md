# Auditoría: `src/ui/chat/runtime.py` — plan de división

## Estado actual

- **~520 líneas**, dos símbolos públicos relevantes: `_normalize_tool_by_user_intent` y `handle_chat_interaction`.
- `handle_chat_interaction` concentra: rate limit, renombrado de chat, comandos por motor (Whisper/TTS/imagen), rama de **imagen Gemini**, rama principal con **adjuntos** (imagen / vídeo / documento), **vídeo con API Files de Gemini**, invocación **LLMFactory**, herramientas, caché semántico, fallback, validación y persistencia.

## Riesgos de un split brusco

- Muchas dependencias inyectadas como callables (`parse_intent_fn`, `get_gemini_provider_fn`, etc.) para testabilidad; los nuevos módulos deben conservar esa firma o un contexto (`ChatRuntimeDeps`) explícito.
- `st.session_state` y widgets Streamlit mezclados con lógica: conviene extraer primero **funciones puras** o **bloques sin UI** antes de mover código con `st.chat_message` / `st.spinner`.

## Propuesta de módulos (orden sugerido)

1. **`runtime_attachments.py`**: construcción de `texto_extraido`, listas `imagenes_adjuntas` / `video_local_paths`, constantes `_exts_*`, uso de `extraer_texto_archivo` y limpieza de paths temporales.
2. **`runtime_gemini_video.py`**: bucle de upload/polling de `google.genai` y mensajes de estado (mantiene imports pesados localizados).
3. **`runtime_llm_turn.py`**: desde selección de motor LLM hasta respuesta final (factory, tool router, streaming en placeholder) — el tramo más largo del `else`.
4. **`runtime_intents.py`**: `_FILE_INTENT_KEYWORDS`, `_normalize_tool_by_user_intent`, y helpers de “motor especial” (Whisper/TTS/imagen) si se desacoplan de Streamlit.

`runtime.py` quedaría como **fachada** que llama a estas piezas y mantiene la firma pública `handle_chat_interaction`.

## Criterios de aceptación por fase

- Cada extracción va acompañada de tests existentes o nuevos que cubran adjuntos, PDF filename patch y al menos un camino de error (rate limit / motor no soportado).
- Sin regresión visual: mismas claves i18n y mismos `st.stop()` por flujos de error.
