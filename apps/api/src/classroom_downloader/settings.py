from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CD_")

    database_url: str = "sqlite:///./classroom_downloader.db"
    frontend_origin: str = "http://localhost:5173"
    google_provider: str = "mock"
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()
