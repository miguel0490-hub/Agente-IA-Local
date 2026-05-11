"""GDPR compliance: right to deletion, data export, retention, anonymization.

Implements Articles 17 (erasure), 20 (portability) and retention policies.
Works with both PostgreSQL and SQLite via the shared SQLAlchemy engine.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from src.database.database import engine, cleanup_expired_tokens
from src.core.logger import get_logger

logger = get_logger(__name__)

RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "365"))
CHAT_RETENTION_DAYS = int(os.getenv("CHAT_RETENTION_DAYS", "90"))


def _anon_hash(value: str) -> str:
    """One-way SHA-256 hash for anonymization — irreversible by design."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def export_user_data(user_id: int) -> dict[str, Any]:
    """GDPR Article 20: Right to data portability.

    Exports all user data as structured JSON suitable for machine-readable
    transfer to another data controller.
    """
    with engine.connect() as conn:
        user_row = conn.execute(
            text(
                "SELECT id, first_name, last_name, email, username, "
                "is_verified, is_admin, is_active, created_at "
                "FROM users WHERE id = :uid"
            ),
            {"uid": user_id},
        ).fetchone()

        if not user_row:
            logger.warning("GDPR export: user %s not found.", user_id)
            return {"error": "user_not_found", "user_id": user_id}

        profile = dict(user_row._mapping)
        if profile.get("created_at"):
            profile["created_at"] = str(profile["created_at"])

        chat_rows = conn.execute(
            text("SELECT id, title, updated_at FROM chats WHERE user_id = :uid ORDER BY id"),
            {"uid": user_id},
        ).fetchall()

        chats: list[dict[str, Any]] = []
        for crow in chat_rows:
            chat = dict(crow._mapping)
            chat_id = chat["id"]
            if chat.get("updated_at"):
                chat["updated_at"] = str(chat["updated_at"])

            msg_rows = conn.execute(
                text(
                    "SELECT role, content, extra_data FROM messages "
                    "WHERE chat_id = :cid ORDER BY id"
                ),
                {"cid": chat_id},
            ).fetchall()
            chat["messages"] = [dict(mr._mapping) for mr in msg_rows]
            chats.append(chat)

        contact_rows = conn.execute(
            text(
                "SELECT id, subject, message, status, admin_reply, created_at "
                "FROM contact_messages WHERE user_id = :uid ORDER BY id"
            ),
            {"uid": user_id},
        ).fetchall()

        contacts: list[dict[str, Any]] = []
        for cr in contact_rows:
            entry = dict(cr._mapping)
            if entry.get("created_at"):
                entry["created_at"] = str(entry["created_at"])
            contacts.append(entry)

    export = {
        "export_timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "user_id": user_id,
        "profile": profile,
        "chats": chats,
        "contact_messages": contacts,
    }

    logger.info("GDPR data export completed for user %s.", user_id)
    return export


