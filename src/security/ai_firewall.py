"""Advanced AI security: multi-turn attack detection, trust scoring,
output validation, and egress control for LLM interactions.

Extends the existing prompt injection detector and LLM firewall with
conversation-level analysis, delayed injection detection, and provenance tracking.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.core.logger import get_logger
from src.security.prompt_injection_detector import PromptInjectionDetector

logger = get_logger(__name__)

_SIGNING_KEY = os.getenv("AI_PROVENANCE_KEY", "superagente-provenance-v1")


class ThreatType(Enum):
    MULTI_TURN_INJECTION = "multi_turn_injection"
    DELAYED_INJECTION = "delayed_injection"
    MEMORY_POISONING = "memory_poisoning"
    RAG_POISONING = "rag_poisoning"
    TOOL_OUTPUT_POISONING = "tool_output_poisoning"
    HALLUCINATION = "hallucination"
    DATA_EXFILTRATION = "data_exfiltration"
    EGRESS_VIOLATION = "egress_violation"


@dataclass(frozen=True)
class ThreatDetection:
    """A detected threat in the AI pipeline."""
    threat_type: ThreatType
    severity: int  # 0-100
    description: str
    evidence: str = ""
    turn_index: int = -1


@dataclass(frozen=True)
class ConversationAnalysis:
    """Result of analyzing an entire conversation for threats."""
    threats: list[ThreatDetection]
    overall_risk: int
    safe_to_continue: bool
    recommendations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProvenanceRecord:
    """Cryptographic provenance for AI-generated content."""
    content_hash: str
    model: str
    timestamp: str
    signature: str
    metadata: dict[str, Any] = field(default_factory=dict)


class MultiTurnDetector:
    """Detects attacks that span multiple conversation turns."""

    _ESCALATION_PATTERNS = [
        (r"(?:let me|can you|please)\s+(?:try|test)\s+(?:something|this)", 5),
        (r"(?:now|ok|good)\s+(?:ignore|forget|override)", 15),
        (r"(?:remember|recall)\s+(?:what i said|earlier|before)", 10),
        (r"(?:as we|like i)\s+(?:discussed|agreed|established)", 10),
    ]

    _CONTEXT_MANIPULATION_PATTERNS = [
        (r"(?:actually|wait)\s*,?\s*(?:i meant|i want|change|modify)", 5),
        (r"(?:the real|my actual)\s+(?:question|request|task)", 10),
        (r"(?:between us|off the record|privately|secretly)", 15),
    ]

    @classmethod
    def analyze_conversation(
        cls,
        messages: list[dict[str, str]],
    ) -> ConversationAnalysis:
        """Analyzes a full conversation for multi-turn attack patterns."""
        threats: list[ThreatDetection] = []
        detector = PromptInjectionDetector()

        injection_turns: list[int] = []
        escalation_score = 0

        for i, msg in enumerate(messages):
            if msg.get("role") != "user":
                continue

            content = msg.get("content", "")
            if not content:
                continue

            result = detector.analyze(content)
            if result.is_suspicious:
                injection_turns.append(i)

            for pattern, weight in cls._ESCALATION_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    escalation_score += weight

            for pattern, weight in cls._CONTEXT_MANIPULATION_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    escalation_score += weight

        if len(injection_turns) >= 2:
            threats.append(ThreatDetection(
                threat_type=ThreatType.MULTI_TURN_INJECTION,
                severity=min(100, 30 + len(injection_turns) * 15),
                description=f"Suspicious patterns detected across {len(injection_turns)} turns",
                evidence=f"Turns: {injection_turns}",
            ))

        if len(injection_turns) >= 1 and escalation_score > 20:
            threats.append(ThreatDetection(
                threat_type=ThreatType.DELAYED_INJECTION,
                severity=min(100, escalation_score + 20),
                description="Gradual escalation pattern detected with injection attempts",
            ))

        if _detect_memory_poisoning(messages):
            threats.append(ThreatDetection(
                threat_type=ThreatType.MEMORY_POISONING,
                severity=60,
                description="Attempts to establish false context or modify system behavior through conversation history",
            ))

        overall_risk = min(100, sum(t.severity for t in threats))
        recommendations = []
        if overall_risk > 50:
            recommendations.append("Consider resetting conversation context")
        if overall_risk > 70:
            recommendations.append("Flag for human review")
            recommendations.append("Restrict tool access for this session")

        return ConversationAnalysis(
            threats=threats,
            overall_risk=overall_risk,
            safe_to_continue=overall_risk < 50,
            recommendations=recommendations,
        )


def _detect_memory_poisoning(messages: list[dict[str, str]]) -> bool:
    """Detects attempts to poison conversation memory."""
    user_messages = [m.get("content", "") for m in messages if m.get("role") == "user"]
    if len(user_messages) < 3:
        return False

    false_context_patterns = [
        r"you\s+(?:said|told me|agreed|promised)\s+(?:that|to)",
        r"(?:we agreed|you confirmed|as per our)\s",
        r"(?:your instructions|your rules)\s+(?:say|allow|permit)",
        r"(?:earlier you|before you)\s+(?:confirmed|said|mentioned)",
    ]

    hits = 0
    for msg in user_messages:
        for pattern in false_context_patterns:
            if re.search(pattern, msg, re.IGNORECASE):
                hits += 1
                break

    return hits >= 2


class RAGPoisonDetector:
    """Detects injection attempts in RAG-retrieved documents."""

    _INJECTION_IN_DOCS = [
        r"(?:ignore|disregard)\s+(?:previous|above|all)\s+(?:instructions|context)",
        r"(?:system|admin)\s*:\s*",
        r"<\|(?:im_start|system)\|>",
        r"###\s*(?:SYSTEM|INSTRUCTION|OVERRIDE)",
        r"\[INST\]|\[/INST\]",
        r"BEGININSTRUCTION|ENDINSTRUCTION",
    ]

    @classmethod
    def scan_documents(
        cls,
        documents: list[dict[str, str]],
    ) -> list[ThreatDetection]:
        """Scans retrieved documents for injection payloads."""
        threats = []
        for i, doc in enumerate(documents):
            content = doc.get("content", "") or doc.get("chunk_text", "")
            for pattern in cls._INJECTION_IN_DOCS:
                if re.search(pattern, content, re.IGNORECASE):
                    threats.append(ThreatDetection(
                        threat_type=ThreatType.RAG_POISONING,
                        severity=70,
                        description=f"Injection payload found in retrieved document #{i}",
                        evidence=content[:200],
                    ))
                    break
        return threats


class ToolOutputValidator:
    """Validates tool outputs before they're fed back to the LLM."""

    _SUSPICIOUS_OUTPUT_PATTERNS = [
        (r"(?:system|admin)\s+(?:prompt|instruction)", 30),
        (r"(?:api[_-]?key|secret|token|password)\s*[:=]\s*\S+", 50),
        (r"(?:BEGIN|-----)\s*(?:RSA|PRIVATE|CERTIFICATE)", 80),
        (r"(?:aws_access_key|AKIA[A-Z0-9]{16})", 90),
    ]

    @classmethod
    def validate(cls, tool_name: str, output: str) -> list[ThreatDetection]:
        threats = []
        for pattern, severity in cls._SUSPICIOUS_OUTPUT_PATTERNS:
            if re.search(pattern, output, re.IGNORECASE):
                threats.append(ThreatDetection(
                    threat_type=ThreatType.TOOL_OUTPUT_POISONING,
                    severity=severity,
                    description=f"Suspicious content in {tool_name} output",
                    evidence=output[:100],
                ))
        return threats


