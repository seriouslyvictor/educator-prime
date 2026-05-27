import pytest

from classroom_downloader.settings import Settings


def test_llm_settings_have_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CD_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("CD_GOOGLE_PROVIDER", "mock")
    for env_var in (
        "CD_GRADING_ENGINE",
        "CD_LITELLM_MODEL",
        "CD_LITELLM_TIMEOUT_SECONDS",
        "CD_LITELLM_MAX_RETRIES",
        "CD_LLM_MODEL_CATALOG_MODE",
        "CD_LLM_MODEL_CATALOG_URL",
        "CD_LLM_MODEL_CATALOG_CACHE_PATH",
        "CD_LLM_MODEL_OVERLAY_PATH",
        "CD_LLM_MODEL_CATALOG_MAX_AGE_HOURS",
    ):
        monkeypatch.delenv(env_var, raising=False)

    settings = Settings()

    assert settings.grading_engine == "mock"
    assert settings.litellm_model == "openai/gpt-5"
    assert settings.llm_model_catalog_mode == "remote_cached"
    assert settings.llm_model_catalog_url.startswith("https://raw.githubusercontent.com/BerriAI/litellm/")
    assert settings.llm_model_catalog_cache_path == ".cache/llm/model-prices.json"
    assert settings.llm_model_overlay_path == "config/llm-model-overrides.json"
    assert settings.llm_model_catalog_max_age_hours == 24
    assert settings.litellm_timeout_seconds == 60
    assert settings.litellm_max_retries == 2
