from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Host-run commands (`make lint`/`make test`/etc.) `cd backend` first, so
    # their CWD is `backend/` and they need the repo-root `.env` at `../.env`.
    # A `backend/.env` is also checked as a fallback for anyone who creates
    # one there directly. Inside the container, CWD is `/app` (== `backend/`
    # in the image), so `../.env` would resolve to `/.env` at the container
    # filesystem root, which is never mounted there and is simply not found
    # -- harmless, because compose's `env_file: .env` directive already
    # injects the repo-root `.env` as real process environment variables
    # before pydantic-settings ever reads a file, so the file-based lookup
    # here is host-only convenience and never needed in the container.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://app:app@localhost:5432/agentic_wp"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_ttl_hours: int = 12

    llm_provider: str = "fake"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    anthropic_fast_model: str = "claude-haiku-4-5-20251001"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    embedding_provider: str = "ollama"
    embedding_model: str = "bge-m3"
    embedding_dim: int = 1024

    smtp_host: str = "localhost"
    smtp_port: int = 1025

    whatsapp_mode: str = "simulated"
    whatsapp_verify_token: str = "dev-verify-token"
    whatsapp_app_secret: str = "dev-app-secret"
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""

    app_timezone: str = "Asia/Dhaka"

    cors_allowed_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
