"""Chat message rendering helpers."""

from __future__ import annotations

import os
import streamlit as st
from src.core.sanitizer import sanitize_markdown_text


def render_chat_messages(messages: list, render_download_button_fn) -> None:
    """Renders full chat thread, including images, audio, and file downloads."""
    for msg in messages:
        if msg.get("role") == "system":
            continue
        avatar = "🧑‍💻" if msg["role"] == "user" else "🤖"
        with st.chat_message(msg["role"], avatar=avatar):
            if msg.get("content"):
                st.markdown(sanitize_markdown_text(msg["content"]))
            if msg.get("image_path") and os.path.exists(msg.get("image_path")):
                filepath = msg["image_path"]
                from PIL import Image

                img = Image.open(filepath)
                st.image(img, caption="Obra generada", use_container_width=True)
                render_download_button_fn(filepath)
            if msg.get("audio_path") and os.path.exists(msg.get("audio_path")):
                st.audio(msg.get("audio_path"))
                render_download_button_fn(msg.get("audio_path"))

            if msg.get("file_paths"):
                for fp in msg.get("file_paths"):
                    render_download_button_fn(fp)
