from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application configuration, loaded from environment variables.

    Keeping all configuration in one Pydantic-validated object (rather than
    scattering os.environ calls through the codebase) makes required settings
    explicit, type-checked, and easy to override per-environment via a .env
    file or real environment variables in Docker/production.
    """

    APP_NAME: str = "BLIP API"
    APP_ENV: str = "development"
    DEBUG: bool = True

    API_V1_PREFIX: str = "/api/v1"

    # SQLite for local development; swap for a postgresql+asyncpg:// URL in
    # production without touching any application code.
    DATABASE_URL: str = "sqlite+aiosqlite:///./blip.db"

    # Comma-separated list of allowed origins, e.g. "http://localhost:5173,https://blip.app"
    CORS_ORIGINS: str = "http://localhost:5173"

    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor so the .env file is parsed only once per process."""
    return Settings()
