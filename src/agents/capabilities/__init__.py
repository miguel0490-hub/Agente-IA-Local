"""Agent Capabilities — declarative skill/tool/permission system per agent role."""

from src.agents.capabilities.definitions import (
    AgentCapabilityProfile,
    Permission,
    TaskType,
    get_capability_profile,
    get_all_profiles,
    get_profiles_for_task,
    CAPABILITY_PROFILES,
)

__all__ = [
    "AgentCapabilityProfile",
    "Permission",
    "TaskType",
    "get_capability_profile",
    "get_all_profiles",
    "get_profiles_for_task",
    "CAPABILITY_PROFILES",
]
