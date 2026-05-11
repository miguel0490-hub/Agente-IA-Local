"""Immutable audit log for SOC2/ISO27001 compliance.

Stores security-relevant events in the database with tamper-evident hashing.
Each entry includes a chain hash linking to the previous entry, providing
cryptographic proof of log integrity.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Table,
    Column,
    Integer,
    Text,
    DateTime,
    text,
)

from src.database.database import engine, metadata as db_metadata
from src.core.logger import get_logger

logger = get_logger(__name__)

GENESIS_HASH = "0" * 64

audit_log_table = Table(
    "audit_log",
    db_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("timestamp", DateTime, nullable=False),
    Column("event_type", Text, nullable=False),
    Column("actor_id", Integer),
    Column("target_id", Integer),
    Column("details", Text),
    Column("ip_address", Text),
    Column("correlation_id", Text),
    Column("chain_hash", Text, nullable=False),
    extend_existing=True,
)


def init_audit_table() -> None:
    """Creates the audit_log table if it doesn't exist."""
    audit_log_table.create(engine, checkfirst=True)
    logger.info("Audit log table initialized.")


def _compute_chain_hash(prev_hash: str, event_data: dict) -> str:
    """Computes SHA-256 chain hash for tamper evidence.

    Hash = SHA256(prev_hash + canonical_json(event_data))
    """
    canonical = json.dumps(event_data, sort_keys=True, default=str)
    payload = f"{prev_hash}{canonical}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _get_last_chain_hash() -> str:
    """Retrieves the chain hash of the most recent audit entry."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT chain_hash FROM audit_log ORDER BY id DESC LIMIT 1")
        ).fetchone()
    if row:
        return row._mapping["chain_hash"]
    return GENESIS_HASH


def log_event(
    event_type: str,
    *,
    actor_id: int | None = None,
    target_id: int | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str = "",
    correlation_id: str = "",
) -> int:
    """Records an audit event with chain hash. Returns the event ID."""
    from src.core.logger import get_correlation_id

    now = datetime.now(tz=timezone.utc)
    cid = correlation_id or get_correlation_id()
    details_json = json.dumps(details, default=str) if details else None

    event_data = {
        "timestamp": now.isoformat(),
        "event_type": event_type,
        "actor_id": actor_id,
        "target_id": target_id,
        "details": details_json,
        "ip_address": ip_address,
        "correlation_id": cid,
    }

    prev_hash = _get_last_chain_hash()
    chain_hash = _compute_chain_hash(prev_hash, event_data)

    with engine.begin() as conn:
        dialect = engine.dialect.name
        if dialect.startswith("postgresql"):
            event_id = conn.execute(
                text(
                    "INSERT INTO audit_log "
                    "(timestamp, event_type, actor_id, target_id, details, "
                    "ip_address, correlation_id, chain_hash) "
                    "VALUES (:ts, :et, :aid, :tid, :det, :ip, :cid, :ch) "
                    "RETURNING id"
                ),
                {
                    "ts": now, "et": event_type, "aid": actor_id,
                    "tid": target_id, "det": details_json,
                    "ip": ip_address, "cid": cid, "ch": chain_hash,
                },
            ).scalar_one()
        else:
            conn.execute(
                text(
                    "INSERT INTO audit_log "
                    "(timestamp, event_type, actor_id, target_id, details, "
                    "ip_address, correlation_id, chain_hash) "
                    "VALUES (:ts, :et, :aid, :tid, :det, :ip, :cid, :ch)"
                ),
                {
                    "ts": now, "et": event_type, "aid": actor_id,
                    "tid": target_id, "det": details_json,
                    "ip": ip_address, "cid": cid, "ch": chain_hash,
                },
            )
            event_id = conn.execute(
                text("SELECT id FROM audit_log ORDER BY id DESC LIMIT 1")
            ).scalar_one()

    logger.info(
        "Audit event logged: type=%s actor=%s target=%s id=%s",
        event_type, actor_id, target_id, event_id,
    )
    return event_id


def get_audit_events(
    *,
    event_type: str | None = None,
    actor_id: int | None = None,
    since: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Queries audit events with optional filters."""
    clauses: list[str] = []
    params: dict[str, Any] = {"lim": limit}

    if event_type:
        clauses.append("event_type = :et")
        params["et"] = event_type
    if actor_id is not None:
        clauses.append("actor_id = :aid")
        params["aid"] = actor_id
    if since:
        clauses.append("timestamp >= :since")
        params["since"] = since

    where = ""
    if clauses:
        where = "WHERE " + " AND ".join(clauses)

    sql = f"SELECT * FROM audit_log {where} ORDER BY id DESC LIMIT :lim"

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        entry = dict(row._mapping)
        if entry.get("details"):
            try:
                entry["details"] = json.loads(entry["details"])
            except (json.JSONDecodeError, TypeError):
                pass
        results.append(entry)
    return results


def verify_chain_integrity() -> tuple[bool, int]:
    """Verifies the audit log chain hasn't been tampered with.

    Re-computes every chain hash from the genesis and compares with stored
    values. Returns (is_valid, last_verified_id). If the chain is empty,
    returns (True, 0).
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM audit_log ORDER BY id ASC")
        ).fetchall()

    if not rows:
        return True, 0

    prev_hash = GENESIS_HASH
    last_verified = 0

    for row in rows:
        m = row._mapping
        ts = m["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        ts_str = ts.isoformat()

        event_data = {
            "timestamp": ts_str,
            "event_type": m["event_type"],
            "actor_id": m["actor_id"],
            "target_id": m["target_id"],
            "details": m["details"],
            "ip_address": m["ip_address"],
            "correlation_id": m["correlation_id"],
        }

        expected = _compute_chain_hash(prev_hash, event_data)
        if expected != m["chain_hash"]:
            logger.error(
                "Audit chain integrity violation at id=%s: expected=%s stored=%s",
                m["id"], expected, m["chain_hash"],
            )
            return False, last_verified

        prev_hash = m["chain_hash"]
        last_verified = m["id"]

    logger.info("Audit chain verified: %d entries, all valid.", len(rows))
    return True, last_verified
