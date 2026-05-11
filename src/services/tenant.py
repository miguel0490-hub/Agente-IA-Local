"""Multi-tenant architecture: tenant isolation, quotas, and governance.

Provides tenant-aware data access, row-level security enforcement,
resource quotas, usage metering, and tenant administration.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from sqlalchemy import text

from src.core.logger import get_logger
from src.database.database import engine

logger = get_logger(__name__)


class TenantTier(Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


@dataclass
class TenantQuota:
    """Resource quotas per billing tier."""
    max_users: int = 5
    max_chats_per_user: int = 50
    max_messages_per_chat: int = 200
    max_tokens_per_day: int = 100_000
    max_requests_per_hour: int = 100
    max_storage_mb: int = 500
    max_tools_enabled: int = 5
    max_cost_per_day_usd: float = 5.0


TIER_QUOTAS: dict[TenantTier, TenantQuota] = {
    TenantTier.FREE: TenantQuota(
        max_users=3, max_chats_per_user=10, max_tokens_per_day=10_000,
        max_requests_per_hour=20, max_storage_mb=100, max_cost_per_day_usd=1.0,
    ),
    TenantTier.STARTER: TenantQuota(
        max_users=10, max_chats_per_user=50, max_tokens_per_day=100_000,
        max_requests_per_hour=200, max_storage_mb=1_000, max_cost_per_day_usd=10.0,
    ),
    TenantTier.PROFESSIONAL: TenantQuota(
        max_users=50, max_chats_per_user=200, max_tokens_per_day=1_000_000,
        max_requests_per_hour=1_000, max_storage_mb=10_000, max_cost_per_day_usd=100.0,
    ),
    TenantTier.ENTERPRISE: TenantQuota(
        max_users=10_000, max_chats_per_user=10_000, max_tokens_per_day=100_000_000,
        max_requests_per_hour=100_000, max_storage_mb=1_000_000, max_cost_per_day_usd=10_000.0,
    ),
}


@dataclass
class Tenant:
    """Tenant record."""
    id: int
    name: str
    slug: str
    tier: TenantTier
    is_active: bool = True
    created_at: datetime | None = None
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageMeter:
    """Tracks resource usage for quota enforcement and billing."""
    tenant_id: int
    tokens_today: int = 0
    requests_this_hour: int = 0
    storage_mb: float = 0.0
    cost_today_usd: float = 0.0
    last_reset_date: str = ""
    last_reset_hour: int = -1


class TenantManager:
    """Manages tenant lifecycle, quotas, and usage tracking."""

    def __init__(self) -> None:
        self._usage: dict[int, UsageMeter] = {}
        self._lock = threading.Lock()

    def get_tenant_quota(self, tier: TenantTier) -> TenantQuota:
        return TIER_QUOTAS.get(tier, TIER_QUOTAS[TenantTier.FREE])

    def check_quota(
        self,
        tenant_id: int,
        tier: TenantTier,
        *,
        resource: str,
        amount: int = 1,
    ) -> tuple[bool, str]:
        """Checks if a tenant has quota remaining for a resource.

        Returns:
            (allowed, reason) tuple.
        """
        quota = self.get_tenant_quota(tier)
        meter = self._get_or_create_meter(tenant_id)
        self._maybe_reset(meter)

        if resource == "tokens":
            if meter.tokens_today + amount > quota.max_tokens_per_day:
                return False, f"Token quota exceeded ({meter.tokens_today}/{quota.max_tokens_per_day})"
        elif resource == "requests":
            if meter.requests_this_hour + amount > quota.max_requests_per_hour:
                return False, f"Request rate exceeded ({meter.requests_this_hour}/{quota.max_requests_per_hour})"
        elif resource == "cost":
            cost_amount = amount / 100.0
            if meter.cost_today_usd + cost_amount > quota.max_cost_per_day_usd:
                return False, f"Cost limit exceeded (${meter.cost_today_usd:.2f}/${quota.max_cost_per_day_usd})"
        elif resource == "storage":
            if meter.storage_mb + amount > quota.max_storage_mb:
                return False, f"Storage limit exceeded ({meter.storage_mb:.1f}/{quota.max_storage_mb}MB)"

        return True, ""

    def record_usage(
        self,
        tenant_id: int,
        *,
        tokens: int = 0,
        requests: int = 0,
        cost_usd: float = 0.0,
        storage_mb: float = 0.0,
    ) -> None:
        """Records resource usage for a tenant."""
        meter = self._get_or_create_meter(tenant_id)
        self._maybe_reset(meter)

        with self._lock:
            meter.tokens_today += tokens
            meter.requests_this_hour += requests
            meter.cost_today_usd += cost_usd
            meter.storage_mb += storage_mb

    def get_usage_summary(self, tenant_id: int) -> dict[str, Any]:
        meter = self._get_or_create_meter(tenant_id)
        return {
            "tenant_id": tenant_id,
            "tokens_today": meter.tokens_today,
            "requests_this_hour": meter.requests_this_hour,
            "cost_today_usd": round(meter.cost_today_usd, 4),
            "storage_mb": round(meter.storage_mb, 2),
        }

    def _get_or_create_meter(self, tenant_id: int) -> UsageMeter:
        with self._lock:
            if tenant_id not in self._usage:
                self._usage[tenant_id] = UsageMeter(tenant_id=tenant_id)
            return self._usage[tenant_id]

    def _maybe_reset(self, meter: UsageMeter) -> None:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        current_hour = now.hour

        if meter.last_reset_date != today:
            meter.tokens_today = 0
            meter.cost_today_usd = 0.0
            meter.last_reset_date = today
            meter.last_reset_hour = current_hour
            meter.requests_this_hour = 0
        elif meter.last_reset_hour != current_hour:
            meter.requests_this_hour = 0
            meter.last_reset_hour = current_hour


class TenantContext:
    """Thread-local tenant context for request scoping."""

    _local = threading.local()

    @classmethod
    def set(cls, tenant_id: int, tier: TenantTier = TenantTier.FREE) -> None:
        cls._local.tenant_id = tenant_id
        cls._local.tier = tier

    @classmethod
    def get_id(cls) -> int | None:
        return getattr(cls._local, "tenant_id", None)

    @classmethod
    def get_tier(cls) -> TenantTier:
        return getattr(cls._local, "tier", TenantTier.FREE)

    @classmethod
    def clear(cls) -> None:
        cls._local.tenant_id = None
        cls._local.tier = TenantTier.FREE


def setup_rls_policies() -> None:
    """Sets up PostgreSQL Row-Level Security policies for tenant isolation.

    Only runs on PostgreSQL; silently skips on SQLite.
    """
    if engine.dialect.name != "postgresql":
        logger.info("RLS setup skipped (not PostgreSQL)")
        return

    rls_statements = [
        "ALTER TABLE users ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE chats ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE messages ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE contact_messages ENABLE ROW LEVEL SECURITY",

        """CREATE POLICY IF NOT EXISTS tenant_users_policy ON users
           USING (tenant_id = current_setting('app.current_tenant_id', true)::int)""",
        """CREATE POLICY IF NOT EXISTS tenant_chats_policy ON chats
           USING (user_id IN (
               SELECT id FROM users WHERE tenant_id = current_setting('app.current_tenant_id', true)::int
           ))""",
    ]

    try:
        with engine.begin() as conn:
            # Check if tenant_id column exists before applying RLS
            result = conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'tenant_id'"
            ))
            if not result.fetchone():
                logger.info("tenant_id column not found, adding it first")
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS tenant_id INTEGER DEFAULT 1"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_tenant ON users (tenant_id)"))

            for stmt in rls_statements:
                try:
                    conn.execute(text(stmt))
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning("RLS statement failed: %s — %s", stmt[:60], e)

        logger.info("RLS policies applied successfully")
    except Exception as exc:
        logger.error("RLS setup failed: %s", exc)


_tenant_manager: TenantManager | None = None


def get_tenant_manager() -> TenantManager:
    global _tenant_manager
    if _tenant_manager is None:
        _tenant_manager = TenantManager()
    return _tenant_manager
