"""Loads and composes agent prompts from markdown files."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


@lru_cache(maxsize=16)
def _load_prompt_file(name: str) -> str:
    """Loads a prompt markdown file by name (without extension)."""
    filepath = _PROMPTS_DIR / f"{name}.md"
    if not filepath.is_file():
        return ""
    return filepath.read_text(encoding="utf-8").strip()


def load_base_prompt() -> str:
    """Loads the universal base context."""
    return _load_prompt_file("base")


def load_role_prompt(role_key: str) -> str:
    """Loads the role-specific prompt (tech_lead, app_builder, etc.)."""
    return _load_prompt_file(role_key)


def load_example(example_name: str) -> str:
    """Loads a few-shot example file."""
    filepath = _PROMPTS_DIR / "examples" / f"{example_name}.md"
    if not filepath.is_file():
        return ""
    return filepath.read_text(encoding="utf-8").strip()


def compose_system_prompt(role_key: str, task_type: str = "") -> str:
    """Composes the full system prompt for a given role and optional task context."""
    parts = [load_role_prompt(role_key)]

    if task_type:
        from src.agents.task_classifier import get_task_context
        context = get_task_context(task_type)
        if context:
            parts.append(f"\n## Contexto de Tarea Actual\n{context}")

        example = load_example(task_type)
        if example:
            parts.append(f"\n## Ejemplo de Referencia\n{example}")

    return "\n\n".join(p for p in parts if p)
