"""Sidebar chat management section."""

from __future__ import annotations

import streamlit as st


def render_chat_management(create_chat_fn, get_user_chats_fn, cargar_memoria_fn, panel_ajustes_fn) -> None:
    """Renders chat list/create/select and settings trigger inside sidebar."""
    st.header("💬 Mis Chats")

    if st.button("➕ Nuevo Chat", use_container_width=True):
        nuevo_id = create_chat_fn(st.session_state.user_id, "Nuevo Chat")
        st.session_state.chat_id = nuevo_id
        st.session_state.messages = []
        st.rerun()

    chats = get_user_chats_fn(st.session_state.user_id)
    st.session_state.chat_list = chats

    if st.session_state.chat_list:
        opciones_chat = {c["id"]: c["title"] for c in st.session_state.chat_list}

        if not st.session_state.chat_id and opciones_chat:
            st.session_state.chat_id = list(opciones_chat.keys())[0]
            st.session_state.messages = cargar_memoria_fn(st.session_state.chat_id)

        chat_seleccionado = st.selectbox(
            "Seleccionar chat:",
            options=list(opciones_chat.keys()),
            format_func=lambda x: opciones_chat[x],
            index=list(opciones_chat.keys()).index(st.session_state.chat_id) if st.session_state.chat_id in opciones_chat else 0,
        )

        if chat_seleccionado != st.session_state.chat_id:
            st.session_state.chat_id = chat_seleccionado
            st.session_state.messages = cargar_memoria_fn(st.session_state.chat_id)
            st.session_state.auto_close_sidebar = True
            st.rerun()
    else:
        st.info("No tienes chats.")
        if not st.session_state.chat_id:
            nuevo_id = create_chat_fn(st.session_state.user_id, "Nuevo Chat")
            st.session_state.chat_id = nuevo_id
            st.session_state.messages = []
            st.rerun()

    st.divider()
    if st.button("⚙️ Centro de Control", key="btn_settings", use_container_width=True):
        st.session_state.show_settings = True
        st.rerun()

    if st.session_state.show_settings:
        st.session_state.show_settings = False
        panel_ajustes_fn()
    st.divider()
