from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings management using Pydantic Settings.
    Loads configuration from environment variables or a.env file.
    """

    # Application Settings
    APP_NAME: str = "Task Manager Lite"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database Settings
    DATABASE_URL: str = "sqlite:///./tasks.db"
    DATABASE_ECHO: bool = False

    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


# Global settings instance to be imported by other modules
settings = Settings()