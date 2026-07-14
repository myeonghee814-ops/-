from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # PubMed (NCBI E-utilities requires a contact email for high-volume use)
    ncbi_email: str = "blip-app@example.com"
    ncbi_api_key: str = ""

    # Database
    database_url: str = "sqlite:///./blip.db"

    # Search pipeline tuning
    pubmed_candidate_count: int = 40
    top_n_results: int = 10

    # CORS
    frontend_origin: str = "http://localhost:5173"


settings = Settings()
