"""Centralized policy engine for security governance.

Evaluates requests against configurable policies covering authentication,
authorization, rate limiting, content security, and operational constraints.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.core.logger import get_logger

logger = get_logger(__name__)


class PolicyAction(Enum):
    ALLOW = "allow"
    DENY = "deny"
    AUDIT = "audit"
    REQUIRE_MFA = "require_mfa"
    REQUIRE_APPROVAL = "require_approval"


class PolicyCategory(Enum):
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    CONTENT = "content"
    NETWORK = "network"
    RESOURCE = "resource"
    DATA = "data"


@dataclass(frozen=True)
class PolicyRule:
    """A single policy rule with conditions and actions."""
    name: str
    category: PolicyCategory
    action: PolicyAction
    conditions: dict[str, Any] = field(default_factory=dict)
    priority: int = 100
    enabled: bool = True
    description: str = ""


@dataclass(frozen=True)
class PolicyDecision:
    """Result of policy evaluation."""
    action: PolicyAction
    rule_name: str
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class PolicyEngine:
    """Evaluates requests against registered security policies."""

    def __init__(self) -> None:
        self._rules: list[PolicyRule] = []
        self._load_default_rules()

    def _load_default_rules(self) -> None:
        """Loads built-in security policies."""
        self._rules = [
            PolicyRule(
                name="block_admin_api_from_user",
                category=PolicyCategory.AUTHORIZATION,
                action=PolicyAction.DENY,
                conditions={"role": "user", "resource_pattern": r"^/admin/"},
                priority=10,
                description="Non-admin users cannot access admin endpoints",
            ),
            PolicyRule(
                name="require_approval_for_code_execution",
                category=PolicyCategory.AUTHORIZATION,
                action=PolicyAction.REQUIRE_APPROVAL,
                conditions={"action": "execute_code"},
                priority=20,
                description="Code execution requires explicit user approval",
            ),
            PolicyRule(
                name="deny_dangerous_tools",
                category=PolicyCategory.AUTHORIZATION,
                action=PolicyAction.DENY,
                conditions={"action_in": ["shell", "filesystem", "delete_file", "run_system_command"]},
                priority=5,
                description="Dangerous system tools are always blocked",
            ),
            PolicyRule(
                name="block_private_network_access",
                category=PolicyCategory.NETWORK,
                action=PolicyAction.DENY,
                conditions={"target_is_private": True},
                priority=10,
                description="Block access to private/internal networks (SSRF)",
            ),
            PolicyRule(
                name="limit_file_upload_size",
                category=PolicyCategory.RESOURCE,
                action=PolicyAction.DENY,
                conditions={"file_size_exceeds_mb": 100},
                priority=50,
                description="Block file uploads exceeding 100MB",
            ),
            PolicyRule(
                name="block_pii_in_logs",
                category=PolicyCategory.DATA,
                action=PolicyAction.AUDIT,
                conditions={"contains_pii": True},
                priority=30,
                description="Audit when PII is detected in data flows",
            ),
            PolicyRule(
                name="require_mfa_for_admin_actions",
                category=PolicyCategory.AUTHENTICATION,
                action=PolicyAction.REQUIRE_MFA,
                conditions={"role": "admin", "action_pattern": r"^admin\.(delete|reset|promote)"},
                priority=15,
                description="Admin destructive actions require MFA",
            ),
            PolicyRule(
                name="deny_prompt_injection",
                category=PolicyCategory.CONTENT,
                action=PolicyAction.DENY,
                conditions={"prompt_risk_score_above": 50},
                priority=10,
                description="Block high-risk prompt injection attempts",
            ),
        ]

    def evaluate(self, context: dict[str, Any]) -> PolicyDecision:
        """Evaluates a request context against all enabled rules.

        Args:
            context: Dict with keys like 'role', 'action', 'resource',
                     'file_size_mb', 'prompt_risk_score', 'target_is_private', etc.

        Returns:
            The highest-priority matching PolicyDecision.
        """
        sorted_rules = sorted(
            (r for r in self._rules if r.enabled),
            key=lambda r: r.priority,
        )

        for rule in sorted_rules:
            if self._matches(rule, context):
                decision = PolicyDecision(
                    action=rule.action,
                    rule_name=rule.name,
                    reason=rule.description,
                )
                if rule.action == PolicyAction.DENY:
                    logger.warning(
                        "Policy DENY: rule=%s context=%s",
                        rule.name,
                        {k: v for k, v in context.items() if k != "content"},
                    )
                return decision

        return PolicyDecision(action=PolicyAction.ALLOW, rule_name="default_allow")

    def _matches(self, rule: PolicyRule, context: dict[str, Any]) -> bool:
        """Checks if a rule's conditions match the request context."""
        for cond_key, cond_value in rule.conditions.items():
            if cond_key == "role" and context.get("role") != cond_value:
                return False
            elif cond_key == "action" and context.get("action") != cond_value:
                return False
            elif cond_key == "action_in" and context.get("action") not in cond_value:
                return False
            elif cond_key == "resource_pattern":
                resource = context.get("resource", "")
                if not re.search(cond_value, resource):
                    return False
            elif cond_key == "action_pattern":
                action = context.get("action", "")
                if not re.search(cond_value, action):
                    return False
            elif cond_key == "target_is_private" and not context.get("target_is_private"):
                return False
            elif cond_key == "file_size_exceeds_mb":
                if context.get("file_size_mb", 0) <= cond_value:
                    return False
            elif cond_key == "contains_pii" and not context.get("contains_pii"):
                return False
            elif cond_key == "prompt_risk_score_above":
                if context.get("prompt_risk_score", 0) <= cond_value:
                    return False
        return True

    def add_rule(self, rule: PolicyRule) -> None:
        self._rules.append(rule)
        logger.info("Policy rule added: %s (priority=%d)", rule.name, rule.priority)

    def remove_rule(self, name: str) -> bool:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        return len(self._rules) < before

    def get_rules(self, category: PolicyCategory | None = None) -> list[PolicyRule]:
        if category:
            return [r for r in self._rules if r.category == category]
        return list(self._rules)

    def get_rule_summary(self) -> list[dict[str, Any]]:
        return [
            {
                "name": r.name,
                "category": r.category.value,
                "action": r.action.value,
                "priority": r.priority,
                "enabled": r.enabled,
                "description": r.description,
            }
            for r in sorted(self._rules, key=lambda r: r.priority)
        ]


_engine: PolicyEngine | None = None


def get_policy_engine() -> PolicyEngine:
    global _engine
    if _engine is None:
        _engine = PolicyEngine()
    return _engine
