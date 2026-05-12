"""Integration tests for the Prompt Manager."""

from __future__ import annotations

import os
import pytest

os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")

from src.agents.prompt_manager import (
    compose_system_prompt,
    enrich_system_instruction,
    get_prompt_version,
    list_available_examples,
    list_available_profiles,
    load_base_prompt,
    load_examples,
    load_profile,
)


class TestPromptLoading:

    def test_load_base_prompt(self):
        base = load_base_prompt()
        assert len(base) > 0
        assert "SuperAgente" in base

    def test_load_existing_profile(self):
        profile = load_profile("tech_lead")
        assert len(profile) > 0
        assert "Tech Lead" in profile

    def test_load_nonexistent_profile(self):
        profile = load_profile("nonexistent_role_xyz")
        assert profile == ""

    def test_load_existing_examples(self):
        examples = load_examples("code_review")
        assert len(examples) > 0
        assert "Ejemplo" in examples or "ejemplo" in examples.lower()

    def test_load_nonexistent_examples(self):
        examples = load_examples("nonexistent_type")
        assert examples == ""

    def test_list_profiles_returns_all(self):
        profiles = list_available_profiles()
        assert "tech_lead" in profiles
        assert "app_builder" in profiles
        assert "security_engineer" in profiles

    def test_list_examples_returns_types(self):
        examples = list_available_examples()
        assert "code_review" in examples
        assert "file_generation" in examples
        assert "web_research" in examples


class TestPromptComposition:

    def test_compose_with_base_only(self):
        result = compose_system_prompt("Base prompt here")
        assert "Base prompt here" in result

    def test_compose_with_profile(self):
        result = compose_system_prompt("Base", profile_name="tech_lead")
        assert "Base" in result
        assert "PERFIL DE ESPECIALIZACIÓN" in result

    def test_compose_with_examples(self):
        result = compose_system_prompt("Base", task_type="code_review")
        assert "Base" in result
        assert "EJEMPLOS DE REFERENCIA" in result

    def test_compose_with_extra_context(self):
        result = compose_system_prompt("Base", extra_context="Extra info")
        assert "CONTEXTO ADICIONAL" in result
        assert "Extra info" in result

    def test_compose_full_chain(self):
        result = compose_system_prompt(
            "Base",
            profile_name="tech_lead",
            task_type="code_review",
            extra_context="User is expert",
        )
        assert "Base" in result
        assert "PERFIL" in result
        assert "EJEMPLOS" in result
        assert "CONTEXTO ADICIONAL" in result


class TestPromptVersioning:

    def test_version_deterministic(self):
        v1 = get_prompt_version("same content")
        v2 = get_prompt_version("same content")
        assert v1 == v2

    def test_version_differs_for_different_content(self):
        v1 = get_prompt_version("content A")
        v2 = get_prompt_version("content B")
        assert v1 != v2

    def test_version_length(self):
        v = get_prompt_version("test")
        assert len(v) == 12


class TestEnrichSystemInstruction:

    def test_enrich_preserves_original(self):
        original = "Original system instruction"
        enriched = enrich_system_instruction(original, role_name="tech_lead", user_prompt="hola")
        assert original in enriched

    def test_enrich_adds_profile_for_code_review(self):
        enriched = enrich_system_instruction(
            "Base",
            role_name="tech_lead",
            user_prompt="revisa este código",
        )
        assert len(enriched) > len("Base")

    def test_enrich_without_role(self):
        enriched = enrich_system_instruction("Base", role_name="", user_prompt="hola")
        assert "Base" in enriched

    def test_enrich_without_prompt(self):
        enriched = enrich_system_instruction("Base", role_name="tech_lead", user_prompt="")
        assert "Base" in enriched
