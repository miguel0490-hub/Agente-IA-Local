"""Tests for FASE 8 — Compliance & Governance (GDPR, SOC2, ISO27001).

Uses an in-memory SQLite database for full isolation.  Every test function
gets a fresh database via the ``setup_db`` fixture so tests never interfere
with each other.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest
from sqlalchemy import create_engine, text, MetaData

# ---------------------------------------------------------------------------
# Fixtures: in-memory SQLite engine that replaces the production engine
# ---------------------------------------------------------------------------

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    encrypted_api_keys TEXT,
    is_verified INTEGER NOT NULL DEFAULT 0,
    is_admin INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verification_token TEXT,
    verification_token_expires TIMESTAMP,
    reset_token TEXT,
    reset_token_expires TIMESTAMP,
    remember_token TEXT,
    remember_token_expires TIMESTAMP
);
CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    content TEXT,
    extra_data TEXT
);
CREATE TABLE IF NOT EXISTS contact_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    admin_reply TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL,
    event_type TEXT NOT NULL,
    actor_id INTEGER,
    target_id INTEGER,
    details TEXT,
    ip_address TEXT,
    correlation_id TEXT,
    chain_hash TEXT NOT NULL
);
"""


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    """Creates fresh in-memory tables and patches the production engine."""
    test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False})

    with test_engine.begin() as conn:
        for statement in _CREATE_TABLES_SQL.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(text(stmt))

    import src.database.database as db_mod
    monkeypatch.setattr(db_mod, "engine", test_engine)

    import src.compliance.audit_log as audit_mod
    monkeypatch.setattr(audit_mod, "engine", test_engine)

    import src.compliance.gdpr as gdpr_mod
    monkeypatch.setattr(gdpr_mod, "engine", test_engine)

    yield test_engine


