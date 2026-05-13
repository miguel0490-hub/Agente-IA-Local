"""Chat runtime orchestration extracted from app.py."""

from __future__ import annotations

import os
import uuid as _uuid

import streamlit as st

from src.core.i18n import TOOL_CONTEXT_PREFIX, all_locale_values_for_key, t
from src.core.sanitizer import sanitize_markdown_text

# User may type in any language; match file-generation intent across locales.
_FILE_INTENT_KEYWORDS = frozenset(
    {
        "pdf",
        "informe",
        "documento",
        "archivo",
        "excel",
        "report",
        "genera un",
        "file",
        "document",
        "spreadsheet",
        "create",
        "generate",
        "generar",
        "fichier",
        "rapport",
        "générer",
        "créer",
        "datei",
        "bericht",
        "erstellen",
        "relatório",
        "arquivo",
        "criar",
        "gerar",
        "planilha",
    }
)


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
    if chat_actual and chat_actual["title"] in all_locale_values_for_key("new_chat_title"):
        new_title = prompt[:30] + ("..." if len(prompt) > 30 else "")
        update_chat_title_fn(st.session_state.chat_id, new_title)
        st.session_state.chat_list = get_user_chats_fn(st.session_state.user_id)
        renamed = True

    es_comando_imagen, prompt_artistico = parse_intent_fn(prompt)

    whisper_l = t("engine_whisper")
    tts_l = t("engine_tts")
    image_l = t("engine_image")
    if motor == whisper_l:
        st.info(t("hint_tool_whisper"))
        st.stop()
    if motor == tts_l:
        st.info(t("hint_tool_tts"))
        st.stop()
    if motor == image_l:
        st.info(t("hint_tool_image"))
        st.stop()

    if es_comando_imagen:
        if "Gemini" not in motor:
            st.warning(t("art_requires_gemini"))
            st.stop()
        if not prompt_artistico:
            st.error(t("art_prompt_missing"))
            st.stop()

        prompt_visibilidad = f"🎨 *{t('art_user_asked_create', prompt=prompt_artistico)}*"
        prompt_visibilidad_safe = sanitize_markdown_text(prompt_visibilidad)
        st.session_state.messages.append({"role": "user", "content": prompt_visibilidad_safe})
        with st.chat_message("user", avatar="🧑‍💻"):
            st.markdown(prompt_visibilidad_safe)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner(t("art_spinner")):
                provider = get_gemini_provider_fn()
                filepath, error = provider.generar_imagen(prompt_artistico)

            if error:
                st.error(error)
                st.session_state.messages.append({"role": "assistant", "content": sanitize_markdown_text(error)})
            else:
                from PIL import Image

                img = Image.open(filepath)
                st.image(img, caption=t("art_caption", prompt=prompt_artistico), use_container_width=True)
                render_download_button_fn(filepath)
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": sanitize_markdown_text(t("art_done", prompt=prompt_artistico)),
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
                texto_extraido = t("attach_image_note", name=archivo.name)
            elif _ext in _exts_video:
                import uuid

                safe_filename = f"video_analisis_{uuid.uuid4().hex[:8]}{_ext}"
                video_adjunto_path = os.path.join(carpeta_imagenes, safe_filename)
                with open(video_adjunto_path, "wb") as f:
                    f.write(archivo.getbuffer())
                texto_extraido = t("attach_video_note", name=archivo.name)
            else:
                contenido_extraido = extraer_texto_archivo(archivo)
                if contenido_extraido.startswith("⛔"):
                    st.warning(contenido_extraido)
                    texto_extraido = t("attach_doc_error_block", name=archivo.name, body=contenido_extraido)
                else:
                    texto_extraido = t(
                        "attach_doc_content_block",
                        name=archivo.name.upper(),
                        content=contenido_extraido,
                    )

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
                        with st.status(t("video_status_init"), expanded=True) as status:
                            st.write(t("video_uploading"))
                            gemini_key = st.session_state.api_keys.get("GEMINI_API_KEY")
                            if not gemini_key:
                                st.error(t("video_missing_key"))
                                st.stop()
                            cliente_g = ggenai.Client(api_key=gemini_key)
                            video_file = cliente_g.files.upload(file=video_adjunto_path)
                            start_time = time.time()
                            while video_file.state.name == "PROCESSING":
                                elapsed = int(time.time() - start_time)
                                status.update(label=t("video_analyzing", elapsed=elapsed), state="running")
                                time.sleep(2)
                                video_file = cliente_g.files.get(name=video_file.name)
                            if video_file.state.name == "FAILED":
                                status.update(label=t("video_failed"), state="error", expanded=True)
                                st.error(t("video_decode_error"))
                                st.stop()
                            status.update(
                                label=t("video_done", seconds=int(time.time() - start_time)),
                                state="complete",
                                expanded=False,
                            )
                        carga_util.append(video_file)
                    finally:
                        if video_adjunto_path and os.path.exists(video_adjunto_path):
                            os.remove(video_adjunto_path)
            else:
                if imagen_adjunta:
                    st.warning(t("image_motor_unsupported"))

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
                st.toast(t("semantic_cache_toast"), icon="⚡")
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
                        st.warning(
                            t("provider_error_warning", provider=_provider_name, detail=err_str[:200])
                        )
                        st.info(t("fallback_switching_info", name=fallback_tier.name))
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
                            st.error(
                                t("backup_generation_error", name=fallback_tier.name, error=e_backup)
                            )
                            break
                    else:
                        st.error(t("generation_error", motor=motor, error=e))
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
                        st.warning(t("execute_blocked_warning"))
                        st.session_state.security_events.append("execute_code_blocked_no_explicit_approval")
                        break
                    codigo = execute_tool.get("code", "")
                    with st.spinner(t("exec_spinner")):
                        from src.services.execution_service import CodeExecutionService
                        from src.security.execution_timeout_guard import ExecutionTimeoutGuard

                        exec_service = CodeExecutionService()
                        _guard = ExecutionTimeoutGuard.get_instance()
                        resultado_ejecucion = exec_service.execute_python(codigo)
                    st.info(t("exec_done_info"))
                    st.session_state.messages.append({"role": "assistant", "content": clean_res_safe})
                    msg_sistema = TOOL_CONTEXT_PREFIX + t("exec_system_user_message", output=resultado_ejecucion)
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
                    with st.spinner(t("rag_spinner", query=query)):
                        from src.services.rag_service import RAGService

                        rag_service = RAGService()
                        resultados = rag_service.query(query)
                    st.info(t("rag_done_info", count=len(resultados)))
                    st.session_state.messages.append({"role": "assistant", "content": clean_res_safe})
                    if resultados:
                        res_texto = "\n\n".join([f"📄 {r['filename']}:\n{r['content']}..." for r in resultados])
                        msg_sistema = TOOL_CONTEXT_PREFIX + t("rag_results_system", query=query, snippets=res_texto)
                    else:
                        msg_sistema = TOOL_CONTEXT_PREFIX + t("rag_empty_system", query=query)
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
                    with st.spinner(t("web_spinner", query=query)):
                        from src.services.web_search import search_web

                        resultados_web = search_web(query)
                    st.info(t("web_done_info", query=query))
                    st.session_state.messages.append({"role": "assistant", "content": clean_res_safe})
                    pl = (prompt or "").lower()
                    user_wants_file = any(kw in pl for kw in _FILE_INTENT_KEYWORDS)
                    file_instruction = (
                        t("web_file_instruction_yes") if user_wants_file else t("web_file_instruction_no")
                    )
                    msg_sistema = TOOL_CONTEXT_PREFIX + t(
                        "web_search_tool_system_message",
                        query=query,
                        results=resultados_web,
                        file_instruction=file_instruction,
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
                        st.warning(t("tool_rate_limit_warning"))
                        st.session_state.security_events.append(f"tool_rate_limit_exceeded:{action}")
                        continue
                    if tool.get("action") == "search_web":
                        continue
                    if tool.get("action") == "create_file" and _did_web_search:
                        if not any(kw in (prompt or "").lower() for kw in _FILE_INTENT_KEYWORDS):
                            continue
                    if tool.get("action") == "open_converter":
                        last_user_text = st.session_state.messages[-1].get("content", "") if st.session_state.messages else ""
                        if tool.get("requires_confirmation") and not tool_guard_cls.has_explicit_approval(last_user_text, "open_converter"):
                            st.warning(t("converter_blocked_warning"))
                            st.session_state.security_events.append("open_converter_blocked_no_explicit_approval")
                            continue
                        st.session_state["suggested_format"] = tool.get("suggested_format", "")
                        st.success(
                            t("converter_panel_opening", format=st.session_state["suggested_format"])
                        )
                        panel_conversor_fn()
                        continue
                    path = factory.execute_tool(tool)
                    if path:
                        file_paths.append(path)
                        if path not in rendered_paths:
                            render_download_button_fn(path)
                            rendered_paths.add(path)
                    else:
                        st.error(t("tool_internal_error", action=tool.get("action")))

        st.session_state.messages.append(
            {"role": "assistant", "content": sanitize_markdown_text(clean_res), "file_paths": file_paths}
        )
        guardar_memoria_fn(st.session_state.chat_id, st.session_state.messages, st.session_state.api_keys)

    if renamed:
        st.rerun()
