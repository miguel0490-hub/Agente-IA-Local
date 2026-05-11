"""Application bootstrap: DB init, garbage collection, cookie manager setup.

Extracts heavy initialization logic from app.py so it only composes UI.
"""

from __future__ import annotations

import os
import time

import streamlit as st

from src.core.config import CARPETA_IMAGENES
from src.core.logger import get_logger
from src.core.session_state import initialize_session_state
from src.database.database import cleanup_expired_tokens, init_db

logger = get_logger(__name__)


@st.cache_resource(show_spinner=False)
def start_database() -> None:
    """Runs DB table creation and token cleanup once per server lifecycle."""
    init_db()
    cleanup_expired_tokens()


def run_garbage_collector() -> None:
    """Removes temp files older than 24 hours."""
    now = time.time()
    for directory in [CARPETA_IMAGENES, "data/temp"]:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                if os.path.isfile(filepath) and os.stat(filepath).st_mtime < now - 86400:
                    try:
                        os.remove(filepath)
                    except OSError as exc:
                        logger.warning("No se pudo eliminar temporal %s: %s", filepath, exc)


def bootstrap_app() -> None:
    """Runs all one-time initialization: DB, session state, GC, output dirs."""
    start_database()

    initialize_session_state()

    if "gc_run" not in st.session_state:
        run_garbage_collector()
        st.session_state.gc_run = True

    os.makedirs(CARPETA_IMAGENES, exist_ok=True)
