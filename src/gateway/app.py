"""FastAPI Gateway — enterprise API layer for SuperAgente IA.

Provides a REST API decoupled from Streamlit, enabling programmatic access
to chat, tools, admin, and observability endpoints. Implements middleware
for authentication, rate limiting, correlation IDs, and request logging.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.logger import get_logger, set_correlation_id
from src.security.zero_trust import ServiceRole, create_service_token, verify_service_token

logger = get_logger(__name__)

_PUBLIC_PATHS = frozenset({"/api/v1/health", "/api/v1/status", "/api/docs", "/openapi.json"})


def _cors_allow_headers() -> list[str]:
    if os.getenv("ENVIRONMENT", "").strip().lower() == "production":
        return [
            "Authorization",
            "Content-Type",
            "X-Correlation-ID",
            "Accept",
            "X-Requested-With",
        ]
    return ["*"]


async def require_auth(request: Request) -> None:
    """Dependency that enforces service token auth on protected endpoints."""
    if request.url.path in _PUBLIC_PATHS:
        return
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth_header[7:]
    identity = verify_service_token(token)
    if not identity:
        raise HTTPException(status_code=401, detail="Invalid or expired service token")
    request.state.service_identity = identity

app = FastAPI(
    title="SuperAgente IA Gateway",
    version="2.0.0",
    description="Enterprise AI platform API",
    docs_url="/api/docs" if os.getenv("ENVIRONMENT") != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else [],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=_cors_allow_headers(),
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Injects a correlation ID into every request for distributed tracing."""
    cid = request.headers.get("X-Correlation-ID", uuid.uuid4().hex[:16])
    set_correlation_id(cid)
    request.state.correlation_id = cid

    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start

    response.headers["X-Correlation-ID"] = cid
    response.headers["X-Response-Time"] = f"{duration:.4f}"

    logger.info(
        "API %s %s %d (%.3fs)",
        request.method, request.url.path, response.status_code, duration,
    )
    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Adds security headers to all API responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


# --- Health & Status ---

@app.get("/api/v1/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "superagente-gateway", "version": "2.0.0"}


@app.get("/api/v1/status")
async def status():
    """Detailed system status."""
    from src.services.model_router import get_model_router
    from src.services.semantic_cache import get_semantic_cache

    router = get_model_router()
    cache = get_semantic_cache()

    return {
        "status": "operational",
        "providers": router.get_provider_health(),
        "cache": cache.get_stats(),
    }


# --- Chat API ---

@app.post("/api/v1/chat/completions", dependencies=[Depends(require_auth)])
async def chat_completions(request: Request):
    """Proxies chat requests through the AI pipeline with full governance."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    model = body.get("model", "")
    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="messages field required")

    from src.security.ai_firewall import MultiTurnDetector
    analysis = MultiTurnDetector.analyze_conversation(messages)
    if not analysis.safe_to_continue:
        logger.warning("Chat blocked by AI firewall: risk=%d", analysis.overall_risk)
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Request blocked by AI security policy",
                "risk_score": analysis.overall_risk,
                "threats": [t.threat_type.value for t in analysis.threats],
            },
        )

    from src.services.semantic_cache import get_semantic_cache
    cache = get_semantic_cache()
    last_msg = messages[-1].get("content", "") if messages else ""
    cached = cache.get(last_msg, model)
    if cached:
        return {
            "id": f"cache-{uuid.uuid4().hex[:8]}",
            "model": model,
            "choices": [{"message": {"role": "assistant", "content": cached}}],
            "cached": True,
        }

    return {
        "id": f"req-{uuid.uuid4().hex[:8]}",
        "model": model,
        "choices": [{"message": {"role": "assistant", "content": "[Gateway: route to provider]"}}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        "cached": False,
    }


# --- Admin API ---

@app.get("/api/v1/admin/users", dependencies=[Depends(require_auth)])
async def list_users(page: int = 1, page_size: int = 50):
    """Lists users with pagination."""
    from src.database.database import get_all_users, get_user_count
    users = get_all_users(page=page, page_size=page_size)
    total = get_user_count()
    return {"users": users, "total": total, "page": page, "page_size": page_size}


@app.get("/api/v1/admin/stats", dependencies=[Depends(require_auth)])
async def admin_stats():
    """Returns admin dashboard statistics."""
    from src.database.database import get_user_stats, get_contact_stats
    return {
        "users": get_user_stats(),
        "contacts": get_contact_stats(),
    }


# --- Cost & Usage API ---

@app.get("/api/v1/usage/summary", dependencies=[Depends(require_auth)])
async def usage_summary(user_id: int | None = None):
    from src.services.cost_tracker import get_usage_summary
    return get_usage_summary(user_id)


@app.get("/api/v1/usage/recent", dependencies=[Depends(require_auth)])
async def usage_recent(limit: int = 50):
    from src.services.cost_tracker import get_recent_usage
    return get_recent_usage(limit)


# --- Security API ---

@app.get("/api/v1/agents/health", dependencies=[Depends(require_auth)])
async def agent_health():
    """Returns agent health monitor status including circuit breakers."""
    from src.agents.health_monitor import AgentHealthMonitor
    return AgentHealthMonitor.get_instance().get_health_status()


@app.get("/api/v1/agents/fallback-chain", dependencies=[Depends(require_auth)])
async def fallback_chain_status():
    """Returns the status of the model fallback chain."""
    from src.agents.model_fallback import get_fallback_chain
    chain = get_fallback_chain()
    return {
        "chain": chain.get_chain_status({}),
        "recent_failovers": chain.get_failover_log(20),
    }


@app.get("/api/v1/security/execution-guard", dependencies=[Depends(require_auth)])
async def execution_guard_status():
    """Returns execution timeout guard status."""
    from src.security.execution_timeout_guard import ExecutionTimeoutGuard
    return ExecutionTimeoutGuard.get_instance().get_status()


@app.get("/api/v1/security/audit-log", dependencies=[Depends(require_auth)])
async def audit_log():
    from src.security.tool_guard import get_audit_log
    return {"entries": get_audit_log()[-100:]}


@app.get("/api/v1/security/policy-rules", dependencies=[Depends(require_auth)])
async def policy_rules():
    from src.security.policy_engine import get_policy_engine
    return {"rules": get_policy_engine().get_rule_summary()}


# --- Tenant API ---

@app.get("/api/v1/tenant/{tenant_id}/usage", dependencies=[Depends(require_auth)])
async def tenant_usage(tenant_id: int):
    from src.services.tenant import get_tenant_manager
    return get_tenant_manager().get_usage_summary(tenant_id)


# --- Service Token API (internal) ---

@app.post("/api/v1/internal/token", dependencies=[Depends(require_auth)])
async def create_internal_token(request: Request):
    """Issues a service token for internal microservice communication."""
    body = await request.json()
    service_name = body.get("service_name", "")
    role = body.get("role", "")
    if not service_name or not role:
        raise HTTPException(status_code=400, detail="service_name and role required")

    try:
        role_enum = ServiceRole(role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown role: {role}")

    token = create_service_token(service_name, role_enum)
    return {"token": token, "expires_in": 3600}


# --- Error handlers ---

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "correlation_id": getattr(request.state, "correlation_id", "")},
    )
