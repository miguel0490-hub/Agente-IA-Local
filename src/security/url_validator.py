"""SSRF protection: validates URLs before they reach HTTP clients.

Blocks requests to private IP ranges, loopback addresses, link-local,
cloud metadata endpoints, and optionally enforces a domain allowlist.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

from src.core.logger import get_logger

logger = get_logger(__name__)

_BLOCKED_HOSTNAMES = frozenset({
    "metadata.google.internal",
    "metadata.goog",
    "169.254.169.254",
    "fd00:ec2::254",
})

_BLOCKED_PORTS = frozenset({
    25, 110, 143, 445, 3306, 5432, 6379, 27017,
})


@dataclass(frozen=True)
class URLValidationResult:
    safe: bool
    reason: str = ""


def _is_private_ip(addr: str) -> bool:
    """Returns True if addr resolves to a private, loopback, or link-local IP."""
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _resolve_hostname(hostname: str) -> list[str]:
    """DNS resolution with timeout to prevent hanging on crafted hostnames."""
    try:
        socket.setdefaulttimeout(3.0)
        results = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        return list({r[4][0] for r in results})
    except (socket.gaierror, socket.timeout, OSError):
        return []


def _get_allowed_domains() -> frozenset[str] | None:
    raw = (os.getenv("ALLOWED_LLM_DOMAINS") or "").strip()
    if not raw:
        return None
    return frozenset(d.strip().lower() for d in raw.split(",") if d.strip())


def validate_url(url: str, *, context: str = "generic") -> URLValidationResult:
    """Validates a URL against SSRF vectors.

    Args:
        url: The URL to validate.
        context: Description for logging (e.g. 'custom_model_base_url').

    Returns:
        URLValidationResult with safe=True if the URL passes all checks.
    """
    if not url or not isinstance(url, str):
        return URLValidationResult(safe=False, reason="URL vacía o inválida.")

    try:
        parsed = urlparse(url.strip())
    except Exception:
        return URLValidationResult(safe=False, reason="URL malformada.")

    if parsed.scheme not in ("http", "https"):
        return URLValidationResult(
            safe=False,
            reason=f"Esquema '{parsed.scheme}' no permitido. Solo http/https.",
        )

    hostname = (parsed.hostname or "").lower().strip()
    if not hostname:
        return URLValidationResult(safe=False, reason="URL sin hostname.")

    port = parsed.port
    if port and port in _BLOCKED_PORTS:
        return URLValidationResult(
            safe=False,
            reason=f"Puerto {port} bloqueado por política de seguridad.",
        )

    if hostname in _BLOCKED_HOSTNAMES:
        logger.warning("SSRF blocked [%s]: metadata hostname %s", context, hostname)
        return URLValidationResult(
            safe=False,
            reason="Hostname bloqueado: endpoint de metadata cloud.",
        )

    allowlist = _get_allowed_domains()
    if allowlist is not None:
        if hostname not in allowlist and not any(
            hostname.endswith(f".{d}") for d in allowlist
        ):
            return URLValidationResult(
                safe=False,
                reason=f"Dominio '{hostname}' no está en la allowlist.",
            )

    if _is_private_ip(hostname):
        logger.warning("SSRF blocked [%s]: private IP literal %s", context, hostname)
        return URLValidationResult(
            safe=False,
            reason="Dirección IP privada/loopback no permitida.",
        )

    resolved_ips = _resolve_hostname(hostname)
    if not resolved_ips:
        return URLValidationResult(
            safe=False,
            reason=f"No se pudo resolver DNS para '{hostname}'.",
        )

    for ip_str in resolved_ips:
        if _is_private_ip(ip_str):
            logger.warning(
                "SSRF blocked [%s]: hostname %s resolves to private IP %s",
                context, hostname, ip_str,
            )
            return URLValidationResult(
                safe=False,
                reason=f"'{hostname}' resuelve a IP privada ({ip_str}).",
            )

    return URLValidationResult(safe=True)


def assert_url_safe(url: str, *, context: str = "generic") -> None:
    """Raises ValueError if URL fails SSRF validation."""
    result = validate_url(url, context=context)
    if not result.safe:
        raise ValueError(f"URL bloqueada ({context}): {result.reason}")
