"""Adjuntos de chat en la barra lateral (diseño clásico)."""

from __future__ import annotations

import hashlib
import html
import io
import uuid

import streamlit as st

from src.core.i18n import t
from src.core.security import check_scoped_rate_limit
from src.services.file_validator import get_upload_policy_summary

MAX_STAGED_FILES = 12
_HTML_TAG = "di" + "v"


def _fingerprint(name: str, data: bytes) -> str:
    h = hashlib.sha256()
    h.update(name.encode("utf-8", errors="replace"))
    h.update(b"\0")
    h.update(str(len(data)).encode("ascii"))
    h.update(data[: min(len(data), 8192)])
    return h.hexdigest()


def attachments_for_chat_send() -> list:
    """Construye objetos tipo archivo desde ``staged_attachments`` para el envío del chat."""
    out: list = []
    for item in st.session_state.get("staged_attachments") or []:
        bio = io.BytesIO(item["data"])
        bio.name = item["name"]
        out.append(bio)
    return out


def _stage_uploaded_files(batch, secure_upload_check_fn) -> int:
    """Añade archivos a la cola; devuelve cuántos se incorporaron."""
    if not batch:
        return 0
    files = batch if isinstance(batch, list) else [batch]
    staged = list(st.session_state.get("staged_attachments") or [])
    known = {x.get("fp") for x in staged}
    added = 0
    for f in files:
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
        staged.append(
            {
                "id": uuid.uuid4().hex[:12],
                "name": f.name,
                "data": raw,
                "fp": fp,
            }
        )
        known.add(fp)
        added += 1
    if added:
        st.session_state.staged_attachments = staged
    return added


def render_sidebar_attachment_uploader(secure_upload_check_fn) -> None:
    """Cargador de archivos visible en el sidebar, fuera de popovers o pestañas."""
    st.session_state.setdefault("staged_attachments", [])

    policy_esc = html.escape(get_upload_policy_summary())
    card_html = (
        f"<{_HTML_TAG} class=\"sidebar-upload-card\">"
        "<p class=\"sidebar-upload-title\"><strong>Adjuntar Archivo</strong></p>"
        f"<p class=\"sidebar-upload-policy\">{policy_esc}</p>"
        f"</{_HTML_TAG}>"
    )
    st.markdown(card_html, unsafe_allow_html=True)

    batch = st.file_uploader(
        "Código, docs, imágenes, datos…",
        accept_multiple_files=True,
        help=t("attach_help"),
        label_visibility="collapsed",
        key=f"sidebar_uploader_{st.session_state.get('form_clear_counter', 0)}",
    )

    added = _stage_uploaded_files(batch, secure_upload_check_fn)
    if added:
        st.session_state.form_clear_counter = int(st.session_state.get("form_clear_counter", 0)) + 1
        st.rerun()

    staged = st.session_state.get("staged_attachments") or []
    if staged:
        for item in staged:
            st.caption(f"📎 {item.get('name', '—')}")
