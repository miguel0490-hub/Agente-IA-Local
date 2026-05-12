"""Integration tests for the Agent Capability Registry."""

from __future__ import annotations

import os
import pytest

os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")

from src.agents.capabilities import (
    CAPABILITY_PROFILES,
    AgentCapabilityProfile,
    Permission,
    TaskType,
    get_all_profiles,
    get_capability_profile,
    get_profiles_for_task,
)
from src.agents.registry import (
    AGENT_REGISTRY,
    ROLE_NAME_MAP,
    get_agent_capability,
    get_allowed_tools,
    is_tool_allowed_for_role,
)


class TestCapabilityProfiles:
    """Validates the capability profile definitions."""

    def test_all_profiles_exist(self):
        expected = {"tech_lead", "app_builder", "ui_designer", "security_engineer",
                    "devops_engineer", "research_agent", "multimedia_agent"}
        assert set(CAPABILITY_PROFILES.keys()) == expected

    def test_every_profile_has_required_fields(self):
        for key, profile in CAPABILITY_PROFILES.items():
            assert profile.role_key == key
            assert len(profile.display_name) > 0
            assert len(profile.skills) > 0
            assert len(profile.tools) > 0
            assert len(profile.permissions) > 0
            assert len(profile.task_types) > 0
            assert len(profile.supported_models) > 0
            assert len(profile.prompt_profile) > 0
            assert profile.max_tool_iterations >= 1

    def test_tools_are_valid_actions(self):
        valid_actions = {"create_file", "edit_file", "search_web", "execute_code",
                         "query_rag", "open_converter"}
        for key, profile in CAPABILITY_PROFILES.items():
            for tool in profile.tools:
                assert tool in valid_actions, f"Unknown tool '{tool}' in profile '{key}'"

    def test_can_handle_task(self):
        tech = get_capability_profile("tech_lead")
        assert tech.can_handle_task(TaskType.CODE_REVIEW)
        assert tech.can_handle_task(TaskType.GENERAL)

    def test_has_permission(self):
        tech = get_capability_profile("tech_lead")
        assert tech.has_permission(Permission.EXECUTE_CODE)
        assert tech.has_permission(Permission.WEB_SEARCH)

    def test_supports_tool(self):
        tech = get_capability_profile("tech_lead")
        assert tech.supports_tool("search_web")
        assert tech.supports_tool("execute_code")

    def test_get_profiles_for_task_returns_matching(self):
        profiles = get_profiles_for_task(TaskType.SECURITY_SCAN)
        assert len(profiles) >= 1
        role_keys = [p.role_key for p in profiles]
        assert "security_engineer" in role_keys

    def test_get_profiles_for_task_general_includes_tech_lead(self):
        profiles = get_profiles_for_task(TaskType.GENERAL)
        role_keys = [p.role_key for p in profiles]
        assert "tech_lead" in role_keys


class TestRegistryBackwardCompat:
    """Ensures the legacy registry API still works after refactor."""

    def test_agent_registry_populated(self):
        assert len(AGENT_REGISTRY) == 7

    def test_role_name_map_populated(self):
        assert len(ROLE_NAME_MAP) == 7

    def test_get_agent_capability_by_key(self):
        cap = get_agent_capability("tech_lead")
        assert "search_web" in cap.tools
        assert "code_review" in cap.specializations

    def test_get_agent_capability_by_display_name(self):
        cap = get_agent_capability("🧠 Asistente General (Tech Lead)")
        assert "search_web" in cap.tools

    def test_fallback_to_tech_lead(self):
        cap = get_agent_capability("nonexistent_role")
        assert "search_web" in cap.tools

    def test_get_allowed_tools(self):
        tools = get_allowed_tools("tech_lead")
        assert isinstance(tools, frozenset)
        assert "create_file" in tools

    def test_is_tool_allowed_for_role(self):
        assert is_tool_allowed_for_role("tech_lead", "search_web")
        assert not is_tool_allowed_for_role("ui_designer", "execute_code")

    def test_registry_matches_capabilities(self):
        for key in CAPABILITY_PROFILES:
            assert key in AGENT_REGISTRY
            profile = CAPABILITY_PROFILES[key]
            legacy = AGENT_REGISTRY[key]
            assert legacy.tools == profile.tools
            assert legacy.max_tool_iterations == profile.max_tool_iterations
