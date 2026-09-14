from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
