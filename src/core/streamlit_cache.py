"""Caché en session_state para evitar consultas DB repetidas en cada rerun de Streamlit."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

import streamlit as st

T = TypeVar("T")

_CACHE_GEN_KEY = "_sidebar_cache_gen"


def invalidate_sidebar_cache() -> None:
    """Invalida listas/perfil en caché tras crear, borrar o editar chats o perfil."""
    st.session_state[_CACHE_GEN_KEY] = int(st.session_state.get(_CACHE_GEN_KEY, 0)) + 1


def _cache_gen() -> int:
    return int(st.session_state.get(_CACHE_GEN_KEY, 0))


def _session_cache_get(key: str, loader: Callable[[], T]) -> T:
    if key not in st.session_state:
        st.session_state[key] = loader()
    return st.session_state[key]


def cached_user_chats(user_id: int, fetch_fn: Callable[[int], list]) -> list:
    gen = _cache_gen()
    key = f"_cached_chats_{user_id}_{gen}"
    return _session_cache_get(key, lambda: fetch_fn(user_id))


def cached_user_profile(user_id: int, fetch_fn: Callable[[int], Any]) -> Any:
    gen = _cache_gen()
    key = f"_cached_profile_{user_id}_{gen}"
    return _session_cache_get(key, lambda: fetch_fn(user_id))


def cached_is_admin(user_id: int, fetch_fn: Callable[[int], bool]) -> bool:
    gen = _cache_gen()
    key = f"_cached_is_admin_{user_id}_{gen}"
    return _session_cache_get(key, lambda: bool(fetch_fn(user_id)))
