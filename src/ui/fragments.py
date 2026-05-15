"""Wrappers @st.fragment para acotar reruns de Streamlit."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import streamlit as st

_fragment = getattr(st, "fragment", None)


def _maybe_fragment(fn: Callable) -> Callable:
    if _fragment is None:
        return fn
    return _fragment(fn)


@_maybe_fragment
def render_sidebar_fragment(render_fn: Callable[[], None]) -> None:
    render_fn()


@_maybe_fragment
def render_chat_workspace_fragment(
    messages: list,
    render_messages_fn: Callable[[list], None],
    handle_chat_fn: Callable[..., Any],
    **chat_kwargs: Any,
) -> None:
    render_messages_fn(messages)
    handle_chat_fn(**chat_kwargs)
