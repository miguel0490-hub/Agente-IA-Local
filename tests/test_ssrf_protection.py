"""Tests for SSRF protection in url_validator."""
from __future__ import annotations
import os, pytest
os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")

from src.security.url_validator import validate_url, assert_url_safe


class TestBlockedURLs:
    @pytest.mark.parametrize("url", [
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://127.0.0.1:8080/admin",
        "http://localhost/secret",
        "http://0.0.0.0/",
        "http://[::1]/",
        "http://10.0.0.1/internal",
        "http://192.168.1.1/admin",
        "http://172.16.0.1/db",
    ])
    def test_blocks_private_and_metadata(self, url):
        result = validate_url(url, context="test")
        assert not result.safe, f"Should block: {url}"

    @pytest.mark.parametrize("url", [
        "",
        None,
        "ftp://example.com/file",
        "file:///etc/passwd",
        "gopher://evil.com",
        "://no-scheme",
    ])
    def test_blocks_invalid_schemes(self, url):
        result = validate_url(url, context="test")
        assert not result.safe

    def test_blocks_dangerous_ports(self):
        result = validate_url("http://example.com:3306/", context="test")
        assert not result.safe
        assert "3306" in result.reason


class TestAllowedURLs:
    @pytest.mark.parametrize("url", [
        "https://api.openai.com/v1/chat/completions",
        "https://api.deepseek.com/v1",
        "https://openrouter.ai/api/v1",
        "https://api.groq.com/openai/v1",
    ])
    def test_allows_public_apis(self, url):
        result = validate_url(url, context="test")
        assert result.safe, f"Should allow: {url} — reason: {result.reason}"


class TestAllowlist:
    def test_allowlist_blocks_unlisted_domain(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_LLM_DOMAINS", "api.openai.com,api.groq.com")
        result = validate_url("https://evil.attacker.com/v1", context="test")
        assert not result.safe
        assert "allowlist" in result.reason

    def test_allowlist_permits_listed_domain(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_LLM_DOMAINS", "api.openai.com,api.groq.com")
        result = validate_url("https://api.openai.com/v1", context="test")
        assert result.safe


class TestAssertHelper:
    def test_assert_raises_on_blocked(self):
        with pytest.raises(ValueError, match="bloqueada"):
            assert_url_safe("http://127.0.0.1/", context="test")

    def test_assert_passes_on_safe(self):
        assert_url_safe("https://api.openai.com/v1", context="test")
