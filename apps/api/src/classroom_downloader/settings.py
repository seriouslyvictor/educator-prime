import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Tests must ignore the developer's apps/api/.env so the suite stays deterministic
# regardless of local CD_* / provider-key configuration. conftest sets CD_TESTING
# before importing the app.
_TESTING = bool(os.environ.get("CD_TESTING"))
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

# Outside tests, export apps/api/.env into the process environment so SDKs that
# read os.environ directly -- notably LiteLLM, which reads provider keys by their
# native names (OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, ...) -- get
# them from the same file pydantic uses for the CD_* settings. override=False
# keeps real shell environment variables authoritative.
if not _TESTING:
    load_dotenv(_ENV_PATH, override=False)


class Settings(BaseSettings):
    # extra="ignore": the .env also holds provider keys (OPENAI_API_KEY,
    # GEMINI_API_KEY, ...) for LiteLLM, which are not CD_ settings fields; without
    # this pydantic-settings raises extra_forbidden on those non-CD_ keys.
    model_config = SettingsConfigDict(
        env_file=None if _TESTING else str(_ENV_PATH),
        env_prefix="CD_",
        extra="ignore",
    )

    database_url: str = "sqlite:///./classroom_downloader.db"
    frontend_origin: str = "http://localhost:5173"
    google_provider: str = "mock"
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    google_token_path: str = ".tokens/google-user.json"  # deprecated, ignored
    google_oauth_state_path: str = ".tokens/google-oauth-state.txt"  # deprecated, ignored
    # Keys Fernet encryption for stored Google OAuth credentials.
    session_secret_key: str | None = None
    session_max_age_hours: int = 24
    session_cookie_name: str = "cd_session"
    grading_cache_path: str = ".cache/grading"
    grading_cache_ttl_hours: int = 24
    classroom_cache_ttl_minutes: int = 10
    google_profile_cache_ttl_minutes: int = 30
    google_drive_metadata_cache_ttl_minutes: int = 30
    export_cache_path: str = ".cache/exports"
    export_cache_ttl_hours: int = 24
    static_dir: str | None = None
    sentry_dsn: str | None = None
    sentry_environment: str = "dev"
    admin_emails: str = ""
    app_event_retention_days: int = 30
    llm_payload_logging: bool = True
    llm_payload_retention_days: int = 14
    grading_engine: Literal["mock", "litellm"] = "mock"
    litellm_model: str = "openai/gpt-5"
    litellm_timeout_seconds: int = 60
    litellm_max_retries: int = 2
    grading_auto_accept_confidence: float = 0.85
    grading_structured_output: Literal["auto", "json_object"] = "auto"
    grading_batch_mode: Literal["per_submission", "class_batch"] = "per_submission"
    rubric_infer_sample_size: int = 4
    rubric_description_min_chars: int = 200
    rubric_description_min_words: int = 25
    llm_model_catalog_mode: Literal["remote_cached", "local_only", "remote_required"] = "remote_cached"
    llm_model_catalog_url: str = (
        "https://raw.githubusercontent.com/BerriAI/litellm/main/"
        "model_prices_and_context_window.json"
    )
    llm_model_catalog_cache_path: str = ".cache/llm/model-prices.json"
    llm_model_overlay_path: str = "config/llm-model-overrides.json"
    llm_model_catalog_max_age_hours: int = 24
    log_level: str = "INFO"
    log_rich: bool = True
    log_format: Literal["text", "json"] = "text"
    log_payload_previews: bool = True
    log_preview_chars: int = 1000


@lru_cache
def get_settings() -> Settings:
    return Settings()
