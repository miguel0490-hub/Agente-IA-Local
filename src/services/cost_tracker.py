"""LLM usage and cost tracking.

Logs token usage per request and provides aggregation for the admin dashboard.
Stores data in-memory with periodic flush to DB when the usage_log table exists.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.core.logger import get_logger

logger = get_logger(__name__)

_COST_PER_1K_INPUT: dict[str, float] = {
    "gemini-2.5-pro": 0.00125,
    "llama-3.3-70b-versatile": 0.00059,
    "openrouter/auto": 0.001,
}
_DEFAULT_COST_PER_1K = 0.001


@dataclass
class UsageEntry:
    user_id: int
    model: str
    tokens_in: int
    tokens_out: int
    estimated_cost: float
    timestamp: datetime = field(default_factory=datetime.now)


_usage_log: list[UsageEntry] = []
_lock = threading.Lock()


def record_usage(
    user_id: int,
    model: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
) -> UsageEntry:
    """Records a single LLM usage event."""
    cost_rate = _COST_PER_1K_INPUT.get(model, _DEFAULT_COST_PER_1K)
    estimated_cost = ((tokens_in + tokens_out) / 1000) * cost_rate

    entry = UsageEntry(
        user_id=user_id,
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        estimated_cost=round(estimated_cost, 6),
    )

    with _lock:
        _usage_log.append(entry)
        if len(_usage_log) > 50_000:
            _usage_log.pop(0)

    try:
        from src.database.database import persist_usage_entry
        persist_usage_entry(user_id, model, tokens_in, tokens_out, entry.estimated_cost)
    except Exception as e:
        logger.warning("Failed to persist usage to DB: %s", e)

    return entry


def get_usage_summary(user_id: int | None = None) -> dict[str, Any]:
    """Returns aggregated usage stats, optionally filtered by user."""
    with _lock:
        entries = list(_usage_log)

    if user_id is not None:
        entries = [e for e in entries if e.user_id == user_id]

    total_in = sum(e.tokens_in for e in entries)
    total_out = sum(e.tokens_out for e in entries)
    total_cost = sum(e.estimated_cost for e in entries)

    by_model: dict[str, dict[str, Any]] = {}
    for e in entries:
        if e.model not in by_model:
            by_model[e.model] = {"requests": 0, "tokens_in": 0, "tokens_out": 0, "cost": 0.0}
        by_model[e.model]["requests"] += 1
        by_model[e.model]["tokens_in"] += e.tokens_in
        by_model[e.model]["tokens_out"] += e.tokens_out
        by_model[e.model]["cost"] += e.estimated_cost

    return {
        "total_requests": len(entries),
        "total_tokens_in": total_in,
        "total_tokens_out": total_out,
        "total_estimated_cost": round(total_cost, 4),
        "by_model": by_model,
    }


def get_recent_usage(limit: int = 50) -> list[dict[str, Any]]:
    """Returns most recent usage entries as dicts."""
    with _lock:
        recent = _usage_log[-limit:]
    return [
        {
            "user_id": e.user_id,
            "model": e.model,
            "tokens_in": e.tokens_in,
            "tokens_out": e.tokens_out,
            "estimated_cost": e.estimated_cost,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in reversed(recent)
    ]
