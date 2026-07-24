"""FastAPI application for the AI Development Team platform."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest
from starlette.responses import Response

from apps.api.routers import auth, costs, models, runs, tasks, ws
from core.config import get_settings
from core.observability import (
    APP_INFO,
    PrometheusMiddleware,
    health_router,
    setup_logging,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    setup_logging(log_level=settings.LOG_LEVEL)
    APP_INFO.info({
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
    })
    yield
    # Shutdown - cleanup resources if needed


app = FastAPI(
    title="AI Development Team API",
    description="Multi-agent platform for automated software development",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics middleware
app.add_middleware(PrometheusMiddleware)

# Include routers
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
app.include_router(runs.router, prefix="/api/v1", tags=["runs"])
app.include_router(models.router, prefix="/api/v1", tags=["models"])
app.include_router(costs.router, prefix="/api/v1", tags=["costs"])
app.include_router(ws.router, tags=["websocket"])
app.include_router(health_router)


@app.get("/metrics", tags=["observability"])
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with API information."""
    return {
        "name": "AI Development Team API",
        "version": "0.1.0",
        "docs": "/docs",
        "metrics": "/metrics",
    }
