"""Tests for multi-tenancy: quotas, usage tracking, tenant context, RLS."""

from __future__ import annotations

import pytest

from src.services.tenant import (
    TIER_QUOTAS,
    Tenant,
    TenantContext,
    TenantManager,
    TenantQuota,
    TenantTier,
    get_tenant_manager,
)


class TestTenantQuotas:
    def test_tier_quotas_defined(self):
        assert TenantTier.FREE in TIER_QUOTAS
        assert TenantTier.STARTER in TIER_QUOTAS
        assert TenantTier.PROFESSIONAL in TIER_QUOTAS
        assert TenantTier.ENTERPRISE in TIER_QUOTAS

    def test_free_tier_most_restrictive(self):
        free = TIER_QUOTAS[TenantTier.FREE]
        enterprise = TIER_QUOTAS[TenantTier.ENTERPRISE]
        assert free.max_users < enterprise.max_users
        assert free.max_tokens_per_day < enterprise.max_tokens_per_day
        assert free.max_cost_per_day_usd < enterprise.max_cost_per_day_usd

    def test_tiers_are_ascending(self):
        tiers = [TenantTier.FREE, TenantTier.STARTER, TenantTier.PROFESSIONAL, TenantTier.ENTERPRISE]
        for i in range(len(tiers) - 1):
            lower = TIER_QUOTAS[tiers[i]]
            higher = TIER_QUOTAS[tiers[i + 1]]
            assert lower.max_tokens_per_day <= higher.max_tokens_per_day


class TestTenantManager:
    def test_check_quota_within_limits(self):
        mgr = TenantManager()
        ok, reason = mgr.check_quota(1, TenantTier.PROFESSIONAL, resource="tokens", amount=100)
        assert ok
        assert reason == ""

    def test_check_quota_exceeds_tokens(self):
        mgr = TenantManager()
        quota = TIER_QUOTAS[TenantTier.FREE]
        mgr.record_usage(1, tokens=quota.max_tokens_per_day)
        ok, reason = mgr.check_quota(1, TenantTier.FREE, resource="tokens", amount=1)
        assert not ok
        assert "quota exceeded" in reason.lower() or "Token" in reason

    def test_check_quota_exceeds_requests(self):
        mgr = TenantManager()
        quota = TIER_QUOTAS[TenantTier.FREE]
        mgr.record_usage(1, requests=quota.max_requests_per_hour)
        ok, reason = mgr.check_quota(1, TenantTier.FREE, resource="requests", amount=1)
        assert not ok

    def test_record_usage_accumulates(self):
        mgr = TenantManager()
        mgr.record_usage(1, tokens=100, requests=5, cost_usd=0.50)
        mgr.record_usage(1, tokens=200, requests=3, cost_usd=0.25)
        summary = mgr.get_usage_summary(1)
        assert summary["tokens_today"] == 300
        assert summary["requests_this_hour"] == 8
        assert summary["cost_today_usd"] == 0.75

    def test_separate_tenant_tracking(self):
        mgr = TenantManager()
        mgr.record_usage(1, tokens=100)
        mgr.record_usage(2, tokens=200)
        assert mgr.get_usage_summary(1)["tokens_today"] == 100
        assert mgr.get_usage_summary(2)["tokens_today"] == 200

    def test_storage_quota(self):
        mgr = TenantManager()
        quota = TIER_QUOTAS[TenantTier.FREE]
        mgr.record_usage(1, storage_mb=float(quota.max_storage_mb))
        ok, _ = mgr.check_quota(1, TenantTier.FREE, resource="storage", amount=1)
        assert not ok


class TestTenantContext:
    def test_set_and_get(self):
        TenantContext.set(42, TenantTier.PROFESSIONAL)
        assert TenantContext.get_id() == 42
        assert TenantContext.get_tier() == TenantTier.PROFESSIONAL

    def test_clear(self):
        TenantContext.set(42)
        TenantContext.clear()
        assert TenantContext.get_id() is None
        assert TenantContext.get_tier() == TenantTier.FREE

    def test_default_when_unset(self):
        TenantContext.clear()
        assert TenantContext.get_id() is None
        assert TenantContext.get_tier() == TenantTier.FREE


class TestTenantModel:
    def test_create_tenant(self):
        tenant = Tenant(
            id=1,
            name="Acme Corp",
            slug="acme-corp",
            tier=TenantTier.PROFESSIONAL,
        )
        assert tenant.name == "Acme Corp"
        assert tenant.is_active


class TestGetTenantManager:
    def test_singleton(self):
        mgr1 = get_tenant_manager()
        mgr2 = get_tenant_manager()
        assert mgr1 is mgr2
