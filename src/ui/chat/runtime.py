"""Chat runtime orchestration extracted from app.py."""

from __future__ import annotations

import os
import uuid as _uuid

import streamlit as st

from src.core.i18n import t
from src.core.sanitizer import sanitize_markdown_text


def _normalize_tool_by_user_intent(tool: dict, user_prompt: str) -> dict:
    """Forces PDF filename when user explicitly asks for PDF output."""
    if not isinstance(tool, dict):
        return tool
    action = (tool.get("action") or "").strip().lower()
    filename = (tool.get("filename") or "").strip()
    if action != "create_file" or not filename:
        return tool

    wants_pdf = "pdf" in (user_prompt or "").lower()
    lower_name = filename.lower()
    if wants_pdf and lower_name.endswith((".html", ".htm")):
        stem = filename.rsplit(".", 1)[0]
        patched = dict(tool)
        patched["filename"] = f"{stem}.pdf"
        return patched
    return tool


def handle_chat_interaction(
    motor: str,
    archivo,
    system_instruction_activo: str,
    parse_intent_fn,
    get_gemini_provider_fn,
    panel_conversor_fn,
    render_download_button_fn,
    guardar_memoria_fn,
    tool_guard_cls,
    carpeta_imagenes: str,
    get_user_chats_fn,
    update_chat_title_fn,
) -> None:
    """Handles chat input, model execution, tool calls and persistence."""
    prompt = st.chat_input(t("chat_placeholder"))
    if not prompt:
        return

    st.session_state.auto_close_sidebar = True

    from src.core.security import check_scoped_rate_limit

    if not check_scoped_rate_limit(str(st.session_state.user_id), scope="chat", limit=10, window_seconds=60):
        st.error(t("chat_rate_limit"))
        st.stop()

    renamed = False
    chats_actuales = get_user_chats_fn(st.session_state.user_id)
    chat_actual = next((c for c in chats_actuales if c["id"] == st.session_state.chat_id), None)
    if chat_actual and chat_actual["title"] in ["Nuevo Chat", "New Chat"]:
        new_title = prompt[:30] + ("..." if len(prompt) > 30 else "")
        update_chat_title_fn(st.session_state.chat_id, new_title)
        st.session_state.chat_list = get_user_chats_fn(st.session_state.user_id)
        renamed = True

    es_comando_imagen, prompt_artistico = parse_intent_fn(prompt)

    motores_herramienta = {
        "Groq Whisper (Oídos: Transcripción STT)",
        "OpenAI TTS (Voz: Text-to-Speech)",
        "Generador de Assets (Manos: Texto a Imagen)",
    }
    if motor in motores_herramienta:
        _guias = {
            "Groq Whisper (Oídos: Transcripción STT)": "🎙️ **Modo STT activo.** Sube un archivo de audio en el panel **'Groq Whisper'** del sidebar y pulsa *'Transcribir'*.",
            "OpenAI TTS (Voz: Text-to-Speech)": "🔊 **Modo TTS activo.** Escribe el texto en el panel **'OpenAI TTS'** del sidebar y pulsa *'Generar Audio'*.",
            "Generador de Assets (Manos: Texto a Imagen)": "🎨 **Modo Imagen activo.** Escribe tu prompt en el panel **'Generador de Assets'** del sidebar y pulsa *'Generar Imagen'*.",
        }
        st.info(_guias[motor])
        st.stop()

    if es_comando_imagen:
        if "Gemini" not in motor:
            st.warning("⚠️ La generación de arte requiere seleccionar el motor **Gemini** en el panel de control.")
            st.stop()
        if not prompt_artistico:
            st.error("❌ Te ha faltado decirme qué quieres que dibuje.")
            st.stop()

        prompt_visibilidad = f"🎨 *Has pedido crear:* {prompt_artistico}"
        prompt_visibilidad_safe = sanitize_markdown_text(prompt_visibilidad)
        st.session_state.messages.append({"role": "user", "content": prompt_visibilidad_safe})
        with st.chat_message("user", avatar="🧑‍💻"):
            st.markdown(prompt_visibilidad_safe)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Conectando con el estudio de arte de Gemini..."):
                provider = get_gemini_provider_fn()
                filepath, error = provider.generar_imagen(prompt_artistico)

            if error:
                st.error(error)
                st.session_state.messages.append({"role": "assistant", "content": sanitize_markdown_text(error)})
            else:
                from PIL import Image

                img = Image.open(filepath)
                st.image(img, caption=f"Obra: {prompt_artistico}", use_container_width=True)
                render_download_button_fn(filepath)
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": sanitize_markdown_text(f"Aquí tienes la imagen generada: '{prompt_artistico}'"),
                        "image_path": filepath,
                    }
                )
        guardar_memoria_fn(st.session_state.chat_id, st.session_state.messages, st.session_state.api_keys)
    else:
        from src.services.document_parser import extraer_texto_archivo

        texto_extraido = ""
        imagen_adjunta = None
        video_adjunto_path = None

        if archivo:
            from pathlib import Path as _Path

            _ext = _Path(archivo.name.lower()).suffix
            _exts_imagen = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".ico"}
            _exts_video = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv"}

            if _ext in _exts_imagen:
                from PIL import Image

                imagen_adjunta = Image.open(archivo)
                texto_extraido = f"\n*(Adjuntada imagen para análisis visual: {archivo.name})*"
            elif _ext in _exts_video:
                import uuid

                safe_filename = f"video_analisis_{uuid.uuid4().hex[:8]}{_ext}"
                video_adjunto_path = os.path.join(carpeta_imagenes, safe_filename)
                with open(video_adjunto_path, "wb") as f:
                    f.write(archivo.getbuffer())
                texto_extraido = f"\n*(Adjuntado vídeo para análisis: {archivo.name})*"
            else:
                contenido_extraido = extraer_texto_archivo(archivo)
                if contenido_extraido.startswith("⛔"):
                    st.warning(contenido_extraido)
                    texto_extraido = f"\n\n[ARCHIVO: {archivo.name}]\n{contenido_extraido}\n"
                else:
                    texto_extraido = f"\n\n[CONTENIDO DE {archivo.name.upper()}]:\n{contenido_extraido}\n"

        prompt_final = prompt + texto_extraido
        prompt_final_safe = sanitize_markdown_text(prompt_final)
        st.session_state.messages.append({"role": "user", "content": prompt_final_safe})
        with st.chat_message("user", avatar="🧑‍💻"):
            st.markdown(prompt_final_safe)

        with st.chat_message("assistant", avatar="🤖"):
            res_placeholder = st.empty()

            if "Gemini" in motor:
                carga_util = [prompt_final]
                if imagen_adjunta:
                    carga_util.append(imagen_adjunta)
                if video_adjunto_path:
                    import google.genai as ggenai
                    import time

                    try:
                        with st.status("🎬 Inicializando procesamiento de vídeo...", expanded=True) as status:
                            st.write("📤 Subiendo archivo seguro a Gemini...")
                            gemini_key = st.session_state.api_keys.get("GEMINI_API_KEY")
                            if not gemini_key:
                                st.error("❌ Falta la clave de Gemini para procesar vídeo.")
                                st.stop()
                            cliente_g = ggenai.Client(api_key=gemini_key)
                            video_file = cliente_g.files.upload(file=video_adjunto_path)
                            start_time = time.time()
                            while video_file.state.name == "PROCESSING":
                                elapsed = int(time.time() - start_time)
                                status.update(label=f"🎬 Analizando vídeo en la nube... (⏳ {elapsed}s transcurridos)", state="running")
                                time.sleep(2)
                                video_file = cliente_g.files.get(name=video_file.name)
                            if video_file.state.name == "FAILED":
                                status.update(label="❌ Error crítico de procesamiento", state="error", expanded=True)
                                st.error("Fallo interno en los servidores de Google GenAI al decodificar el vídeo.")
                                st.stop()
                            status.update(label=f"✅ Vídeo procesado con éxito en {int(time.time() - start_time)}s", state="complete", expanded=False)
                        carga_util.append(video_file)
                    finally:
                        if video_adjunto_path and os.path.exists(video_adjunto_path):
                            os.remove(video_adjunto_path)
            else:
                if imagen_adjunta:
                    st.warning("⚠️ Este motor no soporta análisis de imágenes locales.")

            from src.services.llm_provider import LLMFactory
            from src.services.semantic_cache import get_semantic_cache
            from src.agents.prompt_manager import enrich_system_instruction
            from src.agents.tool_router import get_tool_router
            from src.agents.health_monitor import AgentHealthMonitor
            from src.agents.model_fallback import get_fallback_chain
            from src.agents.validators import validate_response

            _active_role = st.session_state.get("active_role", "")
            _enriched_instruction = enrich_system_instruction(
                system_instruction_activo,
                role_name=_active_role,
                user_prompt=prompt,
            )

            _tool_router = get_tool_router()
            _routing = _tool_router.route(_active_role, prompt)
            max_iteraciones = _routing.max_iterations

            _health_monitor = AgentHealthMonitor.get_instance()
            _request_id = _uuid.uuid4().hex[:12]

            provider = LLMFactory.get_provider(motor_name=motor, api_keys=st.session_state.api_keys)
            clean_res = ""
            file_paths = []
            iteracion = 0
            tools = []
            _did_web_search = False

            _sem_cache = get_semantic_cache()
            _cached = _sem_cache.get(prompt_final, motor, system_instruction=_enriched_instruction)
            if _cached:
                clean_res = _cached
                res_placeholder.markdown(sanitize_markdown_text(clean_res))
                st.toast("⚡ Respuesta recuperada de caché", icon="⚡")
                iteracion = max_iteraciones

            _health_monitor.start_request(
                _request_id,
                agent_role=_routing.role_key,
                provider=motor,
            )

            while iteracion < max_iteraciones:
                iteracion += 1
                full_res = ""
                try:
                    if "Gemini" in motor:
                        gen = provider.stream_chat(carga_util, st.session_state.messages[:-1], system_instruction=_enriched_instruction)
                    else:
                        gen = provider.stream_chat(prompt_final, st.session_state.messages[:-1], system_instruction=_enriched_instruction)
                    for chunk in gen:
                        if chunk:
                            full_res += chunk
                            res_placeholder.markdown(full_res + "▌")
                            _health_monitor.heartbeat(_request_id)
                except Exception as e:
                    _health_monitor.complete_request(_request_id, error=str(e))
                    _fallback_chain = get_fallback_chain()
                    _provider_name = _fallback_chain._extract_provider_name(motor)
                    fallback_tier = _fallback_chain.get_fallback(
                        _provider_name, st.session_state.api_keys,
                    )
                    if fallback_tier:
                        err_str = str(e)
                        res_placeholder.empty()
                        st.warning(f"⚠️ Error de {_provider_name}: {err_str[:200]}")
                        st.info(f"🔄 Cambiando automáticamente a {fallback_tier.name}...")
                        provider_backup = LLMFactory.get_provider(
                            motor_name=fallback_tier.motor_key,
                            api_keys=st.session_state.api_keys,
                        )
                        _request_id_fb = _uuid.uuid4().hex[:12]
                        _health_monitor.start_request(
                            _request_id_fb,
                            agent_role=_routing.role_key,
                            provider=fallback_tier.name,
                        )
                        if "Gemini" in fallback_tier.motor_key:
                            carga_util = [prompt_final]
                            if imagen_adjunta:
                                carga_util.append(imagen_adjunta)
                        full_res = ""
                        try:
                            if "Gemini" in fallback_tier.motor_key:
                                gen_backup = provider_backup.stream_chat(carga_util, st.session_state.messages[:-1], system_instruction=_enriched_instruction)
                            else:
                                gen_backup = provider_backup.stream_chat(prompt_final, st.session_state.messages[:-1], system_instruction=_enriched_instruction)
                            for chunk in gen_backup:
                                if chunk:
                                    full_res += chunk
                                    res_placeholder.markdown(full_res + "▌")
                                    _health_monitor.heartbeat(_request_id_fb)
                            _health_monitor.complete_request(_request_id_fb)
                        except Exception as e_backup:
                            _health_monitor.complete_request(_request_id_fb, error=str(e_backup))
                            st.error(f"❌ Error en el sistema de respaldo ({fallback_tier.name}): {e_backup}")
                            break
                    else:
                        st.error(f"❌ Error en la generación ({motor}): {e}")
                        break

                from src.core.agent_tools import parse_tool_calls
                from src.services.file_factory import FileFactory

                clean_res, tools = parse_tool_calls(full_res, role_name=_active_role)

                _validation = validate_response(clean_res)
                if _validation.sanitized_text:
                    clean_res = _validation.sanitized_text

                clean_res_safe = sanitize_markdown_text(clean_res)
                res_placeholder.markdown(clean_res_safe)

                execute_tool = next((t for t in tools if t.get("action") == "execute_code"), None)
                if execute_tool:
                    last_user_text = st.session_state.messages[-1].get("content", "") if st.session_state.messages else ""
                    if execute_tool.get("requires_confirmation") and not tool_guard_cls.has_explicit_approval(last_user_text, "execute_code"):
                        st.warning("⛔ Ejecución bloqueada. Confirma explícitamente con [approve:execute_code] en tu mensaje.")
                        st.session_state.security_events.append("execute_code_blocked_no_explicit_approval")
                        break
                    codigo = execute_tool.get("code", "")
                    with st.spinner("Ejecutando código Python en sandbox local..."):
                        from src.services.execution_service import CodeExecutionService
                        from src.security.execution_timeout_guard import ExecutionTimeoutGuard

                        exec_service = CodeExecutionService()
                        _guard = ExecutionTimeoutGuard.get_instance()
                        resultado_ejecucion = exec_service.execute_python(codigo)
                    st.info("💻 Ejecución de código local completada.")
                    st.session_state.messages.append({"role": "assistant", "content": clean_res_safe})
                    msg_sistema = (
                        "RESULTADO DE LA EJECUCIÓN (STDOUT/STDERR):\n"
                        f"{resultado_ejecucion}\n\n"
                        "Por favor, usa esta salida para responder al usuario o continuar tu tarea."
                    )
                    st.session_state.messages.append({"role": "user", "content": msg_sistema})
                    if "Gemini" in motor:
                        carga_util = [msg_sistema]
                    else:
                        prompt_final = msg_sistema
                    res_placeholder = st.empty()
                    continue

                rag_tool = next((t for t in tools if t.get("action") == "query_rag"), None)
                if rag_tool:
                    query = rag_tool.get("query", "").strip().replace("\\n", "").replace("\n", "")
                    with st.spinner(f"Consultando Cerebro RAG para: '{query}'..."):
                        from src.services.rag_service import RAGService

                        rag_service = RAGService()
                        resultados = rag_service.query(query)
                    st.info(f"🧠 Consulta RAG completada: {len(resultados)} fragmentos encontrados.")
                    st.session_state.messages.append({"role": "assistant", "content": clean_res_safe})
                    if resultados:
                        res_texto = "\n\n".join([f"📄 {r['filename']}:\n{r['content']}..." for r in resultados])
                        msg_sistema = f"RESULTADOS DEL CEREBRO RAG PARA '{query}':\n{res_texto}\n\nUsa esta información parcial para responder."
                    else:
                        msg_sistema = f"El Cerebro RAG no encontró resultados relevantes para '{query}'."
                    st.session_state.messages.append({"role": "user", "content": msg_sistema})
                    if "Gemini" in motor:
                        carga_util = [msg_sistema]
                    else:
                        prompt_final = msg_sistema
                    res_placeholder = st.empty()
                    continue

                search_tool = next((t for t in tools if t.get("action") == "search_web"), None)
                if search_tool:
                    _did_web_search = True
                    query = search_tool.get("query", "").strip().replace("\\n", "").replace("\n", "")
                    with st.spinner(f"Buscando en la web: '{query}'..."):
                        from src.services.web_search import search_web

                        resultados_web = search_web(query)
                    st.info(f"🌐 Búsqueda web completada: {query}")
                    st.session_state.messages.append({"role": "assistant", "content": clean_res_safe})
                    user_wants_file = any(
                        kw in prompt.lower()
                        for kw in ("pdf", "informe", "documento", "archivo", "excel", "report", "genera un")
                    )
                    if user_wants_file:
                        file_instruction = (
                            "4. El usuario SÍ pidió un documento. Genera contenido EXTENSO y "
                            "PROFESIONAL con el formato adecuado usando create_file.\n"
                        )
                    else:
                        file_instruction = (
                            "4. El usuario NO pidió un documento. PROHIBIDO usar create_file, "
                            "PROHIBIDO generar PDF/HTML. Responde SOLO en texto plano en el chat.\n"
                        )
                    msg_sistema = (
                        f"RESULTADOS DE BÚSQUEDA PARA '{query}':\n{resultados_web}\n\n"
                        "INSTRUCCIONES POST-BÚSQUEDA (OBLIGATORIAS):\n"
                        "1. Analiza TODAS las fuentes anteriores en profundidad.\n"
                        "2. Responde al usuario con un resumen claro, completo y bien estructurado "
                        "basado en los datos extraídos de las fuentes.\n"
                        "3. PROHIBIDO usar bloques ```json con create_file a menos que se indique en el punto 4.\n"
                        + file_instruction
                        + "5. Genera la respuesta definitiva ahora."
                    )
                    st.session_state.messages.append({"role": "user", "content": msg_sistema})
                    if "Gemini" in motor:
                        carga_util = [msg_sistema]
                    else:
                        prompt_final = msg_sistema
                    res_placeholder = st.empty()
                    continue
                break

            _health_monitor.complete_request(_request_id)

            if clean_res and not _cached:
                _sem_cache.put(prompt_final, motor, clean_res, system_instruction=_enriched_instruction)

            file_paths = []
            if tools:
                factory = FileFactory(output_dir=carpeta_imagenes)
                rendered_paths = set()
                _allowed_tools = _routing.allowed_tools
                for tool in tools:
                    tool = _normalize_tool_by_user_intent(tool, prompt)
                    action = str(tool.get("action") or "unknown")
                    if action not in _allowed_tools:
                        continue
                    tool_scope_id = f"{st.session_state.user_id}:{action}"
                    if not check_scoped_rate_limit(tool_scope_id, scope="tools"):
                        st.warning("⏳ Has alcanzado temporalmente el límite de uso de herramientas. Espera un momento.")
                        st.session_state.security_events.append(f"tool_rate_limit_exceeded:{action}")
                        continue
                    if tool.get("action") == "search_web":
                        continue
                    if tool.get("action") == "create_file" and _did_web_search:
                        _file_keywords = ("pdf", "informe", "documento", "archivo", "excel", "report")
                        if not any(kw in prompt.lower() for kw in _file_keywords):
                            continue
                    if tool.get("action") == "open_converter":
                        last_user_text = st.session_state.messages[-1].get("content", "") if st.session_state.messages else ""
                        if tool.get("requires_confirmation") and not tool_guard_cls.has_explicit_approval(last_user_text, "open_converter"):
                            st.warning("⛔ Conversión bloqueada. Confirma explícitamente con [approve:open_converter].")
                            st.session_state.security_events.append("open_converter_blocked_no_explicit_approval")
                            continue
                        st.session_state["suggested_format"] = tool.get("suggested_format", "")
                        st.success(f"🤖 ¡Abriendo panel de conversión para ti (Formato: {st.session_state['suggested_format']})!")
                        panel_conversor_fn()
                        continue
                    path = factory.execute_tool(tool)
                    if path:
                        file_paths.append(path)
                        if path not in rendered_paths:
                            render_download_button_fn(path)
                            rendered_paths.add(path)
                    else:
                        st.error(f"❌ La herramienta `{tool.get('action')}` falló internamente.")

        st.session_state.messages.append(
            {"role": "assistant", "content": sanitize_markdown_text(clean_res), "file_paths": file_paths}
        )
        guardar_memoria_fn(st.session_state.chat_id, st.session_state.messages, st.session_state.api_keys)

    if renamed:
        st.rerun()
