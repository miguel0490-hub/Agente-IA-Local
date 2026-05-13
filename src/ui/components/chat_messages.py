"""Chat message rendering helpers."""

from __future__ import annotations

import os
import re

import streamlit as st

from src.core.i18n import TOOL_CONTEXT_PREFIX, t
from src.core.sanitizer import sanitize_markdown_text

_TOOL_ACTIONS = r"(?:create_file|edit_file|execute_code|query_rag|open_converter|search_web)"

_JSON_TOOL_BLOCK = re.compile(
    r"```json\s*\{[^}]*\"action\"\s*:\s*\"" + _TOOL_ACTIONS + r"\"[\s\S]*?```",
    re.DOTALL,
)
_RAW_JSON_TOOL = re.compile(
    r"\{\s*\"action\"\s*:\s*\"" + _TOOL_ACTIONS + r"\"[^}]*\}",
    re.DOTALL,
)


def _clean_tool_json_from_display(text: str) -> str:
    """Strips raw tool-call JSON blocks from text so users never see them."""
    text = _JSON_TOOL_BLOCK.sub("", text)
    text = _RAW_JSON_TOOL.sub("", text)
    return text.strip()


_LEGACY_TOOL_PREFIXES = (
    "RESULTADOS DE BÚSQUEDA",
    "RESULTADOS DEL CEREBRO RAG",
    "RESULTADO DE LA EJECUCIÓN",
    "INSTRUCCIONES POST-BÚSQUEDA",
    "WEB SEARCH RESULTS FOR",
    "EXECUTION RESULT (STDOUT",
    "RAG BRAIN RESULTS FOR",
    "The RAG brain found no",
    "RÉSULTATS RAG POUR",
    "RAG-ERGEBNISSE FÜR",
    "RESULTADOS RAG PARA",
    "RÉSULTATS WEB POUR",
    "WEBSUCHERGEBNISSE FÜR",
    "RESULTADOS DA PESQUISA WEB PARA",
    "RÉSULTAT D'EXÉCUTION",
    "AUSFÜHRUNGSERGEBNIS",
    "RESULTADO DA EXECUÇÃO",
)


def _is_internal_message(content: str) -> bool:
    """Returns True for system-internal messages that shouldn't be shown to the user."""
    if content.startswith(TOOL_CONTEXT_PREFIX):
        return True
    return any(content.startswith(p) for p in _LEGACY_TOOL_PREFIXES)


def render_chat_messages(messages: list, render_download_button_fn) -> None:
    """Renders full chat thread, including images, audio, and file downloads."""
    for idx, msg in enumerate(messages):
        if msg.get("role") == "system":
            continue
        content = msg.get("content", "")
        if _is_internal_message(content):
            continue
        avatar = "🧑‍💻" if msg["role"] == "user" else "🤖"
        with st.chat_message(msg["role"], avatar=avatar):
            display_content = content
            if msg["role"] == "assistant":
                display_content = _clean_tool_json_from_display(content)

            if display_content:
                st.markdown(sanitize_markdown_text(display_content))

            if msg.get("created_at"):
                st.caption(f"🕐 {msg['created_at'][:16].replace('T', ' ')}")

            if msg.get("image_path") and os.path.exists(msg.get("image_path")):
                filepath = msg["image_path"]
                from PIL import Image

                img = Image.open(filepath)
                st.image(img, caption=t("chat_image_caption"), use_container_width=True)
                render_download_button_fn(filepath)
            if msg.get("audio_path") and os.path.exists(msg.get("audio_path")):
                st.audio(msg.get("audio_path"))
                render_download_button_fn(msg.get("audio_path"))

            if msg.get("file_paths"):
                for fp in msg.get("file_paths"):
                    render_download_button_fn(fp)
