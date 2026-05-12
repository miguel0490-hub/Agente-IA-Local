"""Modular Prompt Manager — loads, composes and versions system prompts.

Reads prompt profiles and few-shot examples from the ``prompts/`` directory,
composes them with the base system prompt, and caches the result. The existing
``PROMPT_TECH_LEAD`` etc. in ``src/core/config.py`` remain the canonical source
for backward compatibility; this module enriches them with profile context and
few-shot examples when available.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.core.logger import get_logger

logger = get_logger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"
_PROFILES_DIR = _PROMPTS_DIR / "profiles"
_EXAMPLES_DIR = _PROMPTS_DIR / "examples"


@lru_cache(maxsize=32)
def _load_file(path: Path) -> str:
    """Loads a text file with caching."""
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to load prompt file %s: %s", path, e)
        return ""


def load_profile(profile_name: str) -> str:
    """Loads a prompt profile from prompts/profiles/<name>.md."""
    return _load_file(_PROFILES_DIR / f"{profile_name}.md")


def load_examples(task_type: str) -> str:
    """Loads few-shot examples for a task type from prompts/examples/<type>.md."""
    return _load_file(_EXAMPLES_DIR / f"{task_type}.md")


def load_base_prompt() -> str:
    """Loads the base system context from prompts/base.md."""
    return _load_file(_PROMPTS_DIR / "base.md")


def compose_system_prompt(
    base_prompt: str,
    profile_name: str = "",
    task_type: str = "",
    extra_context: str = "",
) -> str:
    """Composes a full system prompt from base + profile + examples + context.

    The base_prompt (from config.py) is always preserved as the core.
    Profile and example enrichments are appended as supplementary context.
    """
    parts: list[str] = [base_prompt]

    profile_text = load_profile(profile_name) if profile_name else ""
    if profile_text:
        parts.append(f"\n\n--- PERFIL DE ESPECIALIZACIÓN ---\n{profile_text}")

    examples_text = load_examples(task_type) if task_type else ""
    if examples_text:
        parts.append(f"\n\n--- EJEMPLOS DE REFERENCIA ---\n{examples_text}")

    if extra_context:
        parts.append(f"\n\n--- CONTEXTO ADICIONAL ---\n{extra_context}")

    return "\n".join(parts)


def get_prompt_version(prompt_text: str) -> str:
    """Returns a short hash for prompt versioning/tracking."""
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:12]


def list_available_profiles() -> list[str]:
    """Lists all available profile names."""
    if not _PROFILES_DIR.exists():
        return []
    return sorted(p.stem for p in _PROFILES_DIR.glob("*.md"))


def list_available_examples() -> list[str]:
    """Lists all available example types."""
    if not _EXAMPLES_DIR.exists():
        return []
    return sorted(p.stem for p in _EXAMPLES_DIR.glob("*.md"))


def enrich_system_instruction(
    system_instruction: str,
    role_name: str = "",
    user_prompt: str = "",
) -> str:
    """Enriches an existing system instruction with profile and task-aware context.

    This is the main integration point: called from chat runtime to dynamically
    add profile specialization and few-shot examples without replacing the
    existing system instruction.
    """
    from src.agents.capabilities import get_capability_profile
    from src.agents.task_classifier import classify_task

    profile = get_capability_profile(role_name) if role_name else None
    task_type = classify_task(user_prompt) if user_prompt else "general"

    profile_name = profile.prompt_profile if profile else ""

    return compose_system_prompt(
        base_prompt=system_instruction,
        profile_name=profile_name,
        task_type=task_type,
    )
