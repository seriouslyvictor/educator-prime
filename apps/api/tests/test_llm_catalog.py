import json
import os
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from classroom_downloader.llm_catalog import estimate_cost_cents, load_llm_catalog
from classroom_downloader.settings import Settings


class _JsonResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> "_JsonResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _write_overlay(path: Path, enabled: object = True) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "default_model": "openai/gpt-5",
                "models": {
                    "openai/gpt-5": {
                        "enabled": enabled,
                        "use_cases": ["grading_draft"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def _catalog_settings(
    cache_path: Path,
    overlay_path: Path,
    mode: str,
) -> Settings:
    return Settings(
        llm_model_catalog_mode=mode,
        llm_model_catalog_url="https://example.test/model-prices.json",
        llm_model_catalog_cache_path=str(cache_path),
        llm_model_overlay_path=str(overlay_path),
        llm_model_catalog_max_age_hours=24,
    )


def _make_stale(path: Path) -> None:
    old_time = time.time() - (48 * 60 * 60)
    os.utime(path, (old_time, old_time))


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


def test_catalog_merges_upstream_cache_and_overlay(tmp_path: Path) -> None:
    cache_path = tmp_path / "model-prices.json"
    overlay_path = tmp_path / "overlay.json"
    cache_path.write_text(
        json.dumps(
            {
                "sample_spec": {},
                "openai/gpt-5": {
                    "litellm_provider": "openai",
                    "mode": "chat",
                    "input_cost_per_token": 0.000001,
                    "output_cost_per_token": 0.000004,
                    "max_input_tokens": 128000,
                    "max_output_tokens": 8192,
                    "supports_response_schema": True,
                },
                "openai/disabled": {
                    "litellm_provider": "openai",
                    "mode": "chat",
                    "input_cost_per_token": 0.000002,
                    "output_cost_per_token": 0.000006,
                },
            }
        ),
        encoding="utf-8",
    )
    overlay_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "default_model": "openai/gpt-5",
                "models": {
                    "openai/gpt-5": {
                        "enabled": True,
                        "display_name": "GPT-5",
                        "use_cases": ["grading_draft"],
                        "rpm_limit": 60,
                        "tpm_limit": 100000,
                        "notes": "local note",
                    },
                    "openai/disabled": {"enabled": False, "display_name": "Disabled"},
                },
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(
        llm_model_catalog_mode="local_only",
        llm_model_catalog_cache_path=str(cache_path),
        llm_model_overlay_path=str(overlay_path),
    )

    catalog = load_llm_catalog(settings)

    assert catalog.default_model == "openai/gpt-5"
    assert catalog.source == "cache"
    assert "openai/gpt-5" in catalog.models
    model = catalog.models["openai/gpt-5"]
    assert model.provider == "openai"
    assert model.enabled is True
    assert model.display_name == "GPT-5"
    assert model.input_cost_per_token == 0.000001
    assert model.output_cost_per_token == 0.000004
    assert model.max_input_tokens == 128000
    assert model.supports_response_schema is True
    assert model.rpm_limit == 60
    assert model.tpm_limit == 100000
    assert catalog.enabled_for("grading_draft") == [model]


def test_estimate_cost_cents_uses_catalog_token_prices(tmp_path: Path) -> None:
    cache_path = tmp_path / "model-prices.json"
    overlay_path = tmp_path / "overlay.json"
    cache_path.write_text(
        json.dumps(
            {
                "openai/gpt-5": {
                    "litellm_provider": "openai",
                    "mode": "chat",
                    "input_cost_per_token": 0.000001,
                    "output_cost_per_token": 0.000004,
                }
            }
        ),
        encoding="utf-8",
    )
    overlay_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "default_model": "openai/gpt-5",
                "models": {
                    "openai/gpt-5": {
                        "enabled": True,
                        "use_cases": ["grading_draft"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(
        llm_model_catalog_mode="local_only",
        llm_model_catalog_cache_path=str(cache_path),
        llm_model_overlay_path=str(overlay_path),
    )
    catalog = load_llm_catalog(settings)

    assert (
        estimate_cost_cents(
            catalog.models["openai/gpt-5"],
            prompt_tokens=1000,
            completion_tokens=500,
        )
        == 0.3
    )


def test_remote_cached_uses_stale_cache_when_fetch_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_path = tmp_path / "model-prices.json"
    overlay_path = tmp_path / "overlay.json"
    cache_path.write_text(
        json.dumps({"openai/gpt-5": {"litellm_provider": "openai"}}),
        encoding="utf-8",
    )
    _make_stale(cache_path)
    _write_overlay(overlay_path)
    urlopen = Mock(side_effect=OSError("network unavailable"))
    monkeypatch.setattr("classroom_downloader.llm_catalog.urlopen", urlopen)

    catalog = load_llm_catalog(_catalog_settings(cache_path, overlay_path, "remote_cached"))

    assert catalog.source == "cache"
    assert catalog.models["openai/gpt-5"].provider == "openai"
    urlopen.assert_called_once()


def test_remote_cached_returns_empty_when_fetch_fails_without_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_path = tmp_path / "model-prices.json"
    overlay_path = tmp_path / "overlay.json"
    _write_overlay(overlay_path)
    monkeypatch.setattr(
        "classroom_downloader.llm_catalog.urlopen",
        Mock(side_effect=OSError("network unavailable")),
    )

    catalog = load_llm_catalog(_catalog_settings(cache_path, overlay_path, "remote_cached"))

    assert catalog.source == "empty"
    assert catalog.models["openai/gpt-5"].provider is None


def test_remote_cached_writes_cache_when_fetch_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_path = tmp_path / "model-prices.json"
    overlay_path = tmp_path / "overlay.json"
    _write_overlay(overlay_path)
    monkeypatch.setattr(
        "classroom_downloader.llm_catalog.urlopen",
        Mock(return_value=_JsonResponse({"openai/gpt-5": {"litellm_provider": "openai"}})),
    )

    catalog = load_llm_catalog(_catalog_settings(cache_path, overlay_path, "remote_cached"))

    assert catalog.source == "remote"
    assert catalog.models["openai/gpt-5"].provider == "openai"
    assert json.loads(cache_path.read_text(encoding="utf-8")) == {
        "openai/gpt-5": {"litellm_provider": "openai"}
    }


def test_remote_required_raises_when_fetch_fails_with_stale_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_path = tmp_path / "model-prices.json"
    overlay_path = tmp_path / "overlay.json"
    cache_path.write_text(
        json.dumps({"openai/gpt-5": {"litellm_provider": "openai"}}),
        encoding="utf-8",
    )
    _make_stale(cache_path)
    _write_overlay(overlay_path)
    monkeypatch.setattr(
        "classroom_downloader.llm_catalog.urlopen",
        Mock(side_effect=OSError("network unavailable")),
    )

    with pytest.raises(OSError, match="network unavailable"):
        load_llm_catalog(_catalog_settings(cache_path, overlay_path, "remote_required"))


def test_overlay_enabled_string_is_not_treated_as_enabled(tmp_path: Path) -> None:
    cache_path = tmp_path / "model-prices.json"
    overlay_path = tmp_path / "overlay.json"
    cache_path.write_text(json.dumps({"openai/gpt-5": {}}), encoding="utf-8")
    _write_overlay(overlay_path, enabled="false")

    catalog = load_llm_catalog(_catalog_settings(cache_path, overlay_path, "local_only"))

    assert catalog.models["openai/gpt-5"].enabled is False
