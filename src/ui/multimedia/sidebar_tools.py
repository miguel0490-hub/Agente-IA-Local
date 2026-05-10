"""Sidebar multimedia tools UI (STT, TTS, Image Gen)."""

from __future__ import annotations

import streamlit as st
from src.core.security import check_scoped_rate_limit
from src.services.file_validator import get_upload_policy
from src.services.task_queue import enqueue_transcription, get_job_status


def render_multimedia_sidebar_tools(
    panel_conversor_fn,
    secure_upload_check_fn,
    get_groq_whisper_provider_fn,
    get_openai_tts_provider_fn,
    get_edge_tts_provider_fn,
    guardar_memoria_fn,
) -> None:
    """Renders multimedia expander and routes successful outputs to chat thread."""
    pending_stt_jobs = st.session_state.setdefault("pending_stt_jobs", [])
    remaining_stt_jobs = []
    for job in pending_stt_jobs:
        status = get_job_status(job.get("job_id"))
        if status["status"] == "finished":
            result = status.get("result") or {}
            if result.get("ok"):
                text = (result.get("text") or "").strip()
                st.success("✅ Transcripción asíncrona completada.")
                st.session_state.messages.append({"role": "user", "content": f"🎙️ *(Audio transcrito)*:\n{text}"})
                if st.session_state.chat_id:
                    guardar_memoria_fn(st.session_state.chat_id, st.session_state.messages, st.session_state.api_keys)
            else:
                st.error(result.get("error") or "❌ Falló la transcripción asíncrona.")
        elif status["status"] == "failed":
            st.error(f"❌ Job de transcripción falló: {status.get('error') or 'error desconocido'}")
        else:
            remaining_stt_jobs.append(job)
    st.session_state.pending_stt_jobs = remaining_stt_jobs

    with st.expander("🛠️ Herramientas Multimedia", expanded=False):
        if st.button("🔄 Estudio de Conversión", use_container_width=True):
            st.session_state["suggested_format"] = ""
            panel_conversor_fn()

        st.markdown("---")

        st.markdown("**🎙️ Transcripción STT — Groq Whisper**")
        st.caption("Transcribe audio a texto con Whisper Large v3.")
        audio_stt = st.file_uploader(
            "Sube tu audio o vídeo",
            key=f"uploader_stt_{st.session_state.form_clear_counter}",
        )
        if get_upload_policy() == "permissive":
            st.caption("Modo pruebas: transcripción con subida abierta para audio/vídeo (no ejecutables).")
        else:
            st.caption("Límite para transcripción: audio/vídeo hasta 100 MB.")
        if audio_stt:
            if not check_scoped_rate_limit(str(st.session_state.user_id), scope="uploads"):
                st.error("⏳ Has alcanzado el límite temporal de subidas. Espera un momento e inténtalo de nuevo.")
                audio_stt = None
            else:
                check = secure_upload_check_fn(audio_stt.name, audio_stt.getvalue())
                if not check.ok:
                    st.error(f"⛔ Upload bloqueado: {check.reason}")
                    audio_stt = None

        if audio_stt:
            st.audio(audio_stt, format=f"audio/{audio_stt.name.split('.')[-1]}")
            if st.button("🎤 Transcribir", use_container_width=True, key="btn_stt"):
                with st.spinner("Enviando a Groq Whisper… ⚡"):
                    groq_key = st.session_state.api_keys.get("GROQ_API_KEY", "")
                    job_id = enqueue_transcription(audio_stt.getvalue(), audio_stt.name, groq_key)
                    if job_id:
                        st.toast("🧵 Transcripción encolada en segundo plano.", icon="🧵")
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
                        st.toast("✅ Transcripción completada", icon="✅")
                        st.session_state.messages.append(
                            {
                                "role": "user",
                                "content": f"🎙️ *(Audio transcrito)*:\n{texto_transcrito}",
                            }
                        )
                        if st.session_state.chat_id:
                            guardar_memoria_fn(st.session_state.chat_id, st.session_state.messages, st.session_state.api_keys)
                        st.session_state.form_clear_counter += 1
                        st.rerun()

        st.markdown("---")

        st.markdown("**🔊 Síntesis de Voz — TTS**")
        st.caption("Convierte texto a voz natural.")

        col_prov, col_voice = st.columns([1, 1])
        with col_prov:
            prov_tts_sel = st.selectbox("Proveedor:", ["Edge TTS (Gratis)", "OpenAI TTS (Pago)"], key="tts_provider_sel")

        with col_voice:
            if prov_tts_sel == "OpenAI TTS (Pago)":
                voz_seleccionada = st.selectbox(
                    "Voz:",
                    ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                    index=0,
                    key="tts_voice_selector",
                )
            else:
                from src.services.audio_service import AVAILABLE_EDGE_VOICES

                voz_alias = st.selectbox("Voz (Regional):", list(AVAILABLE_EDGE_VOICES.keys()), key="edge_voice_selector")
                voz_seleccionada = AVAILABLE_EDGE_VOICES[voz_alias]

        texto_para_tts = st.text_area(
            "Texto a sintetizar:",
            placeholder="Escribe aquí el texto que quieres escuchar…",
            height=180,
            key=f"tts_input_text_{st.session_state.form_clear_counter}",
        )
        if st.button("🔊 Generar Audio", use_container_width=True, key="btn_tts"):
            if not texto_para_tts.strip():
                st.warning("⚠️ Escribe algo antes de sintetizar.")
            elif len(texto_para_tts) > 4096:
                st.warning(
                    f"⚠️ El texto es demasiado largo ({len(texto_para_tts)}/4096 caracteres). "
                    "Por favor, recórtalo para poder generar el audio."
                )
            else:
                with st.spinner(f"Sintetizando con {prov_tts_sel}…"):
                    if prov_tts_sel == "OpenAI TTS (Pago)":
                        proveedor_tts = get_openai_tts_provider_fn(voice=voz_seleccionada)
                    else:
                        proveedor_tts = get_edge_tts_provider_fn(voice=voz_seleccionada)

                    _, audio_filepath, error_tts = proveedor_tts.synthesize(texto_para_tts)
                if error_tts:
                    st.error(error_tts)
                else:
                    st.toast("✅ ¡Audio generado!", icon="✅")
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": f"🔊 *Audio sintetizado:* '{texto_para_tts[:50]}...'",
                            "audio_path": audio_filepath,
                        }
                    )
                    if st.session_state.chat_id:
                        guardar_memoria_fn(st.session_state.chat_id, st.session_state.messages, st.session_state.api_keys)
                    st.session_state.form_clear_counter += 1
                    st.rerun()

        st.markdown("---")

        st.markdown("**🎨 Generador de Assets — Texto a Imagen**")
        st.caption("Genera imágenes con DALL-E 3 o Stability AI.")
        proveedor_imagen_sel = st.radio(
            "Proveedor:",
            ["OpenAI DALL-E 3", "Stability AI"],
            horizontal=True,
            key="img_provider_radio",
        )
        prompt_imagen_gen = st.text_area(
            "Prompt:",
            placeholder="Ej: A futuristic robot reading a book…",
            height=80,
            key=f"img_gen_prompt_{st.session_state.form_clear_counter}",
        )
        if proveedor_imagen_sel == "OpenAI DALL-E 3":
            col_size, col_quality = st.columns(2)
            with col_size:
                st.selectbox("Resolución:", ["1024x1024", "1792x1024", "1024x1792"], key="dalle_size")
            with col_quality:
                st.selectbox("Calidad:", ["standard", "hd"], key="dalle_quality")
        else:
            st.selectbox("Proporción:", ["1:1", "16:9", "9:16", "3:2", "2:3", "4:5", "5:4"], key="stability_aspect")
            st.text_input("Prompt negativo (opcional):", placeholder="Ej: blurry, low quality", key="stability_negative")
        if st.button("🎨 Generar Imagen", use_container_width=True, key="btn_img_gen"):
            if not prompt_imagen_gen.strip():
                st.warning("⚠️ Escribe un prompt antes de generar.")
            else:
                with st.spinner(f"Generando con {proveedor_imagen_sel}…"):
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
                    st.toast("✅ ¡Imagen generada!", icon="✅")
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": f"🎨 *Asset generado con {proveedor_imagen_sel}:* '{prompt_imagen_gen}'",
                            "image_path": filepath_gen,
                        }
                    )
                    if st.session_state.chat_id:
                        guardar_memoria_fn(st.session_state.chat_id, st.session_state.messages, st.session_state.api_keys)
                    st.session_state.form_clear_counter += 1
                    st.rerun()
