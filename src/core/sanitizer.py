"""Centralized sanitization helpers for untrusted text/HTML."""

from __future__ import annotations

import html
import re

try:
    import bleach
except Exception:  # pragma: no cover
    bleach = None

_INVISIBLE_CHARS = re.compile(
    r"[\u200b\u200c\u200d\u200e\u200f\u202a-\u202e\u2060\u2066-\u2069\ufeff\u00ad]"
)


def sanitize_markdown_text(value: str) -> str:
    """Sanitizes untrusted markdown text by neutralizing embedded HTML."""
    if not value:
        return ""
    text = html.unescape(str(value))
    if bleach:
        cleaned = bleach.clean(text, tags=[], attributes={}, protocols=[], strip=True)
        return html.unescape(cleaned)
    return html.escape(text, quote=False)


def escape_user_data(value: str) -> str:
    """Escapes a user-controlled string for safe embedding in HTML.

    Unlike sanitize_markdown_text (which preserves markdown), this aggressively
    escapes ALL HTML entities including quotes — suitable for usernames, emails,
    subjects, and any DB-sourced string rendered inside HTML attributes or tags.
    """
    if not value:
        return ""
    text = _INVISIBLE_CHARS.sub("", str(value))
    return html.escape(text, quote=True)


def sanitize_html_output(value: str, *, allowed_tags: frozenset[str] | None = None) -> str:
    """Sanitizes HTML allowing only a controlled set of tags.

    Useful for rendering rich content (e.g. LLM output) while blocking script injection.
    """
    if not value:
        return ""
    tags = list(allowed_tags) if allowed_tags else []
    if bleach:
        return bleach.clean(str(value), tags=tags, attributes={}, protocols=["https", "http"], strip=True)
    return html.escape(str(value), quote=False)
