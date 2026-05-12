"""Converter dialog UI logic extracted from app.py."""

from __future__ import annotations

import os
import uuid

import streamlit as st

from src.core.i18n import t
from src.core.security import check_scoped_rate_limit
from src.services.task_queue import enqueue_conversion, get_job_status
from src.services.file_validator import get_upload_policy_summary


def render_converter_dialog(carpeta_imagenes: str, secure_upload_check, run_conversion, guardar_memoria_fn) -> None:
    """Renders conversion panel and injects successful outputs to chat."""
    pending_jobs = st.session_state.setdefault("pending_conversion_jobs", [])
    remaining_jobs = []
    for job in pending_jobs:
        status = get_job_status(job.get("job_id"))
        if status["status"] == "finished":
            result = status.get("result") or {}
            if result.get("ok") and result.get("output_path"):
                out = result["output_path"]
                st.success(f"✅ Conversión completada ({job.get('filename')}).")
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": f"🔄 *Conversión asíncrona completada:* `{job.get('filename')}`",
                        "file_paths": [out],
                    }
                )
                if st.session_state.chat_id:
                    guardar_memoria_fn(st.session_state.chat_id, st.session_state.messages, st.session_state.api_keys)
            else:
                st.error(f"❌ Conversión asíncrona fallida ({job.get('filename')}).")
        elif status["status"] == "failed":
            st.error(f"❌ Job de conversión falló: {status.get('error') or 'error desconocido'}")
        else:
            remaining_jobs.append(job)
    st.session_state.pending_conversion_jobs = remaining_jobs

    st.write(t("converter_intro"))
    archivo_conv = st.file_uploader(t("converter_upload"), key=f"uploader_conv_{st.session_state.form_clear_counter}")
    st.caption(get_upload_policy_summary())
    if archivo_conv:
        if not check_scoped_rate_limit(str(st.session_state.user_id), scope="uploads"):
            st.error(t("upload_rate_limit"))
            return
        check = secure_upload_check(archivo_conv.name, archivo_conv.getvalue())
        if not check.ok:
            st.error(t("upload_blocked", reason=check.reason))
            return

    if archivo_conv:
        st.info(f"{t('converter_detected')} {archivo_conv.name}")
        formato_destino = st.text_input(t("converter_format"), value=st.session_state.get("suggested_format", ""))

        if st.button(t("converter_button"), use_container_width=True):
            if formato_destino:
                formato_destino = formato_destino.strip().replace(".", "")
                with st.spinner(f"Convirtiendo a .{formato_destino} (Aceleración Local)..."):
                    os.makedirs("data/temp", exist_ok=True)
                    input_ext = os.path.splitext(archivo_conv.name)[1]
                    temp_input = f"data/temp/in_{uuid.uuid4().hex[:8]}{input_ext}"
                    with open(temp_input, "wb") as f:
                        f.write(archivo_conv.getbuffer())

                    output_name = f"conv_{uuid.uuid4().hex[:8]}.{formato_destino}"
                    temp_output = os.path.join(carpeta_imagenes, output_name)

                    job_id = enqueue_conversion(temp_input, temp_output)
                    if job_id:
                        st.toast("🧵 Conversión encolada en segundo plano.", icon="🧵")
                        st.session_state.pending_conversion_jobs.append({"job_id": job_id, "filename": output_name})
                        st.session_state.form_clear_counter += 1
                        st.rerun()

                    exito = run_conversion(temp_input, temp_output)
                    if exito:
                        st.toast(t("converter_success"), icon="✅")
                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "content": f"🔄 *Archivo convertido a `.{formato_destino}` exitosamente.*",
                                "file_paths": [temp_output],
                            }
                        )
                        if st.session_state.chat_id:
                            guardar_memoria_fn(st.session_state.chat_id, st.session_state.messages, st.session_state.api_keys)
                        st.session_state.form_clear_counter += 1
                        st.rerun()
                    else:
                        st.error(t("converter_failed"))

                    if os.path.exists(temp_input):
                        os.remove(temp_input)
