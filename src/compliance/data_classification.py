"""Data classification labels and PII detection for SOC2 compliance.

Provides field-level classification (PUBLIC → RESTRICTED), regex-based PII
scanning, and a data inventory helper used by privacy compliance reports.
"""
from __future__ import annotations

import re
from enum import Enum
from dataclasses import dataclass, field


class DataClassification(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass(frozen=True)
class PIIDetectionResult:
    has_pii: bool
    pii_types: tuple[str, ...]
    confidence: float


_PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),
    "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
}

FIELD_CLASSIFICATIONS: dict[str, DataClassification] = {
    "password_hash": DataClassification.RESTRICTED,
    "encrypted_api_keys": DataClassification.RESTRICTED,
    "email": DataClassification.CONFIDENTIAL,
    "first_name": DataClassification.CONFIDENTIAL,
    "last_name": DataClassification.CONFIDENTIAL,
    "ip_address": DataClassification.CONFIDENTIAL,
    "username": DataClassification.INTERNAL,
    "chat_content": DataClassification.CONFIDENTIAL,
    "content": DataClassification.CONFIDENTIAL,
    "message": DataClassification.CONFIDENTIAL,
    "subject": DataClassification.INTERNAL,
    "is_admin": DataClassification.INTERNAL,
    "is_active": DataClassification.INTERNAL,
    "is_verified": DataClassification.INTERNAL,
    "created_at": DataClassification.PUBLIC,
    "updated_at": DataClassification.PUBLIC,
    "id": DataClassification.PUBLIC,
    "role": DataClassification.PUBLIC,
    "status": DataClassification.PUBLIC,
    "title": DataClassification.INTERNAL,
}

_TABLE_FIELDS: dict[str, list[str]] = {
    "users": [
        "id", "first_name", "last_name", "email", "username",
        "password_hash", "encrypted_api_keys", "is_verified",
        "is_admin", "is_active", "created_at",
    ],
    "chats": ["id", "user_id", "title", "updated_at"],
    "messages": ["id", "chat_id", "role", "content", "extra_data"],
    "contact_messages": [
        "id", "user_id", "subject", "message", "status",
        "admin_reply", "created_at",
    ],
}


def detect_pii(text: str) -> PIIDetectionResult:
    """Scans text for PII patterns. Returns detection result with types found."""
    if not text:
        return PIIDetectionResult(has_pii=False, pii_types=(), confidence=0.0)

    found: list[str] = []
    for pii_type, pattern in _PII_PATTERNS.items():
        if pattern.search(text):
            found.append(pii_type)

    if not found:
        return PIIDetectionResult(has_pii=False, pii_types=(), confidence=0.0)

    confidence = min(1.0, 0.5 + 0.15 * len(found))
    return PIIDetectionResult(
        has_pii=True,
        pii_types=tuple(found),
        confidence=round(confidence, 2),
    )


def classify_field(field_name: str) -> DataClassification:
    """Returns classification level for a database field name."""
    return FIELD_CLASSIFICATIONS.get(field_name, DataClassification.INTERNAL)


def get_data_inventory() -> dict[str, dict]:
    """Returns a complete data inventory with field-level classifications.

    Used for SOC2/ISO27001 compliance reporting — maps every known table
    and column to its classification tier.
    """
    inventory: dict[str, dict] = {}
    for table, fields in _TABLE_FIELDS.items():
        table_entry: dict[str, str] = {}
        for f in fields:
            table_entry[f] = classify_field(f).value
        highest = DataClassification.PUBLIC
        priority = [
            DataClassification.PUBLIC,
            DataClassification.INTERNAL,
            DataClassification.CONFIDENTIAL,
            DataClassification.RESTRICTED,
        ]
        for f in fields:
            c = classify_field(f)
            if priority.index(c) > priority.index(highest):
                highest = c
        inventory[table] = {
            "fields": table_entry,
            "highest_classification": highest.value,
            "field_count": len(fields),
        }
    return inventory
