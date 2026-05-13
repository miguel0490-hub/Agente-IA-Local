"""Multimedia tools UI (STT, TTS, Image Gen) — reusable in sidebar or chat hub."""

from __future__ import annotations

import streamlit as st
from src.core.security import check_scoped_rate_limit
from src.services.file_validator import get_upload_policy
from src.services.task_queue import enqueue_transcription, get_job_status
from src.core.i18n import t


def process_pending_stt_jobs(guardar_memoria_fn) -> None:
    """Drains async STT jobs and appends results to chat (runs on every full page render)."""
    pending_stt_jobs = st.session_state.setdefault("pending_stt_jobs", [])
    remaining_stt_jobs = []
    for job in pending_stt_jobs:
        status = get_job_status(job.get("job_id"))
        if status["status"] == "finished":
            result = status.get("result") or {}
            if result.get("ok"):
                text = (result.get("text") or "").strip()
                st.success(t("mm_stt_async_ok"))
                st.session_state.messages.append(
                    {"role": "user", "content": t("mm_audio_transcript_user", text=text)}
                )
                if st.session_state.chat_id:
                    guardar_memoria_fn(st.session_state.chat_id, st.session_state.messages, st.session_state.api_keys)
            else:
                st.error(result.get("error") or t("mm_stt_async_fail"))
        elif status["status"] == "failed":
            st.error(
                t(
                    "mm_stt_job_fail",
                    detail=status.get("error") or t("mm_stt_unknown_error"),
                )
            )
        else:
            remaining_stt_jobs.append(job)
    st.session_state.pending_stt_jobs = remaining_stt_jobs