class EgressController:
    """Controls outbound network access from AI-generated requests."""

    _DEFAULT_ALLOWED_DOMAINS = frozenset({
        "api.openai.com",
        "generativelanguage.googleapis.com",
        "api.groq.com",
        "openrouter.ai",
        "api.stability.ai",
        "api.duckduckgo.com",
    })

    def __init__(self) -> None:
        extra = os.getenv("AI_EGRESS_ALLOWED_DOMAINS", "")
        extra_domains = frozenset(d.strip() for d in extra.split(",") if d.strip())
        self._allowed = self._DEFAULT_ALLOWED_DOMAINS | extra_domains
        self._blocked_patterns = [
            re.compile(r"^(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)\."),
            re.compile(r"^127\."),
            re.compile(r"^169\.254\."),
            re.compile(r"^0\."),
        ]

    def check_egress(self, url: str) -> tuple[bool, str]:
        """Checks if an outbound URL is allowed by egress policy."""
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
        except Exception:
            return False, "Invalid URL"

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False, "No hostname"

        for pattern in self._blocked_patterns:
            if pattern.match(hostname):
                return False, f"Private IP blocked: {hostname}"

        if hostname in self._allowed:
            return True, ""

        if any(hostname.endswith(f".{d}") for d in self._allowed):
            return True, ""

        return False, f"Domain not in egress allowlist: {hostname}"


