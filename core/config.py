"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # PostgreSQL
    DATABASE_URL: str = (
        "postgresql+asyncpg://ai_team:ai_team_secret@localhost:5432/ai_development_team"
    )

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM Providers
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "google/gemma-4-26b-a4b-it:free"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3.5:9b"
    DEFAULT_PROVIDER: str = "openrouter"

    # API
    API_KEY_STATIC: str = "change-me-in-production"
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"

    # GitHub
    GITHUB_TOKEN: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""

    # Sandbox
    SANDBOX_IMAGE: str = "python:3.11-slim"
    SANDBOX_TIMEOUT: int = 120
    SANDBOX_MEM_LIMIT: str = "256m"

    # App
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Budget (Phase 8)
    BUDGET_MAX_COST_USD: float = 1.0
    BUDGET_MAX_TOKENS: int = 100_000
    LLM_CACHE_TTL_SECONDS: int = 3600


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
