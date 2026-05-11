"""Tool authorization guardrails with RBAC for LLM tool calls."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ToolDecision:
    """Decision result for a tool call."""

    allowed: bool
    requires_confirmation: bool = False
    reason: str = ""


# Role-based permission tiers
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": frozenset({
        "create_file", "edit_file", "execute_code", "search_web",
        "open_converter", "generate_image", "respond", "query_rag",
    }),
    "user": frozenset({
        "create_file", "edit_file", "execute_code", "search_web",
        "open_converter", "generate_image", "respond", "query_rag",
    }),
    "restricted": frozenset({
        "search_web", "respond",
    }),
}

_CUSTOM_PERMISSIONS_ENV = "TOOL_PERMISSIONS_RESTRICTED"


class ToolGuard:
    """Central policy for tool access with role-based authorization."""

    SENSITIVE_ACTIONS = {"execute_code", "open_converter"}
    HARD_BLOCKED_ACTIONS = {"shell", "filesystem", "delete_file", "run_system_command"}

    @classmethod
    def evaluate(cls, action: str, *, role: str = "user") -> ToolDecision:
        """Evaluates whether a tool action is allowed for a given role."""
        if action in cls.HARD_BLOCKED_ACTIONS:
            logger.warning("Tool blocked by hard policy: %s (role=%s)", action, role)
            return ToolDecision(allowed=False, reason="blocked_by_policy")

        permissions = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["restricted"])
        if action not in permissions:
            logger.info("Tool denied by RBAC: %s not in role '%s'", action, role)
            return ToolDecision(allowed=False, reason=f"not_permitted_for_role_{role}")

        if action in cls.SENSITIVE_ACTIONS:
            return ToolDecision(allowed=True, requires_confirmation=True, reason="explicit_user_confirmation_required")

        return ToolDecision(allowed=True)

    @staticmethod
    def has_explicit_approval(user_text: str, action: str) -> bool:
        marker = f"[approve:{action}]"
        return marker.lower() in (user_text or "").lower()


_tool_audit_log: list[dict[str, Any]] = []


def log_tool_execution(
    user_id: int,
    action: str,
    role: str,
    allowed: bool,
    *,
    details: str = "",
) -> None:
    """Records a tool execution attempt for audit trail."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "action": action,
        "role": role,
        "allowed": allowed,
        "details": details,
    }
    _tool_audit_log.append(entry)
    if len(_tool_audit_log) > 10_000:
        _tool_audit_log.pop(0)
    logger.info("Tool audit: user=%s action=%s role=%s allowed=%s", user_id, action, role, allowed)


def get_audit_log() -> list[dict[str, Any]]:
    """Returns the in-memory tool audit log."""
    return list(_tool_audit_log)
