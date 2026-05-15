"""Lightweight internationalization framework with Streamlit session persistence.

Usage:
    from src.core.i18n import t
    st.markdown(t("welcome_message"))
"""

from __future__ import annotations

import json
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger(__name__)

_TRANSLATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "translations"
_translations: dict[str, dict[str, str]] = {}
_current_lang: str = "es"

SUPPORTED_LANGUAGES = {
    "es": "Español",
    "en": "English",
    "fr": "Français",
    "de": "Deutsch",
    "pt": "Português",
}


def _load_language(lang: str) -> dict[str, str]:
    """Loads a translation file from disk."""
    path = _TRANSLATIONS_DIR / f"{lang}.json"
    if not path.exists():
        logger.warning("Translation file not found: %s", path)
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to load translations for %s: %s", lang, e)
        return {}


def _resolve_lang() -> str:
    """Resolves the active language from Streamlit session_state or the module global."""
    global _current_lang
    try:
        import streamlit as st
        stored = st.session_state.get("app_language")
        if stored and stored in SUPPORTED_LANGUAGES and stored != _current_lang:
            _current_lang = stored
            if stored not in _translations:
                _translations[stored] = _load_language(stored)
    except Exception:
        pass
    return _current_lang


def set_language(lang: str) -> None:
    """Sets the active language and persists it to Streamlit session_state."""
    global _current_lang
    if lang not in SUPPORTED_LANGUAGES:
        logger.warning("Unsupported language: %s, falling back to 'es'", lang)
        lang = "es"
    _current_lang = lang
    if lang not in _translations:
        _translations[lang] = _load_language(lang)
    try:
        import streamlit as st
        st.session_state.app_language = lang
    except Exception:
        pass


def get_language() -> str:
    """Returns the current language code, restoring from session if needed."""
    return _resolve_lang()


def t(key: str, **kwargs) -> str:
    """Translates a key to the current language. Falls back to Spanish, then the key itself."""
    lang = _resolve_lang()

    if lang not in _translations:
        _translations[lang] = _load_language(lang)

    text = _translations.get(lang, {}).get(key)
    if text is None:
        if "es" not in _translations:
            _translations["es"] = _load_language("es")
        text = _translations.get("es", {}).get(key, key)

    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def all_locale_values_for_key(key: str) -> frozenset[str]:
    """All translated values of ``key`` across supported languages (e.g. default chat titles)."""
    out: set[str] = set()
    for code in SUPPORTED_LANGUAGES:
        data = _load_language(code)
        val = data.get(key)
        if val:
            out.add(val)
    return frozenset(out)


# Prefix for tool-loop "user" messages hidden from chat UI (multilingual body after prefix).
TOOL_CONTEXT_PREFIX = "[INTERNAL_TOOL_CONTEXT]\n"