def delete_user_data(user_id: int, *, keep_anonymized: bool = True) -> dict[str, int]:
    """GDPR Article 17: Right to erasure.

    Deletes or anonymizes all user data. When *keep_anonymized* is True the
    user profile is anonymized (for aggregate analytics) rather than fully
    removed. Returns counts of affected records.
    """
    counts: dict[str, int] = {
        "messages_deleted": 0,
        "chats_deleted": 0,
        "contacts_deleted": 0,
        "user_deleted": 0,
    }

    with engine.begin() as conn:
        user_exists = conn.execute(
            text("SELECT id FROM users WHERE id = :uid"),
            {"uid": user_id},
        ).fetchone()
        if not user_exists:
            logger.warning("GDPR delete: user %s not found.", user_id)
            return counts

        chat_ids = conn.execute(
            text("SELECT id FROM chats WHERE user_id = :uid"),
            {"uid": user_id},
        ).fetchall()
        cids = [r._mapping["id"] for r in chat_ids]

        for cid in cids:
            result = conn.execute(
                text("DELETE FROM messages WHERE chat_id = :cid"),
                {"cid": cid},
            )
            counts["messages_deleted"] += result.rowcount

        result = conn.execute(
            text("DELETE FROM chats WHERE user_id = :uid"),
            {"uid": user_id},
        )
        counts["chats_deleted"] = result.rowcount

        result = conn.execute(
            text("DELETE FROM contact_messages WHERE user_id = :uid"),
            {"uid": user_id},
        )
        counts["contacts_deleted"] = result.rowcount

        if keep_anonymized:
            anon_email = _anon_hash(f"user-{user_id}@deleted") + "@anon.invalid"
            anon_name = "DELETED"
            anon_username = f"deleted_{_anon_hash(str(user_id))[:12]}"
            conn.execute(
                text(
                    "UPDATE users SET "
                    "first_name = :fn, last_name = :ln, email = :em, "
                    "username = :un, password_hash = :ph, encrypted_api_keys = NULL, "
                    "is_active = 0, verification_token = NULL, "
                    "verification_token_expires = NULL, reset_token = NULL, "
                    "reset_token_expires = NULL, remember_token = NULL, "
                    "remember_token_expires = NULL "
                    "WHERE id = :uid"
                ),
                {
                    "fn": anon_name, "ln": anon_name,
                    "em": anon_email, "un": anon_username,
                    "ph": "DELETED", "uid": user_id,
                },
            )
            counts["user_deleted"] = 1
        else:
            conn.execute(
                text("DELETE FROM users WHERE id = :uid"),
                {"uid": user_id},
            )
            counts["user_deleted"] = 1

    logger.info(
        "GDPR deletion completed for user %s (anonymized=%s): %s",
        user_id, keep_anonymized, counts,
    )
    return counts


def anonymize_user(user_id: int) -> None:
    """Replaces all PII with irreversible hashes while keeping non-PII data.

    Preserves anonymized records for analytics — only identifying
    information is replaced with one-way SHA-256 hashes.
    """
    with engine.begin() as conn:
        user_row = conn.execute(
            text("SELECT email, username, first_name, last_name FROM users WHERE id = :uid"),
            {"uid": user_id},
        ).fetchone()

        if not user_row:
            logger.warning("Anonymize: user %s not found.", user_id)
            return

        m = user_row._mapping
        anon_email = _anon_hash(m["email"]) + "@anon.invalid"
        anon_username = "anon_" + _anon_hash(m["username"])[:12]
        anon_first = _anon_hash(m["first_name"])[:16]
        anon_last = _anon_hash(m["last_name"])[:16]

        conn.execute(
            text(
                "UPDATE users SET "
                "first_name = :fn, last_name = :ln, email = :em, "
                "username = :un, encrypted_api_keys = NULL, "
                "verification_token = NULL, verification_token_expires = NULL, "
                "reset_token = NULL, reset_token_expires = NULL, "
                "remember_token = NULL, remember_token_expires = NULL "
                "WHERE id = :uid"
            ),
            {
                "fn": anon_first, "ln": anon_last,
                "em": anon_email, "un": anon_username,
                "uid": user_id,
            },
        )

        chat_rows = conn.execute(
            text("SELECT id FROM chats WHERE user_id = :uid"),
            {"uid": user_id},
        ).fetchall()

        for crow in chat_rows:
            cid = crow._mapping["id"]
            conn.execute(
                text(
                    "UPDATE messages SET content = '[anonymized]' "
                    "WHERE chat_id = :cid AND content IS NOT NULL"
                ),
                {"cid": cid},
            )

        conn.execute(
            text(
                "UPDATE contact_messages SET "
                "message = '[anonymized]', subject = '[anonymized]' "
                "WHERE user_id = :uid"
            ),
            {"uid": user_id},
        )

    logger.info("User %s anonymized successfully.", user_id)


