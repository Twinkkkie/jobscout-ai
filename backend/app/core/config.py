from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "JobScout AI"
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://jobscout:jobscout@db:5432/jobscout"
    redis_url: str = "redis://redis:6379/0"
    jwt_secret: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 1440
    upload_dir: str = "/app/uploads"
    frontend_url: str = "http://localhost:5173"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_timeout_seconds: float = 20.0
    job_scan_limit: int = 100

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
