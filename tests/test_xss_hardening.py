"""Tests for XSS hardening in the sanitizer module."""
from __future__ import annotations
import os, pytest
os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")

from src.core.sanitizer import escape_user_data, sanitize_html_output, sanitize_markdown_text


class TestEscapeUserData:
    @pytest.mark.parametrize("malicious", [
        '<script>alert("xss")</script>',
        '<img src=x onerror=alert(1)>',
        '"><svg/onload=alert(1)>',
        "javascript:alert('xss')",
        "<iframe src='evil.com'>",
    ])
    def test_escapes_xss_payloads(self, malicious):
        result = escape_user_data(malicious)
        assert "<script>" not in result
        assert "<img " not in result
        assert "<svg" not in result
        assert "<iframe" not in result

    def test_strips_invisible_chars(self):
        text = "normal\u200btext\u200dwith\u2060invisible"
        result = escape_user_data(text)
        assert "\u200b" not in result
        assert "\u200d" not in result
        assert "\u2060" not in result

    def test_empty_string(self):
        assert escape_user_data("") == ""
        assert escape_user_data(None) == ""

    def test_normal_text_preserved(self):
        assert escape_user_data("John Doe") == "John Doe"
        assert escape_user_data("user@email.com") == "user@email.com"


class TestSanitizeHtmlOutput:
    def test_strips_script_tags(self):
        result = sanitize_html_output('<p>Hello</p><script>evil()</script>')
        assert "<script>" not in result
        assert "Hello" in result

    def test_allows_whitelisted_tags(self):
        result = sanitize_html_output(
            '<p><b>Bold</b> and <i>italic</i></p>',
            allowed_tags=frozenset({"p", "b", "i"}),
        )
        assert "<b>" in result
        assert "<i>" in result

    def test_empty_string(self):
        assert sanitize_html_output("") == ""


class TestSanitizeMarkdownBackcompat:
    def test_still_works(self):
        result = sanitize_markdown_text('<script>alert(1)</script>Hello')
        assert "<script>" not in result
        assert "Hello" in result
