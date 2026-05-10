"""Centralized sanitization helpers for untrusted text/HTML."""

from __future__ import annotations

import html

try:
    import bleach
except Exception:  # pragma: no cover
    bleach = None


def sanitize_markdown_text(value: str) -> str:
    """Sanitizes untrusted markdown text by neutralizing embedded HTML."""
    if not value:
        return ""
    # Make sanitizer idempotent for texts that already contain HTML entities.
    text = html.unescape(str(value))
    if bleach:
        # No HTML tags are allowed; markdown syntax remains plain text.
        cleaned = bleach.clean(text, tags=[], attributes={}, protocols=[], strip=True)
        return html.unescape(cleaned)
    # Fallback: escape only HTML metacharacters, preserving quotes for readability.
    return html.escape(text, quote=False)
