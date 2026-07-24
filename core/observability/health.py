"""Health check endpoints — /health/live, /health/ready, /health.

Liveness: always 200 if the process is up.
Readiness: checks PostgreSQL and Redis connectivity.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_db_session
from core.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/health/live", tags=["health"])
async def liveness() -> dict[str, str]:
    """Kubernetes-style liveness probe.

    Returns 200 if the process is alive.
    """
    return {"status": "alive"}


@router.get(
    "/health/ready",
    tags=["health"],
)
async def readiness(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Kubernetes-style readiness probe.

    Checks:
    - PostgreSQL connectivity
    - Redis connectivity

    Returns 200 if all dependencies are reachable, 503 otherwise.
    """
    checks: dict[str, dict[str, Any]] = {}
    healthy = True

    # Check PostgreSQL
    try:
        start = time.perf_counter()
        await db.execute(text("SELECT 1"))
        pg_ms = (time.perf_counter() - start) * 1000
        checks["postgres"] = {"status": "ok", "latency_ms": round(pg_ms, 2)}
    except Exception as e:
        checks["postgres"] = {"status": "error", "error": str(e)}
        healthy = False

    # Check Redis
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL, socket_timeout=2)
        start = time.perf_counter()
        await r.ping()
        redis_ms = (time.perf_counter() - start) * 1000
        await r.aclose()
        checks["redis"] = {"status": "ok", "latency_ms": round(redis_ms, 2)}
    except Exception as e:
        checks["redis"] = {"status": "error", "error": str(e)}
        healthy = False

    result = {
        "status": "ready" if healthy else "not_ready",
        "checks": checks,
    }

    from fastapi.responses import JSONResponse

    return JSONResponse(
        content=result,
        status_code=200 if healthy else 503,
    )


@router.get("/health", tags=["health"])
async def health(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Combined health endpoint with full system status."""
    checks: dict[str, dict[str, Any]] = {}

    # PostgreSQL
    try:
        start = time.perf_counter()
        await db.execute(text("SELECT 1"))
        pg_ms = (time.perf_counter() - start) * 1000
        checks["postgres"] = {"status": "ok", "latency_ms": round(pg_ms, 2)}
    except Exception as e:
        checks["postgres"] = {"status": "error", "error": str(e)}

    # Redis
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL, socket_timeout=2)
        start = time.perf_counter()
        await r.ping()
        redis_ms = (time.perf_counter() - start) * 1000
        await r.aclose()
        checks["redis"] = {"status": "ok", "latency_ms": round(redis_ms, 2)}
    except Exception as e:
        checks["redis"] = {"status": "error", "error": str(e)}

    # OpenRouter key configured
    checks["openrouter"] = {
        "status": "configured" if settings.OPENROUTER_API_KEY else "not_configured"
    }

    # Ollama
    try:
        import httpx

        async with httpx.AsyncClient(timeout=2) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            checks["ollama"] = {"status": "ok", "models": models}
    except Exception:
        checks["ollama"] = {"status": "unreachable"}

    all_ok = all(c.get("status") in ("ok", "configured", "not_configured") for c in checks.values())

    return {
        "status": "healthy" if all_ok else "degraded",
        "environment": settings.ENVIRONMENT,
        "checks": checks,
    }
