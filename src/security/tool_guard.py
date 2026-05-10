"""Tool authorization guardrails for LLM tool calls."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolDecision:
    """Decision result for a tool call."""

    allowed: bool
    requires_confirmation: bool = False
    reason: str = ""


class ToolGuard:
    """Central policy for tool access."""

    SENSITIVE_ACTIONS = {"execute_code", "open_converter"}
    HARD_BLOCKED_ACTIONS = {"shell", "filesystem", "delete_file", "run_system_command"}

    @classmethod
    def evaluate(cls, action: str) -> ToolDecision:
        """Evaluates whether a tool action is allowed."""
        if action in cls.HARD_BLOCKED_ACTIONS:
            return ToolDecision(allowed=False, reason="blocked_by_policy")
        if action in cls.SENSITIVE_ACTIONS:
            return ToolDecision(allowed=True, requires_confirmation=True, reason="explicit_user_confirmation_required")
        return ToolDecision(allowed=True)

    @staticmethod
    def has_explicit_approval(user_text: str, action: str) -> bool:
        """
        Checks for explicit user approval markers.

        Expected markers:
        - [approve:execute_code]
        - [approve:open_converter]
        """
        marker = f"[approve:{action}]"
        return marker.lower() in (user_text or "").lower()
