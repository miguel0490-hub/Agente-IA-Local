import time

from src.core import security


def test_check_rate_limit_memory_allows_then_blocks():
    security._RATE_LIMITS.clear()
    user = "u1"
    assert security.check_rate_limit(user, limit=2, window_seconds=60) is True
    assert security.check_rate_limit(user, limit=2, window_seconds=60) is True
    assert security.check_rate_limit(user, limit=2, window_seconds=60) is False


def test_get_redis_client_without_dependency(monkeypatch):
    monkeypatch.setattr(security, "redis", None)
    security._REDIS_CLIENT = None
    assert security._get_redis_client() is None


def test_get_redis_client_without_url(monkeypatch):
    class DummyRedis:
        @staticmethod
        def from_url(*args, **kwargs):
            raise AssertionError("should not call from_url")

    monkeypatch.setattr(security, "redis", DummyRedis)
    monkeypatch.setenv("REDIS_URL", "")
    security._REDIS_CLIENT = None
    assert security._get_redis_client() is None


def test_check_rate_limit_redis_path(monkeypatch):
    class DummyPipe:
        def zremrangebyscore(self, *args, **kwargs):
            return self

        def zcard(self, *args, **kwargs):
            return self

        def execute(self):
            return [None, 0]

    class DummyClient:
        def pipeline(self):
            return DummyPipe()

        def zadd(self, *args, **kwargs):
            return 1

        def expire(self, *args, **kwargs):
            return 1

    monkeypatch.setattr(security, "_get_redis_client", lambda: DummyClient())
    assert security.check_rate_limit("redis-user", limit=3, window_seconds=60) is True


def test_check_rate_limit_redis_blocks_when_limit_reached(monkeypatch):
    class DummyPipe:
        def zremrangebyscore(self, *args, **kwargs):
            return self

        def zcard(self, *args, **kwargs):
            return self

        def execute(self):
            return [None, 99]

    class DummyClient:
        def pipeline(self):
            return DummyPipe()

    monkeypatch.setattr(security, "_get_redis_client", lambda: DummyClient())
    assert security.check_rate_limit("redis-user", limit=10, window_seconds=60) is False


