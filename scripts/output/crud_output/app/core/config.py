from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration settings using Pydantic Settings.

    This class reads environment variables and provides a centralized
    location for all application-wide configuration parameters.
    """

    # Database Configuration
    DATABASE_URL: str = "sqlite:///./task_master_pro.db"

    # Server Configuration
    PROJECT_NAME: str = "Task Master Pro"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # Model configuration for Pydantic Settings
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8"
    )


# Global settings instance to be used across the application
settings = Settings()