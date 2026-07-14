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

    # "text" for human-readable local logs; "json" for production log aggregators.
    LOG_FORMAT: str = "text"

    # Optional: raises Semantic Scholar's shared-pool rate limit. Unauthenticated
    # requests work fine for development.
    SEMANTIC_SCHOLAR_API_KEY: str | None = None

    # Optional: identifies requests for OpenAlex's "polite pool" (higher rate limits).
    OPENALEX_MAILTO: str | None = None

    EXTERNAL_API_TIMEOUT_SECONDS: float = 10.0
    SEARCH_CACHE_TTL_SECONDS: int = 3600

    # Required for the AI analysis pipeline (services/ai_analysis_service.py).
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Minimum analyzed papers required before the comparison engine will run
    # (services/comparison_service.py).
    COMPARISON_MIN_PAPERS: int = 10

    # --- Authentication placeholders (core/security.py, models/user.py) ---
    # No login endpoint exists yet; these back the token-signing utilities
    # that will be wired up once real auth is implemented. The default is
    # fine for local dev but MUST be overridden with a real secret in any
    # shared/production environment.
    SECRET_KEY: str = "insecure-dev-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

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
