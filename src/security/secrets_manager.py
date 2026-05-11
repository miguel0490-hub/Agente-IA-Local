"""Secrets management with Vault/Infisical integration and rotation support.

Provides a unified interface for secret retrieval that works with:
1. HashiCorp Vault (production)
2. Infisical (SaaS alternative)
3. Environment variables (development fallback)

Secrets are cached in memory with TTL and automatically rotated.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from src.core.logger import get_logger

logger = get_logger(__name__)


class SecretsBackend(Enum):
    ENV = "env"
    VAULT = "vault"
    INFISICAL = "infisical"


@dataclass
class SecretEntry:
    """Cached secret with metadata."""
    key: str
    value: str
    backend: SecretsBackend
    fetched_at: float = field(default_factory=time.monotonic)
    ttl: float = 300.0
    version: int = 0

    @property
    def is_expired(self) -> bool:
        return time.monotonic() - self.fetched_at > self.ttl


class SecretsManager:
    """Unified secrets manager with caching, rotation, and multi-backend support."""

    def __init__(
        self,
        backend: SecretsBackend | None = None,
        cache_ttl: float = 300.0,
    ) -> None:
        self._backend = backend or self._detect_backend()
        self._cache: dict[str, SecretEntry] = {}
        self._lock = threading.Lock()
        self._cache_ttl = cache_ttl
        self._rotation_callbacks: list[Callable[[str, str, str], None]] = []

        logger.info("Secrets manager initialized with backend: %s", self._backend.value)

    @staticmethod
    def _detect_backend() -> SecretsBackend:
        if os.getenv("VAULT_ADDR"):
            return SecretsBackend.VAULT
        if os.getenv("INFISICAL_TOKEN"):
            return SecretsBackend.INFISICAL
        return SecretsBackend.ENV

    def get_secret(self, key: str, *, default: str = "") -> str:
        """Retrieves a secret, using cache if available and not expired."""
        with self._lock:
            cached = self._cache.get(key)
            if cached and not cached.is_expired:
                return cached.value

        value = self._fetch_from_backend(key)
        if value is None:
            return default

        with self._lock:
            self._cache[key] = SecretEntry(
                key=key,
                value=value,
                backend=self._backend,
                ttl=self._cache_ttl,
            )
        return value

    def _fetch_from_backend(self, key: str) -> str | None:
        if self._backend == SecretsBackend.VAULT:
            return self._fetch_from_vault(key)
        elif self._backend == SecretsBackend.INFISICAL:
            return self._fetch_from_infisical(key)
        return self._fetch_from_env(key)

    def _fetch_from_env(self, key: str) -> str | None:
        return os.getenv(key) or os.getenv(key.upper())

    def _fetch_from_vault(self, key: str) -> str | None:
        """Fetches a secret from HashiCorp Vault KV v2."""
        vault_addr = os.getenv("VAULT_ADDR", "")
        vault_token = os.getenv("VAULT_TOKEN", "")
        vault_path = os.getenv("VAULT_SECRET_PATH", "secret/data/superagente")

        if not vault_addr or not vault_token:
            logger.warning("Vault configured but VAULT_ADDR/VAULT_TOKEN not set, falling back to env")
            return self._fetch_from_env(key)

        try:
            import httpx
            response = httpx.get(
                f"{vault_addr}/v1/{vault_path}",
                headers={"X-Vault-Token": vault_token},
                timeout=5.0,
            )
            if response.status_code == 200:
                data = response.json().get("data", {}).get("data", {})
                return data.get(key)
            logger.warning("Vault returned status %d for key %s", response.status_code, key)
        except Exception as exc:
            logger.error("Vault fetch failed for %s: %s", key, exc)

        return self._fetch_from_env(key)

    def _fetch_from_infisical(self, key: str) -> str | None:
        """Fetches a secret from Infisical."""
        token = os.getenv("INFISICAL_TOKEN", "")
        api_url = os.getenv("INFISICAL_API_URL", "https://app.infisical.com/api")
        project_id = os.getenv("INFISICAL_PROJECT_ID", "")
        environment = os.getenv("INFISICAL_ENV", "production")

        if not token or not project_id:
            return self._fetch_from_env(key)

        try:
            import httpx
            response = httpx.get(
                f"{api_url}/v3/secrets/raw/{key}",
                params={"workspaceId": project_id, "environment": environment},
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
            if response.status_code == 200:
                return response.json().get("secret", {}).get("secretValue")
        except Exception as exc:
            logger.error("Infisical fetch failed for %s: %s", key, exc)

        return self._fetch_from_env(key)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)

    def invalidate_all(self) -> None:
        with self._lock:
            self._cache.clear()

    def on_rotation(self, callback: Callable[[str, str, str], None]) -> None:
        """Registers a callback for secret rotation events.
        Callback receives (key, old_value, new_value)."""
        self._rotation_callbacks.append(callback)

    def rotate_secret(self, key: str) -> str | None:
        """Forces a secret refresh and notifies rotation callbacks."""
        with self._lock:
            old_entry = self._cache.pop(key, None)
        old_value = old_entry.value if old_entry else ""

        new_value = self._fetch_from_backend(key)
        if new_value is None:
            return None

        with self._lock:
            self._cache[key] = SecretEntry(
                key=key,
                value=new_value,
                backend=self._backend,
                ttl=self._cache_ttl,
                version=(old_entry.version + 1) if old_entry else 1,
            )

        if old_value and new_value != old_value:
            for cb in self._rotation_callbacks:
                try:
                    cb(key, old_value, new_value)
                except Exception as exc:
                    logger.error("Rotation callback failed for %s: %s", key, exc)

        return new_value

    def get_cache_stats(self) -> dict[str, Any]:
        with self._lock:
            total = len(self._cache)
            expired = sum(1 for e in self._cache.values() if e.is_expired)
        return {"total_cached": total, "expired": expired, "backend": self._backend.value}


_default_manager: SecretsManager | None = None
_init_lock = threading.Lock()


def get_secrets_manager() -> SecretsManager:
    """Returns the singleton SecretsManager instance."""
    global _default_manager
    if _default_manager is None:
        with _init_lock:
            if _default_manager is None:
                _default_manager = SecretsManager()
    return _default_manager