def _seed_user(engine, uid=1, email="alice@example.com", username="alice"):
    """Inserts a test user and returns their id."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, first_name, last_name, email, username, password_hash, "
                "encrypted_api_keys, is_verified, is_active, created_at) "
                "VALUES (:id, :fn, :ln, :em, :un, :ph, :ek, 1, 1, :ca)"
            ),
            {
                "id": uid, "fn": "Alice", "ln": "Smith",
                "em": email, "un": username, "ph": "hashed_pw",
                "ek": json.dumps({"openai": "sk-test"}),
                "ca": datetime.now(tz=timezone.utc),
            },
        )
    return uid


def _seed_chat(engine, user_id=1, title="Hello", age_days=0):
    """Inserts a chat with one message. Returns chat_id."""
    ts = datetime.now(tz=timezone.utc) - timedelta(days=age_days)
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO chats (user_id, title, updated_at) VALUES (:uid, :t, :ua)"),
            {"uid": user_id, "t": title, "ua": ts},
        )
        cid = conn.execute(text("SELECT id FROM chats ORDER BY id DESC LIMIT 1")).scalar_one()
        conn.execute(
            text("INSERT INTO messages (chat_id, role, content) VALUES (:cid, 'user', 'Hi')"),
            {"cid": cid},
        )
    return cid


def _seed_contact(engine, user_id=1, age_days=0):
    ts = datetime.now(tz=timezone.utc) - timedelta(days=age_days)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO contact_messages (user_id, subject, message, created_at) "
                "VALUES (:uid, 'Help', 'Need help', :ca)"
            ),
            {"uid": user_id, "ca": ts},
        )


# ===================================================================
# GDPR Tests
# ===================================================================

class TestGDPRExport:
    def test_export_returns_all_user_data(self, setup_db):
        from src.compliance.gdpr import export_user_data

        _seed_user(setup_db)
        _seed_chat(setup_db, user_id=1, title="Chat 1")
        _seed_contact(setup_db, user_id=1)

        result = export_user_data(1)

        assert result["user_id"] == 1
        assert result["profile"]["email"] == "alice@example.com"
        assert result["profile"]["first_name"] == "Alice"
        assert len(result["chats"]) == 1
        assert result["chats"][0]["title"] == "Chat 1"
        assert len(result["chats"][0]["messages"]) == 1
        assert len(result["contact_messages"]) == 1
        assert "export_timestamp" in result

    def test_export_nonexistent_user_returns_error(self, setup_db):
        from src.compliance.gdpr import export_user_data

        result = export_user_data(9999)
        assert result["error"] == "user_not_found"


class TestGDPRDelete:
    def test_delete_user_data_anonymized(self, setup_db):
        from src.compliance.gdpr import delete_user_data

        _seed_user(setup_db)
        _seed_chat(setup_db)
        _seed_contact(setup_db)

        counts = delete_user_data(1, keep_anonymized=True)

        assert counts["messages_deleted"] >= 1
        assert counts["chats_deleted"] >= 1
        assert counts["contacts_deleted"] >= 1
        assert counts["user_deleted"] == 1

        with setup_db.connect() as conn:
            user = conn.execute(text("SELECT * FROM users WHERE id = 1")).fetchone()
            assert user is not None
            assert user._mapping["first_name"] == "DELETED"
            assert user._mapping["encrypted_api_keys"] is None
            assert user._mapping["is_active"] == 0

    def test_delete_user_data_full_removal(self, setup_db):
        from src.compliance.gdpr import delete_user_data

        _seed_user(setup_db)
        _seed_chat(setup_db)

        counts = delete_user_data(1, keep_anonymized=False)

        assert counts["user_deleted"] == 1
        with setup_db.connect() as conn:
            user = conn.execute(text("SELECT * FROM users WHERE id = 1")).fetchone()
            assert user is None

    def test_delete_nonexistent_user_returns_zeros(self, setup_db):
        from src.compliance.gdpr import delete_user_data

        counts = delete_user_data(9999)
        assert counts["user_deleted"] == 0


class TestAnonymize:
    def test_anonymize_replaces_pii_with_hashes(self, setup_db):
        from src.compliance.gdpr import anonymize_user

        _seed_user(setup_db)
        _seed_chat(setup_db)
        _seed_contact(setup_db)

        anonymize_user(1)

        with setup_db.connect() as conn:
            user = conn.execute(text("SELECT * FROM users WHERE id = 1")).fetchone()
            m = user._mapping
            assert m["first_name"] != "Alice"
            assert m["last_name"] != "Smith"
            assert "anon.invalid" in m["email"]
            assert m["username"].startswith("anon_")
            assert m["encrypted_api_keys"] is None

            msgs = conn.execute(text("SELECT content FROM messages")).fetchall()
            for msg in msgs:
                assert msg._mapping["content"] == "[anonymized]"

            contacts = conn.execute(
                text("SELECT subject, message FROM contact_messages")
            ).fetchall()
            for c in contacts:
                assert c._mapping["subject"] == "[anonymized]"
                assert c._mapping["message"] == "[anonymized]"


class TestRetentionPolicy:
    def test_deletes_old_chats_and_contacts(self, setup_db):
        from src.compliance.gdpr import apply_retention_policy

        _seed_user(setup_db)
        _seed_chat(setup_db, user_id=1, title="recent", age_days=10)
        _seed_chat(setup_db, user_id=1, title="old", age_days=200)
        _seed_contact(setup_db, user_id=1, age_days=10)
        _seed_contact(setup_db, user_id=1, age_days=500)

        with mock.patch("src.compliance.gdpr.CHAT_RETENTION_DAYS", 90), \
             mock.patch("src.compliance.gdpr.RETENTION_DAYS", 365):
            counts = apply_retention_policy()

        assert counts["chats_deleted"] == 1
        assert counts["messages_deleted"] >= 1
        assert counts["contacts_deleted"] == 1

        with setup_db.connect() as conn:
            remaining = conn.execute(text("SELECT title FROM chats")).fetchall()
            assert len(remaining) == 1
            assert remaining[0]._mapping["title"] == "recent"


class TestConsentAndPrivacyReport:
    def test_consent_record_for_existing_user(self, setup_db):
        from src.compliance.gdpr import get_consent_record

        _seed_user(setup_db)
        record = get_consent_record(1)

        assert record["exists"] is True
        assert record["account_active"] is True
        assert record["consent_basis"] == "account_creation"

    def test_consent_record_for_missing_user(self, setup_db):
        from src.compliance.gdpr import get_consent_record

        record = get_consent_record(9999)
        assert record["exists"] is False

    def test_privacy_report_structure(self, setup_db):
        from src.compliance.gdpr import generate_privacy_report

        _seed_user(setup_db)
        _seed_chat(setup_db)

        report = generate_privacy_report()

        assert "report_timestamp" in report
        assert report["data_counts"]["total_users"] == 1
        assert report["data_counts"]["total_chats"] == 1
        assert "data_inventory" in report
        assert "users" in report["data_inventory"]
        assert len(report["gdpr_capabilities"]) >= 4


# ===================================================================
# Audit Log Tests
# ===================================================================

class TestAuditLogEvents:
    def test_log_and_retrieve_event(self, setup_db):
        from src.compliance.audit_log import log_event, get_audit_events

        eid = log_event(
            "auth.login",
            actor_id=1,
            details={"method": "password"},
            ip_address="1.2.3.4",
        )

        assert isinstance(eid, int)
        assert eid >= 1

        events = get_audit_events(event_type="auth.login")
        assert len(events) == 1
        assert events[0]["actor_id"] == 1
        assert events[0]["ip_address"] == "1.2.3.4"
        assert events[0]["details"]["method"] == "password"

    def test_filter_by_actor(self, setup_db):
        from src.compliance.audit_log import log_event, get_audit_events

        log_event("auth.login", actor_id=1)
        log_event("auth.login", actor_id=2)
        log_event("data.export", actor_id=1)

        events = get_audit_events(actor_id=1)
        assert len(events) == 2
        assert all(e["actor_id"] == 1 for e in events)

    def test_filter_by_since(self, setup_db):
        from src.compliance.audit_log import log_event, get_audit_events

        log_event("auth.login", actor_id=1)

        future = datetime.now(tz=timezone.utc) + timedelta(hours=1)
        events = get_audit_events(since=future)
        assert len(events) == 0

        past = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        events = get_audit_events(since=past)
        assert len(events) >= 1

    def test_limit_parameter(self, setup_db):
        from src.compliance.audit_log import log_event, get_audit_events

        for i in range(5):
            log_event("test.event", actor_id=i)

        events = get_audit_events(limit=3)
        assert len(events) == 3


class TestAuditChainIntegrity:
    def test_empty_chain_is_valid(self, setup_db):
        from src.compliance.audit_log import verify_chain_integrity

        valid, last_id = verify_chain_integrity()
        assert valid is True
        assert last_id == 0

    def test_chain_with_events_is_valid(self, setup_db):
        from src.compliance.audit_log import log_event, verify_chain_integrity

        log_event("auth.login", actor_id=1, details={"ip": "10.0.0.1"})
        log_event("admin.delete_user", actor_id=1, target_id=2)
        log_event("data.export", actor_id=3)

        valid, last_id = verify_chain_integrity()
        assert valid is True
        assert last_id >= 3

    def test_tampered_chain_detected(self, setup_db):
        from src.compliance.audit_log import log_event, verify_chain_integrity

        log_event("auth.login", actor_id=1)
        log_event("auth.logout", actor_id=1)

        with setup_db.begin() as conn:
            conn.execute(
                text("UPDATE audit_log SET chain_hash = 'tampered_hash' WHERE id = 2")
            )

        valid, last_id = verify_chain_integrity()
        assert valid is False
        assert last_id == 1


class TestAuditInitTable:
    def test_init_is_idempotent(self, setup_db):
        from src.compliance.audit_log import init_audit_table

        init_audit_table()
        init_audit_table()

        with setup_db.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM audit_log")).scalar()
            assert result == 0


# ===================================================================
# Data Classification Tests
# ===================================================================

class TestPIIDetection:
    def test_detects_email(self):
        from src.compliance.data_classification import detect_pii

        result = detect_pii("Contact me at user@example.com for details")
        assert result.has_pii is True
        assert "email" in result.pii_types

    def test_detects_phone(self):
        from src.compliance.data_classification import detect_pii

        result = detect_pii("Call me at 555-123-4567")
        assert result.has_pii is True
        assert "phone" in result.pii_types

    def test_detects_ssn(self):
        from src.compliance.data_classification import detect_pii

        result = detect_pii("SSN: 123-45-6789")
        assert result.has_pii is True
        assert "ssn" in result.pii_types

    def test_detects_credit_card(self):
        from src.compliance.data_classification import detect_pii

        result = detect_pii("Card: 4111 1111 1111 1111")
        assert result.has_pii is True
        assert "credit_card" in result.pii_types

    def test_detects_ip_address(self):
        from src.compliance.data_classification import detect_pii

        result = detect_pii("Server at 192.168.1.100")
        assert result.has_pii is True
        assert "ip_address" in result.pii_types

    def test_no_pii_in_clean_text(self):
        from src.compliance.data_classification import detect_pii

        result = detect_pii("Hello world, this is a normal message")
        assert result.has_pii is False
        assert len(result.pii_types) == 0
        assert result.confidence == 0.0

    def test_empty_text(self):
        from src.compliance.data_classification import detect_pii

        result = detect_pii("")
        assert result.has_pii is False

    def test_multiple_pii_types_increases_confidence(self):
        from src.compliance.data_classification import detect_pii

        result = detect_pii("Email: a@b.com, phone: 555-111-2222, SSN: 123-45-6789")
        assert result.has_pii is True
        assert len(result.pii_types) >= 3
        assert result.confidence > 0.5


class TestFieldClassification:
    def test_restricted_fields(self):
        from src.compliance.data_classification import classify_field, DataClassification

        assert classify_field("password_hash") == DataClassification.RESTRICTED
        assert classify_field("encrypted_api_keys") == DataClassification.RESTRICTED

    def test_confidential_fields(self):
        from src.compliance.data_classification import classify_field, DataClassification

        assert classify_field("email") == DataClassification.CONFIDENTIAL
        assert classify_field("first_name") == DataClassification.CONFIDENTIAL
        assert classify_field("ip_address") == DataClassification.CONFIDENTIAL

    def test_internal_fields(self):
        from src.compliance.data_classification import classify_field, DataClassification

        assert classify_field("username") == DataClassification.INTERNAL
        assert classify_field("is_admin") == DataClassification.INTERNAL

    def test_public_fields(self):
        from src.compliance.data_classification import classify_field, DataClassification

        assert classify_field("created_at") == DataClassification.PUBLIC
        assert classify_field("id") == DataClassification.PUBLIC

    def test_unknown_field_defaults_to_internal(self):
        from src.compliance.data_classification import classify_field, DataClassification

        assert classify_field("some_unknown_field") == DataClassification.INTERNAL


class TestDataInventory:
    def test_inventory_contains_all_tables(self):
        from src.compliance.data_classification import get_data_inventory

        inventory = get_data_inventory()
        assert "users" in inventory
        assert "chats" in inventory
        assert "messages" in inventory
        assert "contact_messages" in inventory

    def test_inventory_users_table_has_restricted_fields(self):
        from src.compliance.data_classification import get_data_inventory

        inventory = get_data_inventory()
        users = inventory["users"]
        assert users["highest_classification"] == "restricted"
        assert users["fields"]["password_hash"] == "restricted"
        assert users["fields"]["email"] == "confidential"

    def test_inventory_field_count(self):
        from src.compliance.data_classification import get_data_inventory

        inventory = get_data_inventory()
        for table_name, info in inventory.items():
            assert info["field_count"] > 0
            assert len(info["fields"]) == info["field_count"]
