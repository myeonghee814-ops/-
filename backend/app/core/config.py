from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Gemini (Google AI Studio) - free tier, no billing required
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    # When true, every AI call must carry its own caller-supplied key (the
    # X-Gemini-Api-Key header) - the server's own gemini_api_key above is
    # never used as a fallback, even if set. Meant for a publicly reachable
    # deployment: without this, anyone who finds the URL could drain the
    # server's shared free-tier quota with no key of their own. Left false
    # for local dev, where the convenience fallback is safe.
    require_caller_api_key: bool = False

    # Semantic Scholar (optional key raises the shared rate limit)
    semantic_scholar_api_key: str = ""

    # Database
    database_url: str = "sqlite:///./blip.db"

    # Search pipeline tuning
    candidate_count: int = 8
    top_n_results: int = 10

    # CORS
    frontend_origin: str = "http://localhost:5173"


settings = Settings()
