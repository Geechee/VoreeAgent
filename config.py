"""Application configuration loaded from environment variables."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+psycopg2://voree:voree@db:5432/voree"

    # Anthropic Claude API (used in Step 5)
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"

    # Voyage AI embeddings (used in Step 3) — Anthropic's recommended embeddings provider
    voyage_api_key: str = ""
    embedding_model: str = "voyage-3.5"
    embedding_dim: int = 1024  # voyage-3.5 default output dimension

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
