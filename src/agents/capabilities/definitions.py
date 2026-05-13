"""Declarative capability profiles for each agent role.

Each profile declares: skills, tools, permissions, task types, supported models,
and prompt profile references. The registry in ``src/agents/registry.py`` stays
intact for backward compatibility — this module extends it with richer metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class Permission(Enum):
    READ_FILES = auto()
    WRITE_FILES = auto()
    EXECUTE_CODE = auto()
    WEB_SEARCH = auto()
    RAG_QUERY = auto()
    IMAGE_GENERATION = auto()
    AUDIO_PROCESSING = auto()
    FILE_CONVERSION = auto()
    ADMIN_ACCESS = auto()


class TaskType(Enum):
    CODE_REVIEW = "code_review"
    CODE_GENERATION = "code_generation"
    WEB_RESEARCH = "web_research"
    FILE_GENERATION = "file_generation"
    SECURITY_SCAN = "security_scan"
    DEVOPS = "devops"
    DESIGN = "design"
    DATA_ANALYSIS = "data_analysis"
    MULTIMEDIA = "multimedia"
    GENERAL = "general"


@dataclass(frozen=True)
class AgentCapabilityProfile:
    """Full capability declaration for an agent role."""

    role_key: str
    display_name: str
    skills: tuple[str, ...]
    tools: frozenset[str]
    permissions: frozenset[Permission]
    task_types: tuple[TaskType, ...]
    supported_models: tuple[str, ...]
    prompt_profile: str
    max_tool_iterations: int = 4
    preferred_model: str | None = None
    description: str = ""

    def can_handle_task(self, task_type: TaskType) -> bool:
        return task_type in self.task_types

    def has_permission(self, perm: Permission) -> bool:
        return perm in self.permissions

    def supports_tool(self, tool_action: str) -> bool:
        return tool_action in self.tools


CAPABILITY_PROFILES: dict[str, AgentCapabilityProfile] = {
    "tech_lead": AgentCapabilityProfile(
        role_key="tech_lead",
        display_name="🧠 Asistente General (Tech Lead)",
        skills=("code_review", "architecture", "debugging", "documentation", "data_analysis", "web_research"),
        tools=frozenset({"create_file", "edit_file", "search_web", "execute_code", "query_rag", "open_converter"}),
        permissions=frozenset({
            Permission.READ_FILES, Permission.WRITE_FILES, Permission.EXECUTE_CODE,
            Permission.WEB_SEARCH, Permission.RAG_QUERY, Permission.FILE_CONVERSION,
        }),
        task_types=(
            TaskType.CODE_REVIEW, TaskType.CODE_GENERATION, TaskType.WEB_RESEARCH,
            TaskType.FILE_GENERATION, TaskType.DATA_ANALYSIS, TaskType.GENERAL,
        ),
        supported_models=("gemini", "groq", "openrouter", "ollama", "custom"),
        prompt_profile="tech_lead",
        max_tool_iterations=4,
    ),
    "app_builder": AgentCapabilityProfile(
        role_key="app_builder",
        display_name="🏗️ Arquitecto de Software (App Builder)",
        skills=("full_stack_development", "api_design", "database_design", "testing"),
        tools=frozenset({"create_file", "edit_file", "execute_code", "search_web"}),
        permissions=frozenset({
            Permission.READ_FILES, Permission.WRITE_FILES, Permission.EXECUTE_CODE,
            Permission.WEB_SEARCH,
        }),
        task_types=(TaskType.CODE_GENERATION, TaskType.FILE_GENERATION, TaskType.GENERAL),
        supported_models=("gemini", "groq", "openrouter", "ollama", "custom"),
        prompt_profile="app_builder",
        max_tool_iterations=6,
        preferred_model="groq",
    ),
    "ui_designer": AgentCapabilityProfile(
        role_key="ui_designer",
        display_name="🎨 Diseñador Frontend UI/UX (Vision)",
        skills=("css_design", "responsive_layout", "accessibility", "ux_patterns"),
        tools=frozenset({"create_file", "search_web", "query_rag"}),
        permissions=frozenset({
            Permission.READ_FILES, Permission.WRITE_FILES, Permission.WEB_SEARCH,
            Permission.RAG_QUERY,
        }),
        task_types=(TaskType.DESIGN, TaskType.CODE_GENERATION, TaskType.FILE_GENERATION),
        supported_models=("gemini", "groq", "openrouter", "ollama", "custom"),
        prompt_profile="ui_designer",
        max_tool_iterations=3,
        preferred_model="gemini",
    ),
    "security_engineer": AgentCapabilityProfile(
        role_key="security_engineer",
        display_name="🔒 Ingeniero de Seguridad",
        skills=("vulnerability_scan", "code_audit", "pentest_logic", "secrets_review"),
        tools=frozenset({"search_web", "execute_code", "query_rag"}),
        permissions=frozenset({
            Permission.READ_FILES, Permission.EXECUTE_CODE, Permission.WEB_SEARCH,
            Permission.RAG_QUERY,
        }),
        task_types=(TaskType.SECURITY_SCAN, TaskType.CODE_REVIEW, TaskType.WEB_RESEARCH),
        supported_models=("gemini", "groq", "openrouter", "ollama", "custom"),
        prompt_profile="security_engineer",
        max_tool_iterations=4,
        preferred_model="gemini",
    ),
    "devops_engineer": AgentCapabilityProfile(
        role_key="devops_engineer",
        display_name="🚀 Ingeniero DevOps",
        skills=("docker", "kubernetes", "ci_cd", "monitoring", "infrastructure"),
        tools=frozenset({"create_file", "edit_file", "execute_code", "search_web"}),
        permissions=frozenset({
            Permission.READ_FILES, Permission.WRITE_FILES, Permission.EXECUTE_CODE,
            Permission.WEB_SEARCH,
        }),
        task_types=(TaskType.DEVOPS, TaskType.CODE_GENERATION, TaskType.FILE_GENERATION),
        supported_models=("gemini", "groq", "openrouter", "ollama", "custom"),
        prompt_profile="devops_engineer",
        max_tool_iterations=4,
        preferred_model="groq",
    ),
    "research_agent": AgentCapabilityProfile(
        role_key="research_agent",
        display_name="🔍 Agente de Investigación",
        skills=("web_research", "data_synthesis", "report_generation", "fact_checking"),
        tools=frozenset({"search_web", "query_rag", "create_file"}),
        permissions=frozenset({
            Permission.READ_FILES, Permission.WRITE_FILES, Permission.WEB_SEARCH,
            Permission.RAG_QUERY,
        }),
        task_types=(TaskType.WEB_RESEARCH, TaskType.FILE_GENERATION, TaskType.DATA_ANALYSIS),
        supported_models=("gemini", "groq", "openrouter", "ollama", "custom"),
        prompt_profile="research_agent",
        max_tool_iterations=5,
        preferred_model="gemini",
    ),
    "multimedia_agent": AgentCapabilityProfile(
        role_key="multimedia_agent",
        display_name="🎬 Agente Multimedia",
        skills=("image_generation", "audio_processing", "format_conversion", "media_editing"),
        tools=frozenset({"create_file", "search_web", "open_converter"}),
        permissions=frozenset({
            Permission.READ_FILES, Permission.WRITE_FILES, Permission.WEB_SEARCH,
            Permission.IMAGE_GENERATION, Permission.AUDIO_PROCESSING,
            Permission.FILE_CONVERSION,
        }),
        task_types=(TaskType.MULTIMEDIA, TaskType.FILE_GENERATION),
        supported_models=("gemini", "groq", "openrouter", "ollama", "custom"),
        prompt_profile="multimedia_agent",
        max_tool_iterations=3,
        preferred_model="gemini",
    ),
}

_DISPLAY_NAME_MAP: dict[str, str] = {
    profile.display_name: key for key, profile in CAPABILITY_PROFILES.items()
}


def get_capability_profile(role_name: str) -> AgentCapabilityProfile:
    """Resolves a capability profile from either a role key or display name."""
    if role_name in CAPABILITY_PROFILES:
        return CAPABILITY_PROFILES[role_name]
    key = _DISPLAY_NAME_MAP.get(role_name, "tech_lead")
    return CAPABILITY_PROFILES.get(key, CAPABILITY_PROFILES["tech_lead"])


def get_all_profiles() -> dict[str, AgentCapabilityProfile]:
    return dict(CAPABILITY_PROFILES)


def get_profiles_for_task(task_type: TaskType) -> list[AgentCapabilityProfile]:
    """Returns all profiles that can handle a given task type, sorted by specificity."""
    matches = [p for p in CAPABILITY_PROFILES.values() if p.can_handle_task(task_type)]
    return sorted(matches, key=lambda p: len(p.task_types))
