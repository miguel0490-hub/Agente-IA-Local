"""Tests for Zero Trust architecture: service auth, policy engine, secrets, allowlist."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from src.security.zero_trust import (
    AuthorizationDecision,
    ServiceAllowlist,
    ServiceIdentity,
    ServiceRole,
    authorize_action,
    create_service_token,
    require_service_auth,
    verify_service_token,
)
from src.security.policy_engine import (
    PolicyAction,
    PolicyCategory,
    PolicyDecision,
    PolicyEngine,
    PolicyRule,
    get_policy_engine,
)
from src.security.secrets_manager import (
    SecretsBackend,
    SecretsManager,
)


class TestServiceTokens:
    def test_create_and_verify_token(self):
        token = create_service_token("test-app", ServiceRole.GATEWAY)
        identity = verify_service_token(token)
        assert identity is not None
        assert identity.service_name == "test-app"
        assert identity.role == ServiceRole.GATEWAY

    def test_token_with_instance_id(self):
        token = create_service_token("worker", ServiceRole.WORKER, instance_id="pod-abc123")
        identity = verify_service_token(token)
        assert identity.instance_id == "pod-abc123"

    def test_expired_token_rejected(self):
        token = create_service_token("svc", ServiceRole.MONITORING, ttl=-1)
        identity = verify_service_token(token)
        assert identity is None

    def test_tampered_token_rejected(self):
        token = create_service_token("svc", ServiceRole.GATEWAY)
        parts = token.split(".")
        parts[1] = parts[1][::-1]
        tampered = ".".join(parts)
        assert verify_service_token(tampered) is None

    def test_invalid_format_rejected(self):
        assert verify_service_token("not.a.valid.token") is None
        assert verify_service_token("") is None
        assert verify_service_token("abc") is None

    def test_custom_ttl(self):
        token = create_service_token("svc", ServiceRole.SANDBOX, ttl=10)
        identity = verify_service_token(token)
        assert identity is not None
        assert identity.expires_at > identity.issued_at


class TestServiceAuthorization:
    def test_gateway_can_read_users(self):
        identity = ServiceIdentity(
            service_name="gateway",
            role=ServiceRole.GATEWAY,
        )
        decision = authorize_action(identity, "read:users")
        assert decision.allowed

    def test_sandbox_cannot_read_users(self):
        identity = ServiceIdentity(
            service_name="sandbox",
            role=ServiceRole.SANDBOX,
        )
        decision = authorize_action(identity, "read:users")
        assert not decision.allowed

    def test_worker_can_execute_sandbox(self):
        identity = ServiceIdentity(
            service_name="worker",
            role=ServiceRole.WORKER,
        )
        decision = authorize_action(identity, "execute:sandbox")
        assert decision.allowed

    def test_monitoring_read_only(self):
        identity = ServiceIdentity(
            service_name="monitoring",
            role=ServiceRole.MONITORING,
        )
        assert authorize_action(identity, "read:metrics").allowed
        assert not authorize_action(identity, "write:chats").allowed
        assert not authorize_action(identity, "execute:tools").allowed


class TestRequireServiceAuth:
    def test_valid_token_and_action(self):
        token = create_service_token("gateway", ServiceRole.GATEWAY)
        identity = require_service_auth(token, "read:users")
        assert identity.service_name == "gateway"

    def test_invalid_token_raises(self):
        with pytest.raises(ValueError, match="Invalid"):
            require_service_auth("bad-token", "read:users")

    def test_unauthorized_action_raises(self):
        token = create_service_token("sandbox", ServiceRole.SANDBOX)
        with pytest.raises(PermissionError):
            require_service_auth(token, "read:users")


class TestServiceAllowlist:
    def test_app_can_reach_postgres(self):
        allowlist = ServiceAllowlist()
        assert allowlist.can_connect("app", "postgres")

    def test_app_can_reach_redis(self):
        allowlist = ServiceAllowlist()
        assert allowlist.can_connect("app", "redis")

    def test_sandbox_is_isolated(self):
        allowlist = ServiceAllowlist()
        assert not allowlist.can_connect("sandbox", "postgres")
        assert not allowlist.can_connect("sandbox", "redis")
        assert not allowlist.can_connect("sandbox", "app")

    def test_nginx_can_reach_app(self):
        allowlist = ServiceAllowlist()
        assert allowlist.can_connect("nginx", "app")
        assert not allowlist.can_connect("nginx", "postgres")

    def test_add_rule(self):
        allowlist = ServiceAllowlist()
        assert not allowlist.can_connect("sandbox", "app")
        allowlist.add_rule("sandbox", "app")
        assert allowlist.can_connect("sandbox", "app")

    def test_unknown_source_denied(self):
        allowlist = ServiceAllowlist()
        assert not allowlist.can_connect("unknown", "postgres")


class TestPolicyEngine:
    def test_deny_dangerous_tools(self):
        engine = PolicyEngine()
        decision = engine.evaluate({"action": "shell"})
        assert decision.action == PolicyAction.DENY

    def test_allow_normal_action(self):
        engine = PolicyEngine()
        decision = engine.evaluate({"action": "respond", "role": "user"})
        assert decision.action == PolicyAction.ALLOW

    def test_require_approval_for_code(self):
        engine = PolicyEngine()
        decision = engine.evaluate({"action": "execute_code"})
        assert decision.action == PolicyAction.REQUIRE_APPROVAL

    def test_block_admin_endpoint_for_user(self):
        engine = PolicyEngine()
        decision = engine.evaluate({"role": "user", "resource": "/admin/delete"})
        assert decision.action == PolicyAction.DENY

    def test_allow_admin_endpoint_for_admin(self):
        engine = PolicyEngine()
        decision = engine.evaluate({"role": "admin", "resource": "/admin/delete"})
        assert decision.action != PolicyAction.DENY or decision.rule_name != "block_admin_api_from_user"

    def test_block_private_network(self):
        engine = PolicyEngine()
        decision = engine.evaluate({"target_is_private": True})
        assert decision.action == PolicyAction.DENY

    def test_block_high_risk_prompt(self):
        engine = PolicyEngine()
        decision = engine.evaluate({"prompt_risk_score": 80})
        assert decision.action == PolicyAction.DENY

    def test_allow_low_risk_prompt(self):
        engine = PolicyEngine()
        decision = engine.evaluate({"prompt_risk_score": 10})
        assert decision.action == PolicyAction.ALLOW

    def test_block_oversized_upload(self):
        engine = PolicyEngine()
        decision = engine.evaluate({"file_size_mb": 150})
        assert decision.action == PolicyAction.DENY

    def test_add_custom_rule(self):
        engine = PolicyEngine()
        rule = PolicyRule(
            name="custom_deny_test",
            category=PolicyCategory.AUTHORIZATION,
            action=PolicyAction.DENY,
            conditions={"action": "custom_action"},
            priority=1,
        )
        engine.add_rule(rule)
        decision = engine.evaluate({"action": "custom_action"})
        assert decision.action == PolicyAction.DENY
        assert decision.rule_name == "custom_deny_test"

    def test_remove_rule(self):
        engine = PolicyEngine()
        assert engine.remove_rule("block_admin_api_from_user")
        decision = engine.evaluate({"role": "user", "resource": "/admin/delete"})
        assert decision.rule_name != "block_admin_api_from_user"

    def test_get_rule_summary(self):
        engine = PolicyEngine()
        summary = engine.get_rule_summary()
        assert len(summary) > 0
        assert all("name" in r and "action" in r for r in summary)


class TestSecretsManager:
    def test_env_backend(self):
        manager = SecretsManager(backend=SecretsBackend.ENV)
        with patch.dict("os.environ", {"TEST_SECRET": "my-value"}):
            assert manager.get_secret("TEST_SECRET") == "my-value"

    def test_default_on_missing(self):
        manager = SecretsManager(backend=SecretsBackend.ENV)
        result = manager.get_secret("NONEXISTENT_KEY_12345", default="fallback")
        assert result == "fallback"

    def test_caching(self):
        manager = SecretsManager(backend=SecretsBackend.ENV, cache_ttl=60.0)
        with patch.dict("os.environ", {"CACHED_KEY": "v1"}):
            assert manager.get_secret("CACHED_KEY") == "v1"
        with patch.dict("os.environ", {"CACHED_KEY": "v2"}):
            assert manager.get_secret("CACHED_KEY") == "v1"  # still cached

    def test_invalidate(self):
        manager = SecretsManager(backend=SecretsBackend.ENV, cache_ttl=60.0)
        with patch.dict("os.environ", {"INV_KEY": "v1"}):
            manager.get_secret("INV_KEY")
        manager.invalidate("INV_KEY")
        with patch.dict("os.environ", {"INV_KEY": "v2"}):
            assert manager.get_secret("INV_KEY") == "v2"

    def test_rotation_callback(self):
        manager = SecretsManager(backend=SecretsBackend.ENV, cache_ttl=0.01)
        rotated = []
        manager.on_rotation(lambda k, old, new: rotated.append((k, old, new)))

        with patch.dict("os.environ", {"ROT_KEY": "old"}):
            manager.get_secret("ROT_KEY")
        time.sleep(0.02)
        with patch.dict("os.environ", {"ROT_KEY": "new"}):
            manager.rotate_secret("ROT_KEY")

        assert len(rotated) == 1
        assert rotated[0] == ("ROT_KEY", "old", "new")

    def test_cache_stats(self):
        manager = SecretsManager(backend=SecretsBackend.ENV)
        with patch.dict("os.environ", {"STAT_KEY": "val"}):
            manager.get_secret("STAT_KEY")
        stats = manager.get_cache_stats()
        assert stats["total_cached"] >= 1
        assert stats["backend"] == "env"
