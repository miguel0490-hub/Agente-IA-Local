"""Staged file attachments + multimedia tools above the chat input (Gemini-style hub)."""

from __future__ import annotations

import base64
import hashlib
import html
import io
import uuid
from pathlib import Path

import streamlit as st

from src.core.i18n import t
from src.core.security import check_scoped_rate_limit
from src.services.file_validator import get_upload_policy_summary
from src.ui.multimedia.sidebar_tools import process_pending_stt_jobs, render_multimedia_tools_body

MAX_STAGED_FILES = 12

_IMAGE_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".tif", ".ico", ".svg"}
)

_VIDEO_SUFFIXES = frozenset({".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv"})
_AUDIO_SUFFIXES = frozenset({".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"})
_CODE_SUFFIXES = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".java",
        ".go",
        ".rs",
        ".c",
        ".cpp",
        ".h",
        ".cs",
        ".rb",
        ".php",
        ".swift",
        ".kt",
        ".sql",
        ".sh",
        ".ps1",
        ".r",
    }
)
_DOC_SUFFIXES = frozenset({".pdf", ".doc", ".docx", ".odt", ".rtf"})
_SHEET_SUFFIXES = frozenset({".csv", ".xlsx", ".xls", ".ods"})
_ARCHIVE_SUFFIXES = frozenset({".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"})
_DATA_SUFFIXES = frozenset({".json", ".yaml", ".yml", ".xml", ".toml", ".ini", ".env"})
_TEXTLIKE_SUFFIXES = frozenset(
    {".md", ".markdown", ".txt", ".log", ".rst", ".tex", ".me", ".readme"}
)


def _is_image_filename(name: str) -> bool:
    return Path(name or "").suffix.lower() in _IMAGE_SUFFIXES


def _icon_for_filename(name: str) -> str:
    ext = Path(name or "").suffix.lower()
    if ext in _IMAGE_SUFFIXES:
        return "🖼"
    if ext in _VIDEO_SUFFIXES:
        return "🎬"
    if ext in _AUDIO_SUFFIXES:
        return "🎵"
    if ext in _DOC_SUFFIXES:
        return "📕"
    if ext in _SHEET_SUFFIXES:
        return "📊"
    if ext in _ARCHIVE_SUFFIXES:
        return "🗜"
    if ext in _CODE_SUFFIXES:
        return "💻"
    if ext in _DATA_SUFFIXES:
        return "📋"
    if ext in _TEXTLIKE_SUFFIXES:
        return "📝"
    if ext in {".html", ".htm", ".css"}:
        return "🌐"
    if ext:
        return "📄"
    return "📎"


def _thumb_data_uri(data: bytes, name: str) -> str | None:
    """PNG thumbnail data URI for small preview, or None to fall back to icon."""
    if len(data) > 450_000:
        return None
    try:
        from PIL import Image

        im = Image.open(io.BytesIO(data))
        im.thumbnail((52, 52))
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None


def _glass_chip_html(
    *,
    title: str,
    label_esc: str,
    icon: str,
    image_thumb_uri: str | None,
) -> str:
    """Single attachment card: frosted panel + icon or thumbnail + filename."""
    glass = (
        "background:rgba(15,23,42,0.48);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);"
        "border:1px solid rgba(148,163,184,0.32);border-radius:14px;padding:8px 10px 10px;"
        "box-shadow:0 2px 14px rgba(0,0,0,0.28);margin:0 8px 8px 0;"
    )
    if image_thumb_uri:
        body = (
            f'<img src="{image_thumb_uri}" alt="" '
            'style="width:48px;height:48px;object-fit:cover;border-radius:10px;display:block;margin:0 auto 8px;" />'
            f'<div style="font-size:0.78rem;color:#e2e8f0;font-weight:500;text-align:center;'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{label_esc}</div>'
        )
    else:
        body = (
            '<div style="display:flex;align-items:center;gap:8px;min-width:0;">'
            f'<span style="font-size:1.1rem;line-height:1;flex-shrink:0;">{icon}</span>'
            '<span style="color:#e2e8f0;font-size:0.78rem;font-weight:500;min-width:0;flex:1;'
            'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
            f"{label_esc}</span>"
            "</div>"
        )
    return f'<div title="{title}" style="{glass}">{body}</div>'


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

    staged = list(st.session_state.staged_attachments)
    if staged:
        st.caption(t("hub_staged_hint"))
        n = len(staged)
        # Columna izquierda agrupa chips; la derecha absorbe espacio vacío.
        cluster_w = max(52, min(200, 36 + n * 20))
        pack, _rest = st.columns([cluster_w, 100])
        with pack:
            inner_weights: list[int] = []
            for item in staged:
                name = item.get("name") or ""
                if _is_image_filename(name):
                    inner_weights.append(max(40, 56))
                else:
                    inner_weights.append(max(26, min(62, 20 + len(name) // 2)))
            inners = st.columns(inner_weights)
            for i, item in enumerate(staged):
                with inners[i]:
                    nm = item.get("name") or "—"
                    icon = _icon_for_filename(nm)
                    short = nm if len(nm) <= 36 else nm[:33] + "…"
                    esc_label = html.escape(short)
                    esc_title = html.escape(nm, quote=True)
                    thumb = None
                    if _is_image_filename(nm):
                        thumb = _thumb_data_uri(item["data"], nm)
                    chip_html = _glass_chip_html(
                        title=esc_title,
                        label_esc=esc_label,
                        icon=icon,
                        image_thumb_uri=thumb,
                    )
                    st.markdown(chip_html, unsafe_allow_html=True)
                    if st.button(
                        "✕",
                        key=f"hub_chip_rm_{item['id']}",
                        help=t("hub_remove_attachment"),
                        type="secondary",
                    ):
                        st.session_state.staged_attachments = [
                            x for x in st.session_state.staged_attachments if x["id"] != item["id"]
                        ]
                        st.rerun()
