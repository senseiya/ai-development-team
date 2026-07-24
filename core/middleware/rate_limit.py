"""Rate limiting middleware using SlowAPI.

Configures per-endpoint rate limits:
- General API: 60 req/min
- Auth endpoints: 10 req/min (brute-force protection)
- Task creation: 5 req/min (expensive operation)
- Health/metrics: 120 req/min (monitoring needs to poll)
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

from core.config import get_settings

settings = get_settings()

# Create limiter with Redis backend if available, else in-memory
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],
    storage_uri="memory://",
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded: {exc.detail}",
            "retry_after": exc.detail.split("reset ")[-1] if "reset " in exc.detail else None,
        },
    )


# Per-endpoint limits (applied via decorators in routers)
AUTH_RATE_LIMIT = "10/minute"
TASK_RATE_LIMIT = "5/minute"
HEALTH_RATE_LIMIT = "120/minute"
DEFAULT_RATE_LIMIT = "60/minute"