def render_multimedia_tools_body(
    panel_conversor_fn,
    secure_upload_check_fn,
    get_groq_whisper_provider_fn,
    get_openai_tts_provider_fn,
    get_edge_tts_provider_fn,
    guardar_memoria_fn,
) -> None:
    """STT / TTS / image-gen controls (no outer expander — caller provides container)."""
    if st.button(t("multimedia_converter"), use_container_width=True, key="hub_btn_converter"):
        st.session_state["suggested_format"] = ""
        panel_conversor_fn()

    st.markdown("---")

    st.markdown(t("multimedia_stt_title"))
    st.caption(t("multimedia_stt_desc"))
    audio_stt = st.file_uploader(
        t("multimedia_stt_upload"),
        key=f"uploader_stt_{st.session_state.form_clear_counter}",
    )
    if get_upload_policy() == "permissive":
        st.caption(t("mm_stt_permissive_caption"))
    else:
        st.caption(t("mm_stt_limit_caption"))
    if audio_stt:
        if not check_scoped_rate_limit(str(st.session_state.user_id), scope="uploads"):
            st.error(t("upload_rate_limit"))
            audio_stt = None
        else:
            check = secure_upload_check_fn(audio_stt.name, audio_stt.getvalue())
            if not check.ok:
                st.error(t("upload_blocked", reason=check.reason))
                audio_stt = None

    if audio_stt:
        st.audio(audio_stt, format=f"audio/{audio_stt.name.split('.')[-1]}")
        if st.button(t("multimedia_stt_button"), use_container_width=True, key="btn_stt"):
            with st.spinner(t("mm_stt_spinner")):
                groq_key = st.session_state.api_keys.get("GROQ_API_KEY", "")
                job_id = enqueue_transcription(audio_stt.getvalue(), audio_stt.name, groq_key)
                if job_id:
                    st.toast(t("mm_stt_queued_toast"), icon="🧵")
                    st.session_state.pending_stt_jobs.append({"job_id": job_id, "filename": audio_stt.name})
                    st.session_state.form_clear_counter += 1
                    st.rerun()
                proveedor_stt = get_groq_whisper_provider_fn()
                texto_transcrito, error_stt = proveedor_stt.transcribe(
                    audio_bytes=audio_stt.getvalue(),
                    filename=audio_stt.name,
                )
                if error_stt:
                    st.error(error_stt)
                else:
                    st.toast(t("mm_stt_done_toast"), icon="✅")
                    st.session_state.messages.append(
                        {
                            "role": "user",
                            "content": t("mm_audio_transcript_user", text=texto_transcrito),
                        }
                    )
                    if st.session_state.chat_id:
                        guardar_memoria_fn(st.session_state.chat_id, st.session_state.messages, st.session_state.api_keys)
                    st.session_state.form_clear_counter += 1
                    st.rerun()

    st.markdown("---")

    st.markdown(t("multimedia_tts_title"))
    st.caption(t("multimedia_tts_desc"))

    col_prov, col_voice = st.columns([1, 1])
    with col_prov:
        prov_tts_sel = st.selectbox(
            t("multimedia_tts_provider"),
            [t("multimedia_tts_edge"), t("multimedia_tts_openai")],
            key="tts_provider_sel",
        )

    with col_voice:
        if prov_tts_sel == t("multimedia_tts_openai"):
            voz_seleccionada = st.selectbox(
                t("mm_tts_voice_label"),
                ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                index=0,
                key="tts_voice_selector",
            )
        else:
            from src.services.audio_service import AVAILABLE_EDGE_VOICES

            voz_alias = st.selectbox(t("multimedia_tts_voice"), list(AVAILABLE_EDGE_VOICES.keys()), key="edge_voice_selector")
            voz_seleccionada = AVAILABLE_EDGE_VOICES[voz_alias]

    texto_para_tts = st.text_area(
        t("multimedia_tts_text"),
        placeholder=t("multimedia_tts_placeholder"),
        height=120,
        key=f"tts_input_text_{st.session_state.form_clear_counter}",
    )
    if st.button(t("multimedia_tts_button"), use_container_width=True, key="btn_tts"):
        if not texto_para_tts.strip():
            st.warning(t("multimedia_tts_empty"))
        elif len(texto_para_tts) > 4096:
            st.warning(
                t("mm_tts_text_too_long", n=len(texto_para_tts)),
            )
        else:
            with st.spinner(t("mm_tts_spinner", provider=prov_tts_sel)):
                if prov_tts_sel == t("multimedia_tts_openai"):
                    proveedor_tts = get_openai_tts_provider_fn(voice=voz_seleccionada)
                else:
                    proveedor_tts = get_edge_tts_provider_fn(voice=voz_seleccionada)

                _, audio_filepath, error_tts = proveedor_tts.synthesize(texto_para_tts)
            if error_tts:
                st.error(error_tts)
            else:
                st.toast(t("mm_tts_toast_ok"), icon="✅")
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": t(
                            "mm_tts_assistant_line",
                            preview=texto_para_tts[:50],
                        ),
                        "audio_path": audio_filepath,
                    }
                )
                if st.session_state.chat_id:
                    guardar_memoria_fn(st.session_state.chat_id, st.session_state.messages, st.session_state.api_keys)
                st.session_state.form_clear_counter += 1
                st.rerun()

    st.markdown("---")

    st.markdown(t("multimedia_image_title"))
    st.caption(t("multimedia_image_desc"))
    proveedor_imagen_sel = st.radio(
        t("multimedia_image_provider"),
        ["OpenAI DALL-E 3", "Stability AI"],
        horizontal=True,
        key="img_provider_radio",
    )
    prompt_imagen_gen = st.text_area(
        t("mm_img_prompt_label"),
        placeholder=t("mm_img_prompt_placeholder"),
        height=80,
        key=f"img_gen_prompt_{st.session_state.form_clear_counter}",
    )
    if proveedor_imagen_sel == "OpenAI DALL-E 3":
        col_size, col_quality = st.columns(2)
        with col_size:
            st.selectbox(t("multimedia_image_resolution"), ["1024x1024", "1792x1024", "1024x1792"], key="dalle_size")
        with col_quality:
            st.selectbox(t("multimedia_image_quality"), ["standard", "hd"], key="dalle_quality")
    else:
        st.selectbox(t("multimedia_image_ratio"), ["1:1", "16:9", "9:16", "3:2", "2:3", "4:5", "5:4"], key="stability_aspect")
        st.text_input(t("multimedia_image_negative"), placeholder=t("mm_img_negative_placeholder"), key="stability_negative")
    if st.button(t("multimedia_image_button"), use_container_width=True, key="btn_img_gen"):
        if not prompt_imagen_gen.strip():
            st.warning(t("multimedia_image_empty"))
        else:
            with st.spinner(t("mm_img_spinner", provider=proveedor_imagen_sel)):
                from src.services.image_gen_service import generate_image

                if proveedor_imagen_sel == "OpenAI DALL-E 3":
                    filepath_gen, error_gen = generate_image(
                        prompt=prompt_imagen_gen,
                        provider="openai_dalle3",
                        api_key=st.session_state.api_keys.get("OPENAI_API_KEY"),
                        size=st.session_state.get("dalle_size", "1024x1024"),
                        quality=st.session_state.get("dalle_quality", "standard"),
                    )
                else:
                    filepath_gen, error_gen = generate_image(
                        prompt=prompt_imagen_gen,
                        provider="stability_ai",
                        api_key=st.session_state.api_keys.get("STABILITY_API_KEY"),
                        groq_api_key=st.session_state.api_keys.get("GROQ_API_KEY"),
                        aspect_ratio=st.session_state.get("stability_aspect", "1:1"),
                        negative_prompt=st.session_state.get("stability_negative", ""),
                    )
            if error_gen:
                st.error(error_gen)
            else:
                st.toast(t("mm_img_toast_ok"), icon="✅")
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": t(
                            "mm_img_assistant_line",
                            provider=proveedor_imagen_sel,
                            prompt=prompt_imagen_gen,
                        ),
                        "image_path": filepath_gen,
                    }
                )
                if st.session_state.chat_id:
                    guardar_memoria_fn(st.session_state.chat_id, st.session_state.messages, st.session_state.api_keys)
                st.session_state.form_clear_counter += 1
                st.rerun()


def render_multimedia_sidebar_tools(
    panel_conversor_fn,
    secure_upload_check_fn,
    get_groq_whisper_provider_fn,
    get_openai_tts_provider_fn,
    get_edge_tts_provider_fn,
    guardar_memoria_fn,
) -> None:
    """Legacy wrapper: pending jobs + expander in sidebar."""
    process_pending_stt_jobs(guardar_memoria_fn)
    with st.expander(t("multimedia_title"), expanded=False):
        render_multimedia_tools_body(
            panel_conversor_fn=panel_conversor_fn,
            secure_upload_check_fn=secure_upload_check_fn,
            get_groq_whisper_provider_fn=get_groq_whisper_provider_fn,
            get_openai_tts_provider_fn=get_openai_tts_provider_fn,
            get_edge_tts_provider_fn=get_edge_tts_provider_fn,
            guardar_memoria_fn=guardar_memoria_fn,
        )
