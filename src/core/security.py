"""
Límites de peticiones y protección de login (rate limiting, backoff, Redis opcional).

Usado por el chat, subidas, herramientas y el formulario de autenticación. Las claves
``ratelimit:login:*`` y ``loginfail:*`` usan Redis si está disponible; con
``LOGIN_REQUIRE_REDIS=1`` y Redis caído se degrada a memoria del proceso (con log de aviso).
"""

import os
import time
from typing import Dict

from src.core.logger import get_logger

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None

# Almacén en memoria para el MVP (se migrará a Redis en el futuro)
_RATE_LIMITS: Dict[str, list] = {}
_REDIS_CLIENT = None
_LOGIN_REDIS_DEGRADE_WARNED = False

_logger = get_logger(__name__)

_DEFAULT_LIMITS = {
    "chat": (10, 60),
    "uploads": (20, 300),
    "tools": (30, 300),
    "login": (8, 300),
    "api": (60, 60),
}


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except Exception:
        return default


def _env_truthy(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _login_security_requires_redis() -> bool:
    """When True, login rate limit / backoff prefer Redis (in-memory fallback if Redis fails)."""
    return _env_truthy("LOGIN_REQUIRE_REDIS", default=False)


def _is_login_security_key(key: str) -> bool:
    return key.startswith("ratelimit:login:") or key.startswith("loginfail:")


def login_security_backend_ready() -> bool:
    """Siempre permite intentar login.

    Con ``LOGIN_REQUIRE_REDIS=1`` y Redis caído o mal configurado, los límites y el
    backoff de login se aplican en memoria del proceso (adecuado para Streamlit en
    un solo worker; en clúster usar Redis operativo).
    """
    global _LOGIN_REDIS_DEGRADE_WARNED
    if _login_security_requires_redis() and _get_redis_client() is None and not _LOGIN_REDIS_DEGRADE_WARNED:
        _LOGIN_REDIS_DEGRADE_WARNED = True
        _logger.warning(
            "LOGIN_REQUIRE_REDIS=1 pero Redis no está disponible; "
            "límites de login y backoff usan memoria local hasta reiniciar el proceso."
        )
    return True


def _get_redis_client():
    """Returns a Redis client when REDIS_URL is configured."""
    global _REDIS_CLIENT
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT
    if not redis:
        return None
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return None
    try:
        _REDIS_CLIENT = redis.from_url(redis_url, decode_responses=True, socket_timeout=1.5)
        _REDIS_CLIENT.ping()
        return _REDIS_CLIENT
    except Exception:
        return None


def reset_login_throttle_state() -> None:
    """Pone a cero límites y backoff solo del flujo de login (memoria y Redis).

    Evita bloqueos persistentes por ``ip:unknown`` o pruebas repetidas en local.
    No modifica contadores de chat, tools, subidas, etc.
    """
    for k in list(_RATE_LIMITS.keys()):
        if k.startswith("ratelimit:login:") or k.startswith("loginfail:"):
            _RATE_LIMITS.pop(k, None)

    client = _get_redis_client()
    if not client:
        return
    try:
        for key in client.scan_iter(match="ratelimit:login:*"):
            client.delete(key)
        for key in client.scan_iter(match="loginfail:*"):
            client.delete(key)
    except Exception as exc:
        _logger.warning("Redis: no se pudieron borrar claves de throttling de login: %s", exc)


def get_rate_limit_config(scope: str, fallback_limit: int | None = None, fallback_window: int | None = None) -> tuple[int, int]:
    """Returns effective rate-limit tuple for a given scope."""
    normalized = (scope or "chat").strip().lower()
    default_limit, default_window = _DEFAULT_LIMITS.get(normalized, (15, 60))
    if fallback_limit is not None:
        default_limit = fallback_limit
    if fallback_window is not None:
        default_window = fallback_window
    limit = _env_int(f"RATE_LIMIT_{normalized.upper()}_LIMIT", default_limit)
    window = _env_int(f"RATE_LIMIT_{normalized.upper()}_WINDOW", default_window)
    return limit, window


def get_login_rate_limit_config(kind: str) -> tuple[int, int]:
    """Returns login limit/window for kind: ip|user (with generic login fallback)."""
    normalized_kind = (kind or "").strip().lower()
    generic_limit, generic_window = get_rate_limit_config("login")
    if normalized_kind not in {"ip", "user"}:
        return generic_limit, generic_window
    limit = _env_int(f"RATE_LIMIT_LOGIN_{normalized_kind.upper()}_LIMIT", generic_limit)
    window = _env_int(f"RATE_LIMIT_LOGIN_{normalized_kind.upper()}_WINDOW", generic_window)
    return limit, window


def get_login_backoff_config(kind: str) -> tuple[int, int, int]:
    """Returns login backoff config: base_seconds, max_seconds, trigger_failures."""
    normalized_kind = (kind or "").strip().lower()
    suffix = normalized_kind.upper() if normalized_kind in {"ip", "user"} else "USER"
    base = _env_int(f"LOGIN_BACKOFF_{suffix}_BASE_SECONDS", 2)
    max_seconds = _env_int(f"LOGIN_BACKOFF_{suffix}_MAX_SECONDS", 60)
    trigger = _env_int(f"LOGIN_BACKOFF_{suffix}_TRIGGER_FAILURES", 3)
    return base, max_seconds, trigger


def _count_recent_events(key: str, window_seconds: int) -> int:
    now = time.time()
    require = _login_security_requires_redis() and _is_login_security_key(key)
    client = _get_redis_client()
    if client:
        try:
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, now - window_seconds)
            pipe.zcard(key)
            _, current = pipe.execute()
            return int(current)
        except Exception:
            if require:
                _logger.warning("Redis error al contar eventos de login; usando memoria local para %s", key)

    if key not in _RATE_LIMITS:
        return 0
    _RATE_LIMITS[key] = [t for t in _RATE_LIMITS[key] if now - t < window_seconds]
    return len(_RATE_LIMITS[key])


