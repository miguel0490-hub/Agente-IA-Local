"""Zero Trust Architecture: internal service authentication and authorization.

Implements JWT-based service identity, internal RBAC policy engine,
and service-to-service authentication for microservice communication.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.core.logger import get_logger

logger = get_logger(__name__)

_SERVICE_SECRET = os.getenv("SERVICE_JWT_SECRET", "")
_TOKEN_TTL = int(os.getenv("SERVICE_TOKEN_TTL", "3600"))


class ServiceRole(Enum):
    """Internal service identity roles."""
    GATEWAY = "gateway"
    WORKER = "worker"
    MONITORING = "monitoring"
    SANDBOX = "sandbox"
    SCHEDULER = "scheduler"


@dataclass(frozen=True)
class ServiceIdentity:
    """Authenticated service identity."""
    service_name: str
    role: ServiceRole
    instance_id: str = ""
    issued_at: float = 0.0
    expires_at: float = 0.0


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str = ""


_INTERNAL_RBAC: dict[ServiceRole, frozenset[str]] = {
    ServiceRole.GATEWAY: frozenset({
        "read:users", "read:chats", "write:chats", "read:config",
        "execute:tools", "read:health", "read:metrics",
    }),
    ServiceRole.WORKER: frozenset({
        "read:users", "read:chats", "write:chats",
        "execute:tools", "execute:sandbox", "write:files",
    }),
    ServiceRole.MONITORING: frozenset({
        "read:health", "read:metrics", "read:logs", "read:audit",
    }),
    ServiceRole.SANDBOX: frozenset({
        "execute:sandbox", "read:workspace", "write:workspace",
    }),
    ServiceRole.SCHEDULER: frozenset({
        "read:config", "execute:maintenance", "read:metrics",
    }),
}


def _get_secret() -> bytes:
    """Returns the signing secret, falling back to APP_SECRET_KEY."""
    secret = _SERVICE_SECRET or os.getenv("APP_SECRET_KEY", "")
    if not secret:
        logger.warning("No SERVICE_JWT_SECRET or APP_SECRET_KEY set; using insecure default")
        secret = "insecure-dev-only-default"
    return secret.encode("utf-8")


def _b64url_encode(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    import base64
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_service_token(
    service_name: str,
    role: ServiceRole,
    *,
    instance_id: str = "",
    ttl: int | None = None,
) -> str:
    """Creates a signed JWT for service-to-service authentication.

    Uses HMAC-SHA256 for signing. Tokens include service identity,
    role, and expiration.
    """
    now = time.time()
    payload = {
        "sub": service_name,
        "role": role.value,
        "inst": instance_id,
        "iat": int(now),
        "exp": int(now + (ttl or _TOKEN_TTL)),
    }

    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64url_encode(json.dumps(payload).encode())
    signature = hmac.new(_get_secret(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    sig_str = _b64url_encode(signature)

    return f"{header}.{body}.{sig_str}"


def verify_service_token(token: str) -> ServiceIdentity | None:
    """Verifies a service JWT and returns the identity if valid."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, body_b64, sig_b64 = parts

        expected_sig = hmac.new(
            _get_secret(), f"{header_b64}.{body_b64}".encode(), hashlib.sha256
        ).digest()
        actual_sig = _b64url_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            logger.warning("Service token signature mismatch")
            return None

        payload = json.loads(_b64url_decode(body_b64))

        if payload.get("exp", 0) < time.time():
            logger.info("Service token expired for %s", payload.get("sub"))
            return None

        role_str = payload.get("role", "")
        try:
            role = ServiceRole(role_str)
        except ValueError:
            logger.warning("Unknown service role: %s", role_str)
            return None

        return ServiceIdentity(
            service_name=payload["sub"],
            role=role,
            instance_id=payload.get("inst", ""),
            issued_at=payload.get("iat", 0),
            expires_at=payload.get("exp", 0),
        )
    except Exception as exc:
        logger.warning("Failed to verify service token: %s", exc)
        return None


def authorize_action(identity: ServiceIdentity, action: str) -> AuthorizationDecision:
    """Checks if a service identity is authorized for an action."""
    permissions = _INTERNAL_RBAC.get(identity.role, frozenset())
    if action in permissions:
        return AuthorizationDecision(allowed=True)

    logger.info(
        "Authorization denied: service=%s role=%s action=%s",
        identity.service_name, identity.role.value, action,
    )
    return AuthorizationDecision(
        allowed=False,
        reason=f"Service '{identity.service_name}' (role={identity.role.value}) "
               f"not authorized for '{action}'",
    )


def require_service_auth(token: str, required_action: str) -> ServiceIdentity:
    """Verifies token and authorizes action. Raises ValueError on failure."""
    identity = verify_service_token(token)
    if not identity:
        raise ValueError("Invalid or expired service token")

    decision = authorize_action(identity, required_action)
    if not decision.allowed:
        raise PermissionError(decision.reason)

    return identity


class ServiceAllowlist:
    """Network-level service allowlist for deny-by-default internal routing."""

    def __init__(self) -> None:
        self._rules: dict[str, frozenset[str]] = {
            "app": frozenset({"postgres", "redis", "monitoring"}),
            "worker": frozenset({"postgres", "redis"}),
            "monitoring": frozenset({"app", "worker", "postgres", "redis"}),
            "nginx": frozenset({"app", "monitoring"}),
            "sandbox": frozenset(),
        }

    def can_connect(self, source: str, target: str) -> bool:
        allowed = self._rules.get(source, frozenset())
        return target in allowed

    def add_rule(self, source: str, target: str) -> None:
        current = set(self._rules.get(source, frozenset()))
        current.add(target)
        self._rules[source] = frozenset(current)

    def get_rules(self) -> dict[str, list[str]]:
        return {k: sorted(v) for k, v in self._rules.items()}


service_allowlist = ServiceAllowlist()
