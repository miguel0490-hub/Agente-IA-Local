"""Prompt injection detection with scoring, canonicalization, and invisible-char stripping."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class InjectionMatch:
    """Represents a prompt-injection pattern match."""

    pattern: str
    snippet: str
    weight: int = 10


@dataclass(frozen=True)
class InjectionResult:
    """Aggregated detection result with risk scoring."""

    matches: list[InjectionMatch]
    risk_score: int

    @property
    def is_suspicious(self) -> bool:
        return self.risk_score > 0

    @property
    def is_high_risk(self) -> bool:
        return self.risk_score >= 50


_INVISIBLE_CHARS = re.compile(
    r"[\u200b\u200c\u200d\u200e\u200f"
    r"\u202a-\u202e\u2060\u2066-\u2069"
    r"\ufeff\u00ad\u180e\u2028\u2029"
    r"\U000e0001-\U000e007f]"
)


_PATTERNS: list[tuple[str, int]] = [
    # --- Jailbreak / instruction override (weight 15-20) ---
    (r"ignore\s+(all\s+)?previous\s+instructions", 20),
    (r"system\s+instruction\s+override", 20),
    (r"new\s+system\s+prompt", 20),
    (r"you\s+are\s+now\s+(DAN|evil|unrestricted|unfiltered)", 20),
    (r"developer\s+mode\s+(enabled|activated|on)", 20),
    (r"jailbreak\s+(mode|enabled|activated)", 20),
    (r"act\s+as\s+if\s+you\s+have\s+no\s+(restrictions|guardrails|filters)", 15),
    (r"pretend\s+(that\s+)?you\s+are\s+(not\s+)?an?\s+AI", 15),
    (r"forget\s+(all|everything)\s+(you|about)", 15),
    (r"do\s+not\s+follow\s+(any|your)\s+(rules|guidelines|instructions)", 15),

    # --- Exfiltration / secrets (weight 20) ---
    (r"reveal\s+(your|the)\s+(system|hidden|secret)\s+prompt", 20),
    (r"print\s+all\s+environment\s+variables", 20),
    (r"(dump|exfiltrate|steal)\s+(\w+\s+)*(secrets|tokens|credentials|api\s*keys)", 20),
    (r"\b(base64|hex)\s+encode\s+all\s+secrets", 20),
    (r"show\s+(me\s+)?your\s+(instructions|system\s+message|system\s+prompt|prompt)", 15),
    (r"what\s+is\s+your\s+system\s+prompt", 10),
    (r"repeat\s+(the\s+)?(text|words|instructions)\s+above", 15),

    # --- Safety bypass (weight 15) ---
    (r"\bdisable\s+safety\b", 15),
    (r"bypass\s+(content\s+)?filter", 15),
    (r"turn\s+off\s+(moderation|safety|guardrails)", 15),

    # --- Indirect injection (weight 10-15) ---
    (r"developer\s+message", 10),
    (r"\[system\]", 15),
    (r"<\|im_start\|>system", 15),
    (r"###\s*(system|instruction|SYSTEM)", 10),
    (r"BEGININSTRUCTION", 10),
    (r"<\s*/?system\s*>", 15),

    # --- Encoded payloads (weight 10) ---
    (r"eval\s*\(\s*atob\s*\(", 10),
    (r"(?:aWdub3Jl|c3lzdGVt|ZXhmaWx0)", 10),  # base64 for common attack words

    # --- Markdown / HTML injection (weight 5-10) ---
    (r"!\[.*?\]\(https?://[^)]*\?.*?token", 10),
    (r"<script[^>]*>", 10),
    (r"javascript\s*:", 10),
    (r"on(error|load|click)\s*=", 10),
    (r"<!--.*?(system|ignore|override).*?-->", 5),
]


def _canonicalize(text: str) -> str:
    """Normalizes text for consistent pattern matching."""
    text = _INVISIBLE_CHARS.sub("", text)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)
    return text


class PromptInjectionDetector:
    """Detects jailbreak, exfiltration, and injection attempts with risk scoring."""

    @classmethod
    def detect(cls, text: str) -> list[InjectionMatch]:
        """Returns all suspicious matches in text (legacy API)."""
        result = cls.analyze(text)
        return result.matches

    @classmethod
    def analyze(cls, text: str) -> InjectionResult:
        """Full analysis with canonicalization, pattern matching, and scoring."""
        if not text:
            return InjectionResult(matches=[], risk_score=0)

        canonical = _canonicalize(text)
        findings: list[InjectionMatch] = []

        for pattern, weight in _PATTERNS:
            for match in re.finditer(pattern, canonical, flags=re.IGNORECASE):
                snippet = canonical[max(0, match.start() - 30):match.end() + 30]
                findings.append(InjectionMatch(
                    pattern=pattern,
                    snippet=snippet,
                    weight=weight,
                ))

        score = min(100, sum(m.weight for m in findings))
        return InjectionResult(matches=findings, risk_score=score)

    @classmethod
    def strip_invisible(cls, text: str) -> str:
        """Removes zero-width and invisible Unicode characters from text."""
        return _INVISIBLE_CHARS.sub("", text) if text else ""
