"""Context window management: token counting and budget enforcement.

Provides token estimation before sending messages to LLMs and applies
trimming strategies when the context exceeds the model's budget.
"""

from __future__ import annotations

import os
import re
from typing import Any

from src.core.logger import get_logger

logger = get_logger(__name__)

_CHARS_PER_TOKEN_ESTIMATE = 4

_MODEL_BUDGETS: dict[str, int] = {
    "gemini-2.5-pro": 1_000_000,
    "llama-3.3-70b-versatile": 128_000,
    "llama-3.1-8b-instant": 8_192,
    "openrouter/auto": 128_000,
}

_DEFAULT_BUDGET = int(os.getenv("LLM_DEFAULT_CONTEXT_BUDGET", "128000"))


def estimate_tokens(text: str) -> int:
    """Rough token estimate for any text (works for all providers)."""
    if not text:
        return 0
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return max(1, len(text) // _CHARS_PER_TOKEN_ESTIMATE)


def estimate_messages_tokens(messages: list[dict[str, str]]) -> int:
    """Estimates total tokens for a list of chat messages."""
    total = 0
    for msg in messages:
        total += estimate_tokens(msg.get("content", ""))
        total += 4  # per-message overhead
    return total


def get_model_budget(model_name: str) -> int:
    """Returns the token budget for a given model."""
    for key, budget in _MODEL_BUDGETS.items():
        if key in (model_name or "").lower():
            return budget
    return _DEFAULT_BUDGET


def truncate_text(text: str, max_chars: int, *, suffix: str | None = None) -> tuple[str, bool]:
    """Recorta texto plano; devuelve (texto, hubo_recorte)."""
    if not text or max_chars <= 0 or len(text) <= max_chars:
        return text or "", False
    end = max(0, max_chars - len(suffix or "")) if suffix else max_chars
    trimmed = text[:end].rstrip()
    if suffix:
        trimmed = trimmed + suffix
    return trimmed, True


def trim_messages_to_budget(
    messages: list[dict[str, str]],
    model_name: str,
    *,
    system_instruction: str = "",
    reserve_tokens: int = 4096,
) -> list[dict[str, str]]:
    """Trims messages from the beginning to fit within the model's context budget.

    Always preserves the system message and the last N messages.
    """
    budget = get_model_budget(model_name)
    available = budget - reserve_tokens - estimate_tokens(system_instruction)

    if available <= 0:
        logger.warning("Context budget exhausted for model %s", model_name)
        return messages[-2:] if len(messages) >= 2 else messages

    total = estimate_messages_tokens(messages)
    if total <= available:
        return messages

    trimmed = list(messages)
    while estimate_messages_tokens(trimmed) > available and len(trimmed) > 2:
        trimmed.pop(0)

    dropped = len(messages) - len(trimmed)
    if dropped > 0:
        logger.info(
            "Context trimming: dropped %d oldest messages for model %s (budget=%d tokens)",
            dropped, model_name, budget,
        )

    return trimmed