def test_check_rate_limit_redis_exception_falls_back_memory(monkeypatch):
    class DummyClient:
        def pipeline(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(security, "_get_redis_client", lambda: DummyClient())
    security._RATE_LIMITS.clear()
    assert security.check_rate_limit("fallback-user", limit=1, window_seconds=60) is True


def test_get_redis_client_returns_cached_instance(monkeypatch):
    cached = object()
    security._REDIS_CLIENT = cached
    assert security._get_redis_client() is cached
    security._REDIS_CLIENT = None


def test_get_redis_client_handles_from_url_exception(monkeypatch):
    class DummyRedis:
        @staticmethod
        def from_url(*args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(security, "redis", DummyRedis)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    security._REDIS_CLIENT = None
    assert security._get_redis_client() is None


def test_get_redis_client_success(monkeypatch):
    class Conn:
        def ping(self):
            return True

    class DummyRedis:
        @staticmethod
        def from_url(*args, **kwargs):
            return Conn()

    monkeypatch.setattr(security, "redis", DummyRedis)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    security._REDIS_CLIENT = None
    assert security._get_redis_client() is not None


def test_env_int_invalid_and_non_positive(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_CHAT_LIMIT", raising=False)
    assert security._env_int("RATE_LIMIT_CHAT_LIMIT", 10) == 10
    monkeypatch.setenv("RATE_LIMIT_CHAT_LIMIT", "abc")
    assert security._env_int("RATE_LIMIT_CHAT_LIMIT", 10) == 10
    monkeypatch.setenv("RATE_LIMIT_CHAT_LIMIT", "0")
    assert security._env_int("RATE_LIMIT_CHAT_LIMIT", 10) == 10


def test_get_rate_limit_config_reads_env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_UPLOADS_LIMIT", "9")
    monkeypatch.setenv("RATE_LIMIT_UPLOADS_WINDOW", "120")
    assert security.get_rate_limit_config("uploads") == (9, 120)


def test_get_rate_limit_config_fallback_scope(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_X_LIMIT", raising=False)
    monkeypatch.delenv("RATE_LIMIT_X_WINDOW", raising=False)
    limit, window = security.get_rate_limit_config("x")
    assert limit == 15
    assert window == 60


def test_check_scoped_rate_limit_memory(monkeypatch):
    monkeypatch.setattr(security, "_get_redis_client", lambda: None)
    security._RATE_LIMITS.clear()
    assert security.check_scoped_rate_limit("u2", "tools", limit=1, window_seconds=60) is True
    assert security.check_scoped_rate_limit("u2", "tools", limit=1, window_seconds=60) is False


def test_get_login_rate_limit_config_kind_overrides(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_LIMIT", "8")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_WINDOW", "300")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_LIMIT", "4")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_WINDOW", "120")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_USER_LIMIT", "6")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_USER_WINDOW", "240")
    assert security.get_login_rate_limit_config("ip") == (4, 120)
    assert security.get_login_rate_limit_config("user") == (6, 240)


def test_get_login_rate_limit_config_falls_back_to_generic(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_LIMIT", "9")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_WINDOW", "330")
    monkeypatch.delenv("RATE_LIMIT_LOGIN_IP_LIMIT", raising=False)
    monkeypatch.delenv("RATE_LIMIT_LOGIN_IP_WINDOW", raising=False)
    monkeypatch.delenv("RATE_LIMIT_LOGIN_USER_LIMIT", raising=False)
    monkeypatch.delenv("RATE_LIMIT_LOGIN_USER_WINDOW", raising=False)
    assert security.get_login_rate_limit_config("ip") == (9, 330)
    assert security.get_login_rate_limit_config("user") == (9, 330)
    assert security.get_login_rate_limit_config("other") == (9, 330)


def test_get_login_backoff_config_reads_env(monkeypatch):
    monkeypatch.setenv("LOGIN_BACKOFF_IP_BASE_SECONDS", "3")
    monkeypatch.setenv("LOGIN_BACKOFF_IP_MAX_SECONDS", "45")
    monkeypatch.setenv("LOGIN_BACKOFF_IP_TRIGGER_FAILURES", "4")
    assert security.get_login_backoff_config("ip") == (3, 45, 4)


def test_login_backoff_seconds_increases_and_caps(monkeypatch):
    monkeypatch.setattr(security, "_get_redis_client", lambda: None)
    monkeypatch.setenv("RATE_LIMIT_LOGIN_USER_WINDOW", "300")
    monkeypatch.setenv("LOGIN_BACKOFF_USER_BASE_SECONDS", "2")
    monkeypatch.setenv("LOGIN_BACKOFF_USER_MAX_SECONDS", "8")
    monkeypatch.setenv("LOGIN_BACKOFF_USER_TRIGGER_FAILURES", "3")
    security._RATE_LIMITS.clear()
    key = "user:demo"
    assert security.get_login_backoff_seconds(key, "user") == 0
    security.record_login_failure(key, "user")
    security.record_login_failure(key, "user")
    assert security.get_login_backoff_seconds(key, "user") == 0
    security.record_login_failure(key, "user")
    assert security.get_login_backoff_seconds(key, "user") == 2
    security.record_login_failure(key, "user")
    assert security.get_login_backoff_seconds(key, "user") == 4
    security.record_login_failure(key, "user")
    assert security.get_login_backoff_seconds(key, "user") == 8


def test_count_recent_events_redis_success(monkeypatch):
    class DummyPipe:
        def zremrangebyscore(self, *args, **kwargs):
            return self

        def zcard(self, *args, **kwargs):
            return self

        def execute(self):
            return [None, 5]

    class DummyClient:
        def pipeline(self):
            return DummyPipe()

    monkeypatch.setattr(security, "_get_redis_client", lambda: DummyClient())
    assert security._count_recent_events("k", 60) == 5


def test_append_event_redis_success(monkeypatch):
    called = {"zadd": 0, "expire": 0}

    class DummyClient:
        def zadd(self, *args, **kwargs):
            called["zadd"] += 1
            return 1

        def expire(self, *args, **kwargs):
            called["expire"] += 1
            return 1

    monkeypatch.setattr(security, "_get_redis_client", lambda: DummyClient())
    security._append_event("k", 60)
    assert called["zadd"] == 1
    assert called["expire"] == 1


def test_count_recent_events_redis_exception_fallback_memory(monkeypatch):
    class DummyClient:
        def pipeline(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(security, "_get_redis_client", lambda: DummyClient())
    security._RATE_LIMITS["k"] = [time.time()]
    assert security._count_recent_events("k", 60) == 1


def test_append_event_redis_exception_fallback_memory(monkeypatch):
    class DummyClient:
        def zadd(self, *args, **kwargs):
            raise RuntimeError("boom")

        def expire(self, *args, **kwargs):
            return 1

    monkeypatch.setattr(security, "_get_redis_client", lambda: DummyClient())
    security._RATE_LIMITS.clear()
    security._append_event("k", 60)
    assert len(security._RATE_LIMITS["k"]) == 1


def test_login_security_backend_ready_without_requirement(monkeypatch):
    monkeypatch.delenv("LOGIN_REQUIRE_REDIS", raising=False)
    monkeypatch.setattr(security, "_get_redis_client", lambda: None)
    assert security.login_security_backend_ready() is True


def test_login_security_backend_ready_requires_redis(monkeypatch):
    monkeypatch.setenv("LOGIN_REQUIRE_REDIS", "1")
    monkeypatch.setattr(security, "_get_redis_client", lambda: None)
    assert security.login_security_backend_ready() is False


def test_login_security_backend_ready_with_redis(monkeypatch):
    monkeypatch.setenv("LOGIN_REQUIRE_REDIS", "1")

    class DummyClient:
        pass

    monkeypatch.setattr(security, "_get_redis_client", lambda: DummyClient())
    assert security.login_security_backend_ready() is True


def test_login_rate_limit_fail_closed_without_redis(monkeypatch):
    monkeypatch.setenv("LOGIN_REQUIRE_REDIS", "1")
    monkeypatch.setattr(security, "_get_redis_client", lambda: None)
    security._RATE_LIMITS.clear()
    assert security.check_scoped_rate_limit("ip:1.2.3.4", "login", limit=5, window_seconds=60) is False


def test_login_rate_limit_fail_closed_when_redis_raises(monkeypatch):
    monkeypatch.setenv("LOGIN_REQUIRE_REDIS", "1")

    class DummyClient:
        def pipeline(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(security, "_get_redis_client", lambda: DummyClient())
    security._RATE_LIMITS.clear()
    assert security.check_scoped_rate_limit("ip:1.2.3.4", "login", limit=5, window_seconds=60) is False


def test_loginfail_count_fail_closed_without_redis(monkeypatch):
    monkeypatch.setenv("LOGIN_REQUIRE_REDIS", "1")
    monkeypatch.setattr(security, "_get_redis_client", lambda: None)
    assert security._count_recent_events("loginfail:user:x", 300) == 10**9


def test_loginfail_append_skipped_without_redis_when_required(monkeypatch):
    monkeypatch.setenv("LOGIN_REQUIRE_REDIS", "1")
    monkeypatch.setattr(security, "_get_redis_client", lambda: None)
    security._RATE_LIMITS.clear()
    security._append_event("loginfail:user:z", 300)
    assert "loginfail:user:z" not in security._RATE_LIMITS


def test_loginfail_count_redis_exception_when_required(monkeypatch):
    monkeypatch.setenv("LOGIN_REQUIRE_REDIS", "1")

    class DummyClient:
        def pipeline(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(security, "_get_redis_client", lambda: DummyClient())
    assert security._count_recent_events("loginfail:user:x", 300) == 10**9


def test_loginfail_append_redis_exception_when_required(monkeypatch):
    monkeypatch.setenv("LOGIN_REQUIRE_REDIS", "1")

    class DummyClient:
        def zadd(self, *args, **kwargs):
            raise RuntimeError("boom")

        def expire(self, *args, **kwargs):
            return 1

    monkeypatch.setattr(security, "_get_redis_client", lambda: DummyClient())
    security._RATE_LIMITS.clear()
    security._append_event("loginfail:user:z", 300)
    assert "loginfail:user:z" not in security._RATE_LIMITS
