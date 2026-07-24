"""FastAPI application for the AI Development Team platform."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routers import models, runs, tasks
from core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
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

# Include routers
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
app.include_router(runs.router, prefix="/api/v1", tags=["runs"])
app.include_router(models.router, prefix="/api/v1", tags=["models"])


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "environment": settings.ENVIRONMENT}


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with API information."""
    return {
        "name": "AI Development Team API",
        "version": "0.1.0",
        "docs": "/docs",
    }
