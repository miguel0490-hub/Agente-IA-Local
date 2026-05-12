"""Intelligent Tool Router — assigns available tools based on agent role and task context.

Routes tool access dynamically so each agent only sees tools matching its
capability profile. Prevents cross-role tool leakage and enables automatic
tool selection based on classified task type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.agents.capabilities import (
    AgentCapabilityProfile,
    TaskType,
    get_capability_profile,
    get_profiles_for_task,
)
from src.agents.task_classifier import classify_task
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ToolRoutingDecision:
    """Result of a tool routing evaluation."""

    allowed_tools: frozenset[str]
    role_key: str
    task_type: str
    max_iterations: int
    preferred_model: str | None
    context_instructions: str


_TASK_TYPE_MAP: dict[str, TaskType] = {
    "code_review": TaskType.CODE_REVIEW,
    "code_generation": TaskType.CODE_GENERATION,
    "web_research": TaskType.WEB_RESEARCH,
    "file_generation": TaskType.FILE_GENERATION,
    "security_scan": TaskType.SECURITY_SCAN,
    "devops": TaskType.DEVOPS,
    "design": TaskType.DESIGN,
    "data_analysis": TaskType.DATA_ANALYSIS,
    "multimedia": TaskType.MULTIMEDIA,
    "general": TaskType.GENERAL,
}


class ToolRouter:
    """Routes tool access based on agent role and user intent."""

    def __init__(self) -> None:
        self._override_tools: dict[str, frozenset[str]] = {}

    def route(self, role_name: str, user_prompt: str = "") -> ToolRoutingDecision:
        """Determines which tools are available for a given role and prompt context."""
        profile = get_capability_profile(role_name)
        task_type_str = classify_task(user_prompt) if user_prompt else "general"
        task_type = _TASK_TYPE_MAP.get(task_type_str, TaskType.GENERAL)

        allowed = self._resolve_tools(profile, task_type)
        context = self._build_context_instructions(profile, task_type)

        return ToolRoutingDecision(
            allowed_tools=allowed,
            role_key=profile.role_key,
            task_type=task_type_str,
            max_iterations=profile.max_tool_iterations,
            preferred_model=profile.preferred_model,
            context_instructions=context,
        )

    def _resolve_tools(
        self, profile: AgentCapabilityProfile, task_type: TaskType
    ) -> frozenset[str]:
        """Resolves final tool set: profile base + task-specific additions."""
        if profile.role_key in self._override_tools:
            return self._override_tools[profile.role_key]

        base_tools = set(profile.tools)

        if task_type == TaskType.WEB_RESEARCH:
            base_tools.add("search_web")
        elif task_type == TaskType.FILE_GENERATION:
            base_tools.add("create_file")
        elif task_type == TaskType.DATA_ANALYSIS:
            base_tools.add("execute_code")
            base_tools.add("query_rag")

        return frozenset(base_tools)

    def _build_context_instructions(
        self, profile: AgentCapabilityProfile, task_type: TaskType
    ) -> str:
        """Generates task-aware context instructions for the LLM."""
        from src.agents.task_classifier import get_task_context

        task_context = get_task_context(task_type.value)
        skill_list = ", ".join(profile.skills)

        parts = []
        if task_context:
            parts.append(task_context)
        parts.append(f"Tus especialidades son: {skill_list}.")
        parts.append(
            f"Herramientas disponibles: {', '.join(sorted(profile.tools))}."
        )

        return " ".join(parts)

    def set_tool_override(self, role_key: str, tools: frozenset[str]) -> None:
        """Admin override for testing or special scenarios."""
        self._override_tools[role_key] = tools
        logger.info("Tool override set for role=%s tools=%s", role_key, tools)

    def clear_override(self, role_key: str) -> None:
        self._override_tools.pop(role_key, None)

    def is_tool_allowed(self, role_name: str, action: str, user_prompt: str = "") -> bool:
        """Quick check: is a specific tool allowed for this role + context?"""
        decision = self.route(role_name, user_prompt)
        return action in decision.allowed_tools

    def suggest_agent_for_task(self, user_prompt: str) -> AgentCapabilityProfile:
        """Suggests the best agent profile for a given user prompt."""
        task_type_str = classify_task(user_prompt)
        task_type = _TASK_TYPE_MAP.get(task_type_str, TaskType.GENERAL)
        candidates = get_profiles_for_task(task_type)
        if candidates:
            return candidates[0]
        from src.agents.capabilities import CAPABILITY_PROFILES
        return CAPABILITY_PROFILES["tech_lead"]


_router_instance: ToolRouter | None = None


def get_tool_router() -> ToolRouter:
    """Returns the global ToolRouter singleton."""
    global _router_instance
    if _router_instance is None:
        _router_instance = ToolRouter()
    return _router_instance