def apply_retention_policy() -> dict[str, int]:
    """Enforces data retention limits.

    Deletes data older than the configured thresholds:
    - Chats/messages older than CHAT_RETENTION_DAYS
    - Contact messages older than RETENTION_DAYS
    - Expired tokens (via cleanup_expired_tokens)
    """
    counts: dict[str, int] = {
        "chats_deleted": 0,
        "messages_deleted": 0,
        "contacts_deleted": 0,
    }

    chat_cutoff = datetime.now(tz=timezone.utc) - timedelta(days=CHAT_RETENTION_DAYS)
    contact_cutoff = datetime.now(tz=timezone.utc) - timedelta(days=RETENTION_DAYS)

    with engine.begin() as conn:
        old_chats = conn.execute(
            text("SELECT id FROM chats WHERE updated_at < :cutoff"),
            {"cutoff": chat_cutoff},
        ).fetchall()
        old_cids = [r._mapping["id"] for r in old_chats]

        for cid in old_cids:
            result = conn.execute(
                text("DELETE FROM messages WHERE chat_id = :cid"),
                {"cid": cid},
            )
            counts["messages_deleted"] += result.rowcount

        if old_cids:
            result = conn.execute(
                text("DELETE FROM chats WHERE updated_at < :cutoff"),
                {"cutoff": chat_cutoff},
            )
            counts["chats_deleted"] = result.rowcount

        result = conn.execute(
            text("DELETE FROM contact_messages WHERE created_at < :cutoff"),
            {"cutoff": contact_cutoff},
        )
        counts["contacts_deleted"] = result.rowcount

    try:
        cleanup_expired_tokens()
    except Exception as exc:
        logger.warning("Token cleanup during retention sweep failed: %s", exc)

    logger.info("Retention policy applied: %s", counts)
    return counts


def get_consent_record(user_id: int) -> dict[str, Any]:
    """Returns the consent status for a user.

    In the current schema consent is implied by account creation.
    A future consent_records table can be plugged in here.
    """
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id, email, is_active, is_verified, created_at "
                "FROM users WHERE id = :uid"
            ),
            {"uid": user_id},
        ).fetchone()

    if not row:
        return {"user_id": user_id, "exists": False}

    m = row._mapping
    return {
        "user_id": user_id,
        "exists": True,
        "account_active": bool(m["is_active"]),
        "email_verified": bool(m["is_verified"]),
        "account_created": str(m["created_at"]) if m["created_at"] else None,
        "consent_basis": "account_creation",
        "data_processing_legal_basis": "legitimate_interest_and_consent",
    }


def generate_privacy_report() -> dict[str, Any]:
    """Generates a privacy compliance report with data inventory statistics.

    Useful for DPO (Data Protection Officer) reviews and SOC2 evidence
    collection.
    """
    from src.compliance.data_classification import get_data_inventory

    with engine.connect() as conn:
        total_users = conn.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0
        active_users = conn.execute(
            text("SELECT COUNT(*) FROM users WHERE is_active = 1")
        ).scalar() or 0
        total_chats = conn.execute(text("SELECT COUNT(*) FROM chats")).scalar() or 0
        total_messages = conn.execute(text("SELECT COUNT(*) FROM messages")).scalar() or 0
        total_contacts = conn.execute(
            text("SELECT COUNT(*) FROM contact_messages")
        ).scalar() or 0

        inactive_users = conn.execute(
            text("SELECT COUNT(*) FROM users WHERE is_active = 0")
        ).scalar() or 0

        chat_cutoff = datetime.now(tz=timezone.utc) - timedelta(days=CHAT_RETENTION_DAYS)
        stale_chats = conn.execute(
            text("SELECT COUNT(*) FROM chats WHERE updated_at < :cutoff"),
            {"cutoff": chat_cutoff},
        ).scalar() or 0

    inventory = get_data_inventory()

    return {
        "report_timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "retention_policy": {
            "data_retention_days": RETENTION_DAYS,
            "chat_retention_days": CHAT_RETENTION_DAYS,
        },
        "data_counts": {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": inactive_users,
            "total_chats": total_chats,
            "total_messages": total_messages,
            "total_contact_messages": total_contacts,
            "chats_past_retention": stale_chats,
        },
        "data_inventory": inventory,
        "gdpr_capabilities": [
            "data_export (Article 20)",
            "right_to_erasure (Article 17)",
            "anonymization",
            "retention_policy_enforcement",
            "consent_records",
        ],
    }
