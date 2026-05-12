"""Integration tests for the Tool Router."""

from __future__ import annotations

import os
import pytest

os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")

from src.agents.tool_router import ToolRouter, get_tool_router


class TestToolRouting:
    """Tests that tool routing produces correct decisions."""

    def setup_method(self):
        self.router = ToolRouter()

    def test_route_tech_lead_general(self):
        decision = self.router.route("tech_lead", "hola, qué tal")
        assert "search_web" in decision.allowed_tools
        assert "create_file" in decision.allowed_tools
        assert decision.role_key == "tech_lead"

    def test_route_detects_web_research(self):
        decision = self.router.route("tech_lead", "busca información sobre Python 3.13")
        assert decision.task_type == "web_research"
        assert "search_web" in decision.allowed_tools

    def test_route_detects_code_review(self):
        decision = self.router.route("tech_lead", "revisa este código Python")
        assert decision.task_type == "code_review"

    def test_route_detects_security_scan(self):
        decision = self.router.route("security_engineer", "analiza las vulnerabilidades")
        assert decision.task_type == "security_scan"

    def test_route_ui_designer_no_execute_code(self):
        decision = self.router.route("ui_designer", "diseña una landing page")
        assert "execute_code" not in decision.allowed_tools

    def test_route_respects_max_iterations(self):
        decision = self.router.route("app_builder", "crea una app")
        assert decision.max_iterations == 6

    def test_context_instructions_include_skills(self):
        decision = self.router.route("security_engineer", "escanea el código")
        assert "especialidades" in decision.context_instructions.lower()

    def test_is_tool_allowed_quick_check(self):
        assert self.router.is_tool_allowed("tech_lead", "search_web")
        assert not self.router.is_tool_allowed("ui_designer", "execute_code")

    def test_suggest_agent_for_security_task(self):
        profile = self.router.suggest_agent_for_task("revisa las vulnerabilidades de seguridad")
        assert profile.role_key == "security_engineer"

    def test_suggest_agent_for_design_task(self):
        profile = self.router.suggest_agent_for_task("diseña una interfaz responsive con CSS")
        assert profile.role_key in ("ui_designer", "app_builder", "tech_lead")

    def test_tool_override(self):
        self.router.set_tool_override("tech_lead", frozenset({"search_web"}))
        decision = self.router.route("tech_lead", "hola")
        assert decision.allowed_tools == frozenset({"search_web"})
        self.router.clear_override("tech_lead")
        decision2 = self.router.route("tech_lead", "hola")
        assert "create_file" in decision2.allowed_tools


class TestToolRouterSingleton:
    def test_singleton_returns_same_instance(self):
        r1 = get_tool_router()
        r2 = get_tool_router()
        assert r1 is r2
