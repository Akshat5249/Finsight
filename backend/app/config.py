"""
FinSight — Application Settings
Reads all configuration from environment variables via pydantic-settings.
Every variable corresponds to a key in .env.example (§5 of the Blueprint).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+psycopg2://postgres:your-db-password@db.your-project-ref.supabase.co:5432/postgres?sslmode=require"
    )

    # ── LLM Provider ──────────────────────────────────────────────────────────
    LLM_PROVIDER: str = "openrouter"          # "openrouter" | "openai"
    LLM_MODEL: str = "openai/gpt-4o-mini"
    OPENROUTER_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # ── Qdrant Vector Store ───────────────────────────────────────────────────
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "finsight_facts"

    # ── JWT Auth (Phase 7) ────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "changeme-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── App ───────────────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"          # "development" | "production"
    LOG_LEVEL: str = "INFO"


settings = Settings()
