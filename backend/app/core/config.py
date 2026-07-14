from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Gemini (Google AI Studio) - free tier, no billing required
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"

    # Semantic Scholar (optional key raises the shared rate limit)
    semantic_scholar_api_key: str = ""

    # Database
    database_url: str = "sqlite:///./blip.db"

    # Search pipeline tuning
    candidate_count: int = 40
    top_n_results: int = 10

    # CORS
    frontend_origin: str = "http://localhost:5173"


settings = Settings()
