"""Staged file attachments + multimedia tools above the chat input (Gemini-style hub)."""

from __future__ import annotations

import hashlib
import io
import uuid

import streamlit as st

from src.core.i18n import t
from src.core.security import check_scoped_rate_limit
from src.services.file_validator import get_upload_policy_summary
from src.ui.multimedia.sidebar_tools import process_pending_stt_jobs, render_multimedia_tools_body

MAX_STAGED_FILES = 12


def _fingerprint(name: str, data: bytes) -> str:
    h = hashlib.sha256()
    h.update(name.encode("utf-8", errors="replace"))
    h.update(b"\0")
    h.update(str(len(data)).encode("ascii"))
    h.update(data[: min(len(data), 8192)])
    return h.hexdigest()


def attachments_for_chat_send() -> list:
    """Builds file-like objects from `staged_attachments` for `handle_chat_interaction`."""
    out: list = []
    for item in st.session_state.get("staged_attachments") or []:
        bio = io.BytesIO(item["data"])
        bio.name = item["name"]
        out.append(bio)
    return out


def render_chat_composer_hub(
    secure_upload_check_fn,
    panel_conversor_fn,
    get_groq_whisper_provider_fn,
    get_openai_tts_provider_fn,
    get_edge_tts_provider_fn,
    guardar_memoria_fn,
) -> None:
    """Renders STT job toasts, attachment staging, and multimedia tools in the main column."""
    process_pending_stt_jobs(guardar_memoria_fn)

    st.session_state.setdefault("staged_attachments", [])
    st.session_state.setdefault("attachment_hub_uploader_inc", 0)

    col_a, col_b = st.columns(2)
    with col_a:
        with st.expander(f"📎 {t('hub_attachments_expander')}", expanded=False):
            st.caption(get_upload_policy_summary())
            uploader_key = (
                f"chat_hub_uploader_{st.session_state.form_clear_counter}_"
                f"{st.session_state.attachment_hub_uploader_inc}"
            )
            batch = st.file_uploader(
                t("hub_file_uploader_label"),
                accept_multiple_files=True,
                help=t("attach_help"),
                key=uploader_key,
            )
            if batch:
                staged = list(st.session_state.staged_attachments)
                known = {x["fp"] for x in staged}
                added = 0
                for f in batch:
                    raw = f.getvalue()
                    fp = _fingerprint(f.name, raw)
                    if fp in known:
                        continue
                    if len(staged) >= MAX_STAGED_FILES:
                        st.warning(t("hub_max_staged", max=MAX_STAGED_FILES))
                        break
                    if not check_scoped_rate_limit(str(st.session_state.user_id), scope="uploads"):
                        st.error(t("upload_rate_limit"))
                        break
                    check = secure_upload_check_fn(f.name, raw)
                    if not check.ok:
                        st.error(t("upload_blocked", reason=check.reason))
                        continue
                    item_id = uuid.uuid4().hex[:12]
                    staged.append({"id": item_id, "name": f.name, "data": raw, "fp": fp})
                    known.add(fp)
                    added += 1
                if added:
                    st.session_state.staged_attachments = staged
                    st.session_state.attachment_hub_uploader_inc = int(
                        st.session_state.attachment_hub_uploader_inc
                    ) + 1
                    st.rerun()
            if st.button(t("hub_clear_all_attachments"), key="hub_btn_clear_attachments"):
                st.session_state.staged_attachments = []
                st.session_state.attachment_hub_uploader_inc = int(
                    st.session_state.attachment_hub_uploader_inc
                ) + 1
                st.rerun()

    with col_b:
        with st.expander(f"🎛️ {t('hub_multimedia_expander')}", expanded=False):
            render_multimedia_tools_body(
                panel_conversor_fn=panel_conversor_fn,
                secure_upload_check_fn=secure_upload_check_fn,
                get_groq_whisper_provider_fn=get_groq_whisper_provider_fn,
                get_openai_tts_provider_fn=get_openai_tts_provider_fn,
                get_edge_tts_provider_fn=get_edge_tts_provider_fn,
                guardar_memoria_fn=guardar_memoria_fn,
            )

    staged = st.session_state.staged_attachments
    if staged:
        st.caption(t("hub_staged_hint"))
        idx = 0
        while idx < len(staged):
            row_items = staged[idx : idx + 6]
            row_cols = st.columns(len(row_items))
            for col, item in zip(row_cols, row_items):
                with col:
                    short = item["name"] if len(item["name"]) <= 18 else item["name"][:15] + "…"
                    if st.button(
                        f"📎 {short} ✕",
                        key=f"hub_chip_rm_{item['id']}",
                        help=t("hub_remove_attachment"),
                    ):
                        st.session_state.staged_attachments = [
                            x for x in st.session_state.staged_attachments if x["id"] != item["id"]
                        ]
                        st.rerun()
            idx += 6