class HallucinationDetector:
    """Basic hallucination detection via confidence scoring and grounding."""

    _LOW_CONFIDENCE_INDICATORS = [
        r"\bi(?:'m| am)\s+not\s+(?:sure|certain|confident)",
        r"\b(?:might|could|may)\s+(?:be|have)\b",
        r"\b(?:approximately|roughly|around|about)\s+\d",
        r"\b(?:i think|i believe|possibly|perhaps|maybe)\b",
    ]

    _CONTRADICTION_PATTERNS = [
        r"\b(?:actually|wait|correction|i meant|let me correct)\b",
        r"\b(?:on the other hand|however|but then again)\b",
    ]

    @classmethod
    def assess_response(
        cls,
        response: str,
        *,
        grounding_docs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Assesses a model response for potential hallucination indicators."""
        confidence_hits = 0
        for pattern in cls._LOW_CONFIDENCE_INDICATORS:
            if re.search(pattern, response, re.IGNORECASE):
                confidence_hits += 1

        contradiction_hits = 0
        for pattern in cls._CONTRADICTION_PATTERNS:
            if re.search(pattern, response, re.IGNORECASE):
                contradiction_hits += 1

        base_confidence = max(0, 100 - confidence_hits * 15 - contradiction_hits * 20)

        grounding_score = 100
        if grounding_docs:
            response_lower = response.lower()
            doc_text = " ".join(grounding_docs).lower()
            response_words = set(re.findall(r"\b\w{4,}\b", response_lower))
            doc_words = set(re.findall(r"\b\w{4,}\b", doc_text))
            if response_words:
                overlap = len(response_words & doc_words) / len(response_words)
                grounding_score = int(overlap * 100)

        return {
            "confidence_score": base_confidence,
            "grounding_score": grounding_score,
            "low_confidence_indicators": confidence_hits,
            "contradictions": contradiction_hits,
            "is_likely_hallucination": base_confidence < 40 or grounding_score < 20,
        }


def sign_content(content: str, model: str, **metadata: Any) -> ProvenanceRecord:
    """Creates a signed provenance record for AI-generated content."""
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    timestamp = datetime.now(tz=__import__("datetime").timezone.utc).isoformat()

    payload = f"{content_hash}:{model}:{timestamp}"
    signature = hmac.new(
        _SIGNING_KEY.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()

    return ProvenanceRecord(
        content_hash=content_hash,
        model=model,
        timestamp=timestamp,
        signature=signature,
        metadata=metadata,
    )


def verify_provenance(record: ProvenanceRecord) -> bool:
    """Verifies a provenance record's signature."""
    payload = f"{record.content_hash}:{record.model}:{record.timestamp}"
    expected = hmac.new(
        _SIGNING_KEY.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, record.signature)
