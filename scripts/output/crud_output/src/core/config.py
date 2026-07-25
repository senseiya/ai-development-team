from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration settings.

    Uses pydantic-settings to load environment variables.
    Values can be overridden via environment variables or a.env file.
    """

    # Application Settings
    APP_NAME: str = Field(default="TaskMaster-Pro", env="APP_NAME")
    APP_VERSION: str = Field(default="1.0.0", env="APP_VERSION")
    DEBUG: bool = Field(default=False, env="DEBUG")

    # Database Settings
    # Defaulting to a local SQLite file in the current directory
    DATABASE_URL: str = Field(
        default="sqlite:///./taskmaster.db", env="DATABASE_URL"
    )

    # API Settings
    API_PREFIX: str = Field(default="/api/v1", env="API_PREFIX")
    API_DOCS_URL: str = Field(default="/docs", env="API_DOCS_URL")
    API_REDOC_URL: str = Field(default="/redoc", env="API_REDOC_URL")
    API_UTILS_URL: str = Field(default="/", env="API_UTILS_URL")

    # Configuration loading
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Singleton instance for application-wide use
settings = Settings()