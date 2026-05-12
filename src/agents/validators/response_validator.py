"""Response Validator — validates LLM outputs for quality, safety and integrity.

Checks for: empty responses, malformed markdown, broken code blocks,
hallucination patterns, policy violations, and output schema conformance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from src.core.logger import get_logger

logger = get_logger(__name__)


class ValidationSeverity(Enum):
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


@dataclass
class ValidationIssue:
    """A single validation finding."""

    code: str
    message: str
    severity: ValidationSeverity
    details: str = ""


@dataclass
class ValidationResult:
    """Aggregated validation result."""

    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    sanitized_text: str = ""
    original_text: str = ""

    @property
    def has_errors(self) -> bool:
        return any(i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL) for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == ValidationSeverity.WARNING for i in self.issues)

    def summary(self) -> dict[str, Any]:
        return {
            "valid": self.is_valid,
            "issue_count": len(self.issues),
            "errors": sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR),
            "warnings": sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING),
            "issues": [{"code": i.code, "message": i.message, "severity": i.severity.name} for i in self.issues],
        }


_HALLUCINATION_PATTERNS = [
    re.compile(r"como modelo de (?:lenguaje|IA),?\s+no\s+(?:puedo|tengo)", re.IGNORECASE),
    re.compile(r"(?:mi|la)\s+fecha\s+de\s+corte\s+(?:de\s+)?(?:conocimiento|entrenamiento)", re.IGNORECASE),
    re.compile(r"no\s+tengo\s+acceso\s+a\s+internet\s+en\s+(?:tiempo\s+)?real", re.IGNORECASE),
    re.compile(r"soy\s+(?:ChatGPT|GPT-\d|Claude|Bard|Gemini)\b", re.IGNORECASE),
]

_POLICY_VIOLATIONS = [
    re.compile(r"(?:ignore|ignora)\s+(?:previous|anteriores)\s+instructions", re.IGNORECASE),
    re.compile(r"SYSTEM\s+INSTRUCTION\s+OVERRIDE", re.IGNORECASE),
    re.compile(r"(?:jailbreak|DAN|do\s+anything\s+now)", re.IGNORECASE),
]

_REPETITION_THRESHOLD = 5
_MIN_RESPONSE_LENGTH = 2
_MAX_EMPTY_RATIO = 0.7


class ResponseValidator:
    """Validates LLM responses against quality and safety rules."""

    def validate(self, text: str) -> ValidationResult:
        """Runs all validation checks on a response text."""
        issues: list[ValidationIssue] = []
        sanitized = text

        self._check_empty(text, issues)
        self._check_markdown_integrity(text, issues)
        self._check_code_blocks(text, issues)
        self._check_hallucination_patterns(text, issues)
        self._check_policy_violations(text, issues)
        self._check_repetition(text, issues)
        self._check_truncation(text, issues)

        sanitized = self._auto_fix(text, issues)

        is_valid = not any(
            i.severity == ValidationSeverity.CRITICAL for i in issues
        )

        if issues:
            codes = [i.code for i in issues]
            logger.debug("Validation issues: %s", codes)

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            sanitized_text=sanitized,
            original_text=text,
        )

    def _check_empty(self, text: str, issues: list[ValidationIssue]) -> None:
        stripped = text.strip()
        if not stripped:
            issues.append(ValidationIssue(
                code="EMPTY_RESPONSE",
                message="La respuesta está vacía",
                severity=ValidationSeverity.CRITICAL,
            ))
        elif len(stripped) < _MIN_RESPONSE_LENGTH:
            issues.append(ValidationIssue(
                code="TOO_SHORT",
                message="La respuesta es demasiado corta",
                severity=ValidationSeverity.WARNING,
            ))

    def _check_markdown_integrity(self, text: str, issues: list[ValidationIssue]) -> None:
        bold_count = text.count("**")
        if bold_count % 2 != 0:
            issues.append(ValidationIssue(
                code="UNCLOSED_BOLD",
                message="Marcador de negrita (**) sin cerrar",
                severity=ValidationSeverity.INFO,
            ))

        italic_singles = len(re.findall(r"(?<!\*)\*(?!\*)", text))
        if italic_singles % 2 != 0:
            issues.append(ValidationIssue(
                code="UNCLOSED_ITALIC",
                message="Marcador de cursiva (*) sin cerrar",
                severity=ValidationSeverity.INFO,
            ))

    def _check_code_blocks(self, text: str, issues: list[ValidationIssue]) -> None:
        fence_count = text.count("```")
        if fence_count % 2 != 0:
            issues.append(ValidationIssue(
                code="UNCLOSED_CODE_BLOCK",
                message="Bloque de código (```) sin cerrar",
                severity=ValidationSeverity.WARNING,
                details=f"Found {fence_count} fence markers (odd)",
            ))

    def _check_hallucination_patterns(self, text: str, issues: list[ValidationIssue]) -> None:
        for pattern in _HALLUCINATION_PATTERNS:
            match = pattern.search(text)
            if match:
                issues.append(ValidationIssue(
                    code="HALLUCINATION_PATTERN",
                    message="Posible patrón de alucinación detectado",
                    severity=ValidationSeverity.WARNING,
                    details=match.group(0)[:100],
                ))
                break

    def _check_policy_violations(self, text: str, issues: list[ValidationIssue]) -> None:
        for pattern in _POLICY_VIOLATIONS:
            match = pattern.search(text)
            if match:
                issues.append(ValidationIssue(
                    code="POLICY_VIOLATION",
                    message="Contenido que viola la política de seguridad detectado en la respuesta",
                    severity=ValidationSeverity.CRITICAL,
                    details=match.group(0)[:100],
                ))
                break

    def _check_repetition(self, text: str, issues: list[ValidationIssue]) -> None:
        lines = text.strip().split("\n")
        if len(lines) < _REPETITION_THRESHOLD:
            return

        seen: dict[str, int] = {}
        for line in lines:
            stripped = line.strip()
            if len(stripped) < 10:
                continue
            seen[stripped] = seen.get(stripped, 0) + 1

        for line_text, count in seen.items():
            if count >= _REPETITION_THRESHOLD:
                issues.append(ValidationIssue(
                    code="EXCESSIVE_REPETITION",
                    message=f"Línea repetida {count} veces",
                    severity=ValidationSeverity.WARNING,
                    details=line_text[:80],
                ))
                break

    def _check_truncation(self, text: str, issues: list[ValidationIssue]) -> None:
        stripped = text.rstrip()
        if not stripped:
            return

        truncation_signals = [
            stripped.endswith("...") and not stripped.endswith("...."),
            stripped.endswith("```") and stripped.count("```") % 2 != 0,
            stripped[-1] in (",", ":", "{", "["),
        ]

        if any(truncation_signals):
            issues.append(ValidationIssue(
                code="POSSIBLE_TRUNCATION",
                message="La respuesta puede estar truncada",
                severity=ValidationSeverity.INFO,
            ))

    def _auto_fix(self, text: str, issues: list[ValidationIssue]) -> str:
        """Applies safe auto-corrections based on detected issues."""
        fixed = text

        issue_codes = {i.code for i in issues}

        if "UNCLOSED_CODE_BLOCK" in issue_codes:
            fence_count = fixed.count("```")
            if fence_count % 2 != 0:
                fixed = fixed.rstrip() + "\n```"
                logger.debug("Auto-fix: closed unclosed code block")

        return fixed


_validator_instance: ResponseValidator | None = None


def get_validator() -> ResponseValidator:
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = ResponseValidator()
    return _validator_instance


def validate_response(text: str) -> ValidationResult:
    """Convenience function to validate a response using the global validator."""
    return get_validator().validate(text)
