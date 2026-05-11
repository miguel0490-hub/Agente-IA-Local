"""Centralized application settings via Pydantic BaseSettings.

Reads from environment variables and .env file with validation and defaults.
Import ``settings`` from this module instead of scattering ``os.getenv()``
calls across the codebase.  Non-critical callers can still use os.getenv
during the migration period.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

try:
    from pydantic_settings import BaseSettings
    from pydantic import Field
    _HAS_PYDANTIC = True
except ImportError:
    _HAS_PYDANTIC = False


if _HAS_PYDANTIC:
    class _AppSettings(BaseSettings):
        """Typed, validated application configuration."""

        app_secret_key: str = Field(default="", description="Master encryption key for Fernet")
        database_url: str = Field(default="sqlite:///data/superagente.db")

        # SMTP
        smtp_server: str = ""
        smtp_port: int = 587
        smtp_user: str = ""
        smtp_password: str = ""
        smtp_from: str = ""
        admin_notification_email: str = ""

        # Session
        session_idle_timeout_minutes: int = 120
        remember_me_days: int = 7

        # Rate limiting
        rate_limit_chat_limit: int = 10
        rate_limit_chat_window: int = 60

        # LLM
        gemini_temperature: float = 0.2
        gemini_max_tokens: int = 8192
        groq_model: str = "llama-3.3-70b-versatile"
        groq_max_tokens: int = 8192
        openrouter_model: str = "openrouter/auto"

        # HTTP resilience
        http_connect_timeout: float = 10.0
        http_read_timeout: float = 120.0
        http_max_retries: int = 3

        # Security
        allowed_llm_domains: str = ""

        # Sentry
        sentry_dsn: str = ""

        # App
        app_url: str = ""

        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            extra = "ignore"


    @lru_cache(maxsize=1)
    def get_settings() -> _AppSettings:
        return _AppSettings()

else:
    class _FallbackSettings:
        """Minimal fallback when pydantic-settings is not installed."""

        def __getattr__(self, name: str) -> str:
            return os.getenv(name.upper(), "")

    def get_settings():
        return _FallbackSettings()


settings = get_settings()
