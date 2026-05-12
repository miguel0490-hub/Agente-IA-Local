"""Integration test fixtures."""

from __future__ import annotations

import os

os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")

import pytest


@pytest.fixture
def sample_api_keys():
    return {
        "GEMINI_API_KEY": "fake-gemini-key",
        "GROQ_API_KEY": "fake-groq-key",
        "OPENROUTER_API_KEY": "fake-openrouter-key",
    }


@pytest.fixture
def empty_api_keys():
    return {}
