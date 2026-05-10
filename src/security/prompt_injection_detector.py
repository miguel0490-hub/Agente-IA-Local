"""Prompt injection detection helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class InjectionMatch:
    """Represents a prompt-injection pattern match."""

    pattern: str
    snippet: str


class PromptInjectionDetector:
    """Detects common jailbreak and exfiltration attempts."""

    _PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"system\s+instruction\s+override",
        r"developer\s+message",
        r"reveal\s+(your|the)\s+(system|hidden)\s+prompt",
        r"print\s+all\s+environment\s+variables",
        r"(dump|exfiltrate|steal)\s+(secrets|tokens|credentials|api\s*keys)",
        r"\b(base64|hex)\s+encode\s+all\s+secrets",
        r"\bdisable\s+safety\b",
    ]

    @classmethod
    def detect(cls, text: str) -> list[InjectionMatch]:
        """Returns all suspicious matches in text."""
        findings: list[InjectionMatch] = []
        haystack = text or ""
        for pattern in cls._PATTERNS:
            for match in re.finditer(pattern, haystack, flags=re.IGNORECASE):
                snippet = haystack[max(0, match.start() - 24) : match.end() + 24]
                findings.append(InjectionMatch(pattern=pattern, snippet=snippet))
        return findings
