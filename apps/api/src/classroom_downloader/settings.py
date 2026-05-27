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
    google_token_path: str = ".tokens/google-user.json"
    google_oauth_state_path: str = ".tokens/google-oauth-state.txt"
    grading_cache_path: str = ".cache/grading"
    grading_cache_ttl_hours: int = 24
    log_level: str = "INFO"
    log_rich: bool = True
    log_payload_previews: bool = True
    log_preview_chars: int = 1000


@lru_cache
def get_settings() -> Settings:
    return Settings()
