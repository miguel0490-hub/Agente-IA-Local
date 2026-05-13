"""Sidebar chat management section."""

from __future__ import annotations

import json
from datetime import datetime

import streamlit as st

from src.core.i18n import t


def _reset_composer_staging() -> None:
    """Clears chat-attachment staging when switching or creating chats."""
    st.session_state.staged_attachments = []
    st.session_state.attachment_hub_uploader_inc = int(st.session_state.get("attachment_hub_uploader_inc", 0)) + 1


def _export_messages_json(messages: list[dict]) -> str:
    return json.dumps(messages, ensure_ascii=False, indent=2)


def _export_messages_markdown(messages: list[dict]) -> str:
    lines: list[str] = []
    for msg in messages:
        role = msg.get("role", "unknown").capitalize()
        lines.append(f"## {role}\n")
        lines.append(msg.get("content", "") + "\n")
    return "\n".join(lines)


def _export_messages_html(messages: list[dict]) -> str:
    body_parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "unknown").capitalize()
        body_parts.append(f"<h2>{role}</h2>")
        content = (msg.get("content", "") or "").replace("\n", "<br>")
        body_parts.append(f"<p>{content}</p><hr>")
    return (
        "<html><head><meta charset='utf-8'>"
        "<style>body{font-family:sans-serif;max-width:800px;margin:auto;padding:20px}"
        "h2{color:#333}hr{border:none;border-top:1px solid #ddd}</style></head>"
        f"<body>{''.join(body_parts)}</body></html>"
    )


def render_chat_management(
    create_chat_fn,
    get_user_chats_fn,
    cargar_memoria_fn,
    search_chat_messages_fn=None,
    update_chat_title_fn=None,
) -> None:
    """Renders chat list/create/select inside sidebar."""
    st.header(t("my_chats"))

    if st.button(t("new_chat"), use_container_width=True):
        nuevo_id = create_chat_fn(st.session_state.user_id, t("new_chat_title"))
        st.session_state.chat_id = nuevo_id
        st.session_state.messages = []
        _reset_composer_staging()
        st.rerun()

    # --- Search ---
    search_query = st.text_input(
        t("search_chats"),
        key="chat_search_query",
        placeholder=t("search_placeholder"),
    )

    chats = get_user_chats_fn(st.session_state.user_id)
    st.session_state.chat_list = chats

    if search_query and search_chat_messages_fn:
        search_results = search_chat_messages_fn(st.session_state.user_id, search_query)
        if search_results:
            st.caption(t("search_results_count", count=len(search_results)))
            for result in search_results:
                label = f"**{result['title']}**\n{result['snippet']}…"
                if st.button(label, key=f"search_result_{result['chat_id']}", use_container_width=True):
                    st.session_state.chat_id = result["chat_id"]
                    st.session_state.messages = cargar_memoria_fn(result["chat_id"])
                    _reset_composer_staging()
                    st.session_state.auto_close_sidebar = True
                    st.rerun()
        else:
            st.caption(t("search_no_results"))
    elif st.session_state.chat_list:
        opciones_chat = {c["id"]: c["title"] for c in st.session_state.chat_list}

        if not st.session_state.chat_id and opciones_chat:
            st.session_state.chat_id = list(opciones_chat.keys())[0]
            st.session_state.messages = cargar_memoria_fn(st.session_state.chat_id)

        chat_seleccionado = st.selectbox(
            t("select_chat"),
            options=list(opciones_chat.keys()),
            format_func=lambda x: opciones_chat[x],
            index=list(opciones_chat.keys()).index(st.session_state.chat_id) if st.session_state.chat_id in opciones_chat else 0,
        )

        if chat_seleccionado != st.session_state.chat_id:
            st.session_state.chat_id = chat_seleccionado
            st.session_state.messages = cargar_memoria_fn(st.session_state.chat_id)
            _reset_composer_staging()
            st.session_state.auto_close_sidebar = True
            st.rerun()
    else:
        st.info(t("no_chats"))
        if not st.session_state.chat_id:
            nuevo_id = create_chat_fn(st.session_state.user_id, t("new_chat_title"))
            st.session_state.chat_id = nuevo_id
            st.session_state.messages = []
            _reset_composer_staging()
            st.rerun()

    # --- Rename current chat ---
    if update_chat_title_fn and st.session_state.chat_id:
        with st.expander(t("rename_chat")):
            new_name = st.text_input(t("rename_label"), key="rename_chat_input")
            if st.button(t("rename_button"), key="btn_rename_chat") and new_name.strip():
                update_chat_title_fn(st.session_state.chat_id, new_name.strip())
                st.rerun()

    # --- Export ---
    if st.session_state.get("messages"):
        with st.expander(t("export_chat")):
            msgs = st.session_state.messages
            ts = datetime.now().strftime("%Y%m%d_%H%M")

            st.download_button(
                t("export_json"),
                data=_export_messages_json(msgs),
                file_name=f"chat_{ts}.json",
                mime="application/json",
                use_container_width=True,
            )
            st.download_button(
                t("export_markdown"),
                data=_export_messages_markdown(msgs),
                file_name=f"chat_{ts}.md",
                mime="text/markdown",
                use_container_width=True,
            )
            st.download_button(
                t("export_html"),
                data=_export_messages_html(msgs),
                file_name=f"chat_{ts}.html",
                mime="text/html",
                use_container_width=True,
            )

    st.divider()
