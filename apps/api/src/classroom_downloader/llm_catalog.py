from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from .observability import get_logger, log_event, log_warning
from .settings import Settings, get_settings


logger = get_logger(__name__)


@dataclass(frozen=True)
class LlmModelEntry:
    id: str
    provider: str | None
    litellm_model: str
    enabled: bool
    display_name: str
    use_cases: list[str]
    input_cost_per_token: float | None
    output_cost_per_token: float | None
    max_input_tokens: int | None
    max_output_tokens: int | None
    supports_response_schema: bool | None
    supports_vision: bool | None
    rpm_limit: int | None
    tpm_limit: int | None
    notes: str | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LlmModelCatalog:
    default_model: str
    source: str
    models: dict[str, LlmModelEntry]

    def enabled_for(self, use_case: str) -> list[LlmModelEntry]:
        return [
            model
            for model in self.models.values()
            if model.enabled and use_case in model.use_cases
        ]


def load_llm_catalog(settings: Settings | None = None) -> LlmModelCatalog:
    settings = settings or get_settings()
    cache_path = Path(settings.llm_model_catalog_cache_path)
    overlay_path = Path(settings.llm_model_overlay_path)

    upstream, source = _load_upstream(settings, cache_path)
    overlay = _read_json_file(overlay_path) or {}
    models = _merge_models(upstream, overlay)
    default_model = str(overlay.get("default_model") or settings.litellm_model)
    catalog = LlmModelCatalog(default_model=default_model, source=source, models=models)
    log_event(
        logger,
        "llm_catalog.loaded",
        source=source,
        model_count=len(models),
        default_model=default_model,
    )
    return catalog


def estimate_cost_cents(
    model: LlmModelEntry,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    input_cost = model.input_cost_per_token or 0
    output_cost = model.output_cost_per_token or 0
    dollars = (prompt_tokens * input_cost) + (completion_tokens * output_cost)
    return round(dollars * 100, 4)


def _load_upstream(settings: Settings, cache_path: Path) -> tuple[dict[str, Any], str]:
    mode = settings.llm_model_catalog_mode
    if mode == "local_only":
        cached = _read_json_file(cache_path)
        return (cached, "cache") if cached is not None else ({}, "empty")

    if mode in {"remote_cached", "remote_required"} and not _cache_is_stale(
        cache_path,
        settings.llm_model_catalog_max_age_hours,
    ):
        cached = _read_json_file(cache_path)
        if cached is not None:
            return cached, "cache"

    try:
        remote = _fetch_upstream(settings.llm_model_catalog_url)
    except Exception as exc:
        log_warning(
            logger,
            "llm_catalog.remote_fetch_failed",
            url=settings.llm_model_catalog_url,
            error=str(exc),
        )
        if mode == "remote_required":
            raise
        cached = _read_json_file(cache_path)
        if cached is not None:
            return cached, "cache"
        return {}, "empty"

    _write_json_file(cache_path, remote)
    return remote, "remote"


def _fetch_upstream(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object catalog, got {type(data).__name__}")
    return data


def _cache_is_stale(cache_path: Path, max_age_hours: int) -> bool:
    if not cache_path.exists():
        return True
    modified_at = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc)
    max_age = timedelta(hours=max(0, max_age_hours))
    return datetime.now(timezone.utc) - modified_at > max_age


def _read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log_warning(
            logger,
            "llm_catalog.file_read_failed",
            path=str(path),
            error=str(exc),
        )
        return None
    if isinstance(data, dict):
        return data
    log_warning(
        logger,
        "llm_catalog.file_invalid",
        path=str(path),
        kind=type(data).__name__,
    )
    return None


def _write_json_file(path: Path, data: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    except OSError as exc:
        log_warning(
            logger,
            "llm_catalog.cache_write_failed",
            path=str(path),
            error=str(exc),
        )


def _merge_models(
    upstream: dict[str, Any],
    overlay: dict[str, Any],
) -> dict[str, LlmModelEntry]:
    overlay_models = overlay.get("models")
    if not isinstance(overlay_models, dict):
        return {}

    models: dict[str, LlmModelEntry] = {}
    for model_id, overlay_model in overlay_models.items():
        if not isinstance(model_id, str) or not isinstance(overlay_model, dict):
            continue
        upstream_model = upstream.get(model_id)
        if not isinstance(upstream_model, dict):
            upstream_model = {}
        models[model_id] = _merge_model(model_id, upstream_model, overlay_model)
    return models


def _merge_model(
    model_id: str,
    upstream_model: dict[str, Any],
    overlay_model: dict[str, Any],
) -> LlmModelEntry:
    return LlmModelEntry(
        id=model_id,
        provider=_string_or_none(upstream_model.get("litellm_provider"))
        or _string_or_none(upstream_model.get("provider")),
        litellm_model=str(overlay_model.get("litellm_model") or model_id),
        enabled=overlay_model.get("enabled") is True,
        display_name=str(overlay_model.get("display_name") or model_id),
        use_cases=_string_list(overlay_model.get("use_cases")),
        input_cost_per_token=_float_or_none(upstream_model.get("input_cost_per_token")),
        output_cost_per_token=_float_or_none(upstream_model.get("output_cost_per_token")),
        max_input_tokens=_int_or_none(upstream_model.get("max_input_tokens")),
        max_output_tokens=_int_or_none(upstream_model.get("max_output_tokens")),
        supports_response_schema=_bool_or_none(
            upstream_model.get("supports_response_schema")
        ),
        supports_vision=_bool_or_none(upstream_model.get("supports_vision")),
        rpm_limit=_int_or_none(overlay_model.get("rpm_limit")),
        tpm_limit=_int_or_none(overlay_model.get("tpm_limit")),
        notes=_string_or_none(overlay_model.get("notes")),
        raw={"upstream": upstream_model, "overlay": overlay_model},
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None
