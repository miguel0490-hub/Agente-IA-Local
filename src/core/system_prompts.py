"""Centralized system prompt loading.

Prompt content lives in ``prompts/*.md`` so configuration code only exposes
loaded values and does not duplicate long prompt bodies.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


@lru_cache(maxsize=None)
def load_system_prompt(name: str) -> str:
    """Load a required system prompt from the repository prompts directory."""
    prompt_path = _PROMPTS_DIR / f"{name}.md"
    if not prompt_path.is_file():
        raise FileNotFoundError(f"System prompt not found: {prompt_path}")

    content = prompt_path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"System prompt is empty: {prompt_path}")

    return content


def _load_prompt_with_examples(prompt_name: str, *example_files: str) -> str:
    base = load_system_prompt(prompt_name)
    parts = [base]
    for example_file in example_files:
        example_path = _PROMPTS_DIR / "examples" / example_file
        if example_path.is_file():
            example = example_path.read_text(encoding="utf-8").strip()
            if example:
                parts.append(example)
    if len(parts) == 1:
        return base
    return "\n\n---\n\n".join(parts)


@lru_cache(maxsize=1)
def _load_app_builder_prompt() -> str:
    return _load_prompt_with_examples("app_builder", "web_app_bundle.md")


@lru_cache(maxsize=1)
def _load_ui_designer_prompt() -> str:
    return _load_prompt_with_examples("ui_designer", "ui_visual_replica.md")


PROMPT_TECH_LEAD = load_system_prompt("tech_lead")
PROMPT_APP_BUILDER = _load_app_builder_prompt()
PROMPT_UI_DESIGNER = _load_ui_designer_prompt()

# Compatibility alias used by legacy tests/scripts.
INSTRUCCIONES_SISTEMA = PROMPT_TECH_LEAD