def _append_event(key: str, window_seconds: int) -> None:
    now = time.time()
    require = _login_security_requires_redis() and _is_login_security_key(key)
    client = _get_redis_client()
    if client:
        try:
            client.zadd(key, {str(now): now})
            client.expire(key, window_seconds)
            return
        except Exception:
            if require:
                _logger.warning("Redis error al registrar evento de login; usando memoria local para %s", key)

    if key not in _RATE_LIMITS:
        _RATE_LIMITS[key] = []
    _RATE_LIMITS[key] = [t for t in _RATE_LIMITS[key] if now - t < window_seconds]
    _RATE_LIMITS[key].append(now)


def record_login_failure(identifier: str, kind: str) -> None:
    """Stores a login failure event for backoff purposes."""
    normalized_kind = (kind or "").strip().lower()
    _, window_seconds = get_login_rate_limit_config(normalized_kind)
    event_key = f"loginfail:{normalized_kind}:{identifier}"
    _append_event(event_key, window_seconds)


def get_login_backoff_seconds(identifier: str, kind: str) -> int:
    """Returns required wait time before the next login attempt."""
    normalized_kind = (kind or "").strip().lower()
    _, window_seconds = get_login_rate_limit_config(normalized_kind)
    base_seconds, max_seconds, trigger_failures = get_login_backoff_config(normalized_kind)
    failures = _count_recent_events(f"loginfail:{normalized_kind}:{identifier}", window_seconds)
    if failures < trigger_failures:
        return 0
    steps = failures - trigger_failures
    wait_seconds = base_seconds * (2**steps)
    return min(wait_seconds, max_seconds)


def _consume_rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    """Consumes one token from a scoped sliding window."""
    now = time.time()

    require = _login_security_requires_redis() and _is_login_security_key(key)
    client = _get_redis_client()
    if client:
        try:
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, now - window_seconds)
            pipe.zcard(key)
            _, current = pipe.execute()
            if int(current) >= limit:
                return False
            client.zadd(key, {str(now): now})
            client.expire(key, window_seconds)
            return True
        except Exception:
            if require:
                _logger.warning("Redis error al consumir rate limit; usando memoria local para %s", key)

    if key not in _RATE_LIMITS:
        _RATE_LIMITS[key] = []

    # Limpiar timestamps viejos
    _RATE_LIMITS[key] = [t for t in _RATE_LIMITS[key] if now - t < window_seconds]

    if len(_RATE_LIMITS[key]) >= limit:
        return False  # Límite excedido

    _RATE_LIMITS[key].append(now)
    return True


def check_scoped_rate_limit(identifier: str, scope: str, limit: int | None = None, window_seconds: int | None = None) -> bool:
    """Checks scoped rate limit (chat/uploads/tools/login/api) for an identifier."""
    normalized_scope = (scope or "chat").strip().lower()
    eff_limit, eff_window = get_rate_limit_config(normalized_scope, limit, window_seconds)
    rate_key = f"ratelimit:{normalized_scope}:{identifier}"
    return _consume_rate_limit(rate_key, eff_limit, eff_window)


def check_rate_limit(user_id: str, limit: int = 15, window_seconds: int = 60) -> bool:
    """Backward-compatible wrapper for chat-scoped rate limiting."""
    return check_scoped_rate_limit(str(user_id), scope="chat", limit=limit, window_seconds=window_seconds)
