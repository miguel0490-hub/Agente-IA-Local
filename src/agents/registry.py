"""Agent Capability Registry — maps roles to tools, capabilities, and context.

Backward-compatible facade that delegates to the richer
``src.agents.capabilities`` module while preserving the original API surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.agents.capabilities import (
    CAPABILITY_PROFILES,
    AgentCapabilityProfile,
    get_capability_profile,
)


@dataclass(frozen=True)
class AgentCapability:
    """Describes what an agent can do (legacy dataclass kept for compat)."""
    tools: frozenset[str]
    specializations: tuple[str, ...]
    max_tool_iterations: int = 4
    preferred_model: str | None = None


def _profile_to_legacy(profile: AgentCapabilityProfile) -> AgentCapability:
    return AgentCapability(
        tools=profile.tools,
        specializations=profile.skills,
        max_tool_iterations=profile.max_tool_iterations,
        preferred_model=profile.preferred_model,
    )


AGENT_REGISTRY: dict[str, AgentCapability] = {
    key: _profile_to_legacy(profile)
    for key, profile in CAPABILITY_PROFILES.items()
}

ROLE_NAME_MAP: dict[str, str] = {
    profile.display_name: key
    for key, profile in CAPABILITY_PROFILES.items()
}


def get_agent_capability(role_name: str) -> AgentCapability:
    """Returns the capability profile for a given UI role name."""
    profile = get_capability_profile(role_name)
    return _profile_to_legacy(profile)


def get_allowed_tools(role_name: str) -> frozenset[str]:
    """Returns the set of allowed tool actions for a role."""
    return get_capability_profile(role_name).tools


def is_tool_allowed_for_role(role_name: str, action: str) -> bool:
    """Checks if a specific tool action is allowed for the active role."""
    return action in get_allowed_tools(role_name)
