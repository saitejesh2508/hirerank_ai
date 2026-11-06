from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    database_url: str = "sqlite:///./hirerank.db"
    jwt_secret: str = "change-this-development-secret-before-deploying"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480
    upload_dir: str = "uploads"
    ai_api_key: str | None = None
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    frontend_origin: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[3] / ".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url
