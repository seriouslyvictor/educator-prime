# LiteLLM Grading Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the mock-only grading path with an opt-in LiteLLM grading engine that uses a dynamically refreshed model catalog, records token/cost metadata, and keeps the app draft-only.

**Architecture:** Add a small LLM layer beside the existing grading engine: `llm_catalog.py` loads LiteLLM's upstream model price map, merges a local overlay, and caches remote fetches; `litellm_engine.py` converts scrubbed grading requests into structured LiteLLM calls. Existing `grading.py` remains the orchestration point and continues to receive only scrubbed/pseudonymized content.

**Tech Stack:** FastAPI, SQLModel, SQLite, Pydantic settings, LiteLLM Python SDK, Rich logging, pytest.

---

## File Structure

- Create `apps/api/config/llm-model-overrides.json`
  - Local product overlay for allowed models, defaults, rate-limit notes, and use-case labels.
- Create `apps/api/src/classroom_downloader/llm_catalog.py`
  - Loads remote LiteLLM cost map, cached remote map, and local overlay.
  - Exposes `LlmModelCatalog`, `LlmModelEntry`, `load_llm_catalog()`, and `estimate_cost_cents()`.
- Create `apps/api/src/classroom_downloader/litellm_engine.py`
  - Implements `LiteLlmGradingEngine`.
  - Builds the prompt from `GradingEngineRequest`.
  - Calls LiteLLM with structured JSON output.
  - Parses and validates response shape.
- Modify `apps/api/src/classroom_downloader/settings.py`
  - Add engine/catalog/LiteLLM settings.
- Modify `apps/api/src/classroom_downloader/grading_engine.py`
  - Keep `MockGradingEngine`.
  - Add `get_grading_engine()` factory that chooses mock or LiteLLM by settings.
- Modify `apps/api/src/classroom_downloader/grading.py`
  - Replace direct `DEFAULT_GRADING_ENGINE` fallback with the factory.
  - Persist prompt tokens, completion tokens if schema is extended, total token count, and cost.
- Modify `apps/api/src/classroom_downloader/models.py`
  - Add `prompt_tokens`, `completion_tokens`, `cost_cents`, `latency_ms`, and keep `token_count` for compatibility.
- Modify `apps/api/src/classroom_downloader/schemas.py`
  - Expose attempt token/cost fields additively on `GradingSubmissionRead`.
- Modify `apps/api/.env.example` and `README.md`
  - Document engine mode, catalog mode, catalog URL/cache/overlay paths, selected model, timeout, retries.
- Test in `apps/api/tests/test_llm_catalog.py`
  - Catalog remote/cache/overlay behavior.
- Test in `apps/api/tests/test_litellm_engine.py`
  - Engine prompt, parsed result, malformed output, cost metadata.
- Extend `apps/api/tests/test_grading.py`
  - Factory selects mock by default and LiteLLM when enabled.
  - Attempt metadata persists token/cost fields.

---

## Task 1: Model Catalog Settings And Overlay

**Files:**
- Modify: `apps/api/src/classroom_downloader/settings.py`
- Create: `apps/api/config/llm-model-overrides.json`
- Modify: `apps/api/.env.example`
- Modify: `README.md`

- [ ] **Step 1: Write the failing settings test**

Create `apps/api/tests/test_llm_catalog.py` with this initial test:

```python
import os

os.environ["CD_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CD_GOOGLE_PROVIDER"] = "mock"

from classroom_downloader.settings import Settings


def test_llm_settings_have_safe_defaults() -> None:
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd apps/api
uv run pytest tests/test_llm_catalog.py::test_llm_settings_have_safe_defaults -q
```

Expected: FAIL because the settings fields do not exist.

- [ ] **Step 3: Add settings**

In `apps/api/src/classroom_downloader/settings.py`, add fields to `Settings`:

```python
    grading_engine: str = "mock"
    litellm_model: str = "openai/gpt-5"
    litellm_timeout_seconds: int = 60
    litellm_max_retries: int = 2
    llm_model_catalog_mode: str = "remote_cached"
    llm_model_catalog_url: str = (
        "https://raw.githubusercontent.com/BerriAI/litellm/main/"
        "model_prices_and_context_window.json"
    )
    llm_model_catalog_cache_path: str = ".cache/llm/model-prices.json"
    llm_model_overlay_path: str = "config/llm-model-overrides.json"
    llm_model_catalog_max_age_hours: int = 24
```

- [ ] **Step 4: Add overlay file**

Create `apps/api/config/llm-model-overrides.json`:

```json
{
  "schema_version": 1,
  "default_model": "openai/gpt-5",
  "models": {
    "openai/gpt-5": {
      "enabled": true,
      "display_name": "GPT-5",
      "use_cases": ["grading_draft"],
      "rpm_limit": null,
      "tpm_limit": null,
      "notes": "Default draft grading model. Prices and context come from LiteLLM upstream when available."
    }
  }
}
```

- [ ] **Step 5: Document settings**

Add to `apps/api/.env.example`:

```env
# Grading engine.
# Values:
# - mock: deterministic local fake grader.
# - litellm: real LLM calls through LiteLLM.
CD_GRADING_ENGINE=mock

# LiteLLM selected model. Must match a model id in the merged catalog.
CD_LITELLM_MODEL=openai/gpt-5
CD_LITELLM_TIMEOUT_SECONDS=60
CD_LITELLM_MAX_RETRIES=2

# Model catalog mode.
# Values:
# - remote_cached: fetch LiteLLM upstream when cache is stale, use cache if fetch fails.
# - local_only: never fetch, use cached/upstream file plus local overlay.
# - remote_required: fetch upstream or fail catalog loading.
CD_LLM_MODEL_CATALOG_MODE=remote_cached
CD_LLM_MODEL_CATALOG_URL=https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json
CD_LLM_MODEL_CATALOG_CACHE_PATH=.cache/llm/model-prices.json
CD_LLM_MODEL_OVERLAY_PATH=config/llm-model-overrides.json
CD_LLM_MODEL_CATALOG_MAX_AGE_HOURS=24
```

Add a short README row group under Backend Settings:

```markdown
| `CD_GRADING_ENGINE` | `mock`, `litellm` | Selects deterministic local grading or real LiteLLM grading. |
| `CD_LITELLM_MODEL` | model id | Model id from the merged LLM catalog. |
| `CD_LLM_MODEL_CATALOG_MODE` | `remote_cached`, `local_only`, `remote_required` | Controls dynamic LiteLLM price-map fetching. |
```

- [ ] **Step 6: Run test to verify it passes**

Run:

```powershell
cd apps/api
uv run pytest tests/test_llm_catalog.py::test_llm_settings_have_safe_defaults -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/api/src/classroom_downloader/settings.py apps/api/config/llm-model-overrides.json apps/api/.env.example README.md apps/api/tests/test_llm_catalog.py
git commit -m "Add LLM catalog settings"
```

---

## Task 2: Dynamic LiteLLM Catalog Loader

**Files:**
- Create: `apps/api/src/classroom_downloader/llm_catalog.py`
- Modify: `apps/api/tests/test_llm_catalog.py`

- [ ] **Step 1: Add catalog loader tests**

Append to `apps/api/tests/test_llm_catalog.py`:

```python
import json
from pathlib import Path

from classroom_downloader.llm_catalog import (
    estimate_cost_cents,
    load_llm_catalog,
)
from classroom_downloader.settings import Settings


def test_catalog_merges_upstream_cache_and_overlay(tmp_path) -> None:
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


def test_estimate_cost_cents_uses_catalog_token_prices(tmp_path) -> None:
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
                "models": {"openai/gpt-5": {"enabled": True, "use_cases": ["grading_draft"]}},
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

    assert estimate_cost_cents(catalog.models["openai/gpt-5"], prompt_tokens=1000, completion_tokens=500) == 0.3
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd apps/api
uv run pytest tests/test_llm_catalog.py -q
```

Expected: FAIL because `llm_catalog.py` does not exist.

- [ ] **Step 3: Implement catalog loader**

Create `apps/api/src/classroom_downloader/llm_catalog.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from .observability import get_logger, log_event, log_warning
from .settings import Settings, get_settings


logger = get_logger(__name__)


@dataclass(frozen=True)
class LlmModelEntry:
    id: str
    provider: str
    litellm_model: str
    enabled: bool
    display_name: str
    use_cases: list[str]
    input_cost_per_token: float
    output_cost_per_token: float
    max_input_tokens: int | None
    max_output_tokens: int | None
    supports_response_schema: bool
    supports_vision: bool
    rpm_limit: int | None
    tpm_limit: int | None
    notes: str
    raw: dict


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
    upstream, source = _load_upstream(settings)
    overlay = _load_overlay(settings)
    models: dict[str, LlmModelEntry] = {}
    for model_id, local in overlay.get("models", {}).items():
        upstream_row = upstream.get(model_id, {})
        models[model_id] = _merge_model(model_id, upstream_row, local)
    catalog = LlmModelCatalog(
        default_model=overlay.get("default_model") or settings.litellm_model,
        source=source,
        models=models,
    )
    log_event(
        logger,
        "llm.catalog.loaded",
        source=catalog.source,
        default_model=catalog.default_model,
        model_count=len(catalog.models),
        enabled_models=[model.id for model in catalog.models.values() if model.enabled],
    )
    return catalog


def estimate_cost_cents(model: LlmModelEntry, prompt_tokens: int, completion_tokens: int) -> float:
    dollars = prompt_tokens * model.input_cost_per_token + completion_tokens * model.output_cost_per_token
    return round(dollars * 100, 6)


def _load_upstream(settings: Settings) -> tuple[dict, str]:
    cache_path = Path(settings.llm_model_catalog_cache_path)
    if settings.llm_model_catalog_mode != "local_only" and _cache_is_stale(cache_path, settings.llm_model_catalog_max_age_hours):
        try:
            with urlopen(settings.llm_model_catalog_url, timeout=10) as response:
                body = response.read().decode("utf-8")
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(body, encoding="utf-8")
            log_event(logger, "llm.catalog.remote_fetch.complete", url=settings.llm_model_catalog_url, cache_path=str(cache_path))
            return json.loads(body), "remote"
        except (OSError, URLError, json.JSONDecodeError) as error:
            log_warning(logger, "llm.catalog.remote_fetch.failed", url=settings.llm_model_catalog_url, error=str(error))
            if settings.llm_model_catalog_mode == "remote_required":
                raise
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8")), "cache"
    if settings.llm_model_catalog_mode == "remote_required":
        raise FileNotFoundError(cache_path)
    return {}, "empty"


def _load_overlay(settings: Settings) -> dict:
    overlay_path = Path(settings.llm_model_overlay_path)
    if not overlay_path.exists():
        log_warning(logger, "llm.catalog.overlay_missing", path=str(overlay_path))
        return {"schema_version": 1, "default_model": settings.litellm_model, "models": {}}
    return json.loads(overlay_path.read_text(encoding="utf-8"))


def _cache_is_stale(path: Path, max_age_hours: int) -> bool:
    if not path.exists():
        return True
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return datetime.now(UTC) - modified > timedelta(hours=max_age_hours)


def _merge_model(model_id: str, upstream: dict, local: dict) -> LlmModelEntry:
    return LlmModelEntry(
        id=model_id,
        provider=upstream.get("litellm_provider", local.get("provider", "")),
        litellm_model=local.get("litellm_model", model_id),
        enabled=bool(local.get("enabled", False)),
        display_name=local.get("display_name", model_id),
        use_cases=list(local.get("use_cases", [])),
        input_cost_per_token=float(upstream.get("input_cost_per_token", local.get("input_cost_per_token", 0.0)) or 0.0),
        output_cost_per_token=float(upstream.get("output_cost_per_token", local.get("output_cost_per_token", 0.0)) or 0.0),
        max_input_tokens=upstream.get("max_input_tokens") or upstream.get("max_tokens") or local.get("max_input_tokens"),
        max_output_tokens=upstream.get("max_output_tokens") or upstream.get("max_tokens") or local.get("max_output_tokens"),
        supports_response_schema=bool(upstream.get("supports_response_schema", local.get("supports_response_schema", False))),
        supports_vision=bool(upstream.get("supports_vision", local.get("supports_vision", False))),
        rpm_limit=local.get("rpm_limit"),
        tpm_limit=local.get("tpm_limit"),
        notes=local.get("notes", ""),
        raw=upstream,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
cd apps/api
uv run pytest tests/test_llm_catalog.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/src/classroom_downloader/llm_catalog.py apps/api/tests/test_llm_catalog.py
git commit -m "Add dynamic LLM model catalog"
```

---

## Task 3: LiteLLM Dependency And Engine Skeleton

**Files:**
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/uv.lock`
- Create: `apps/api/src/classroom_downloader/litellm_engine.py`
- Modify: `apps/api/tests/test_litellm_engine.py`

- [ ] **Step 1: Add failing engine tests**

Create `apps/api/tests/test_litellm_engine.py`:

```python
import json
import os

os.environ["CD_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CD_GOOGLE_PROVIDER"] = "mock"

import pytest

from classroom_downloader.grading_engine import GradingEngineRequest
from classroom_downloader.litellm_engine import LiteLlmGradingEngine, parse_litellm_result
from classroom_downloader.llm_catalog import LlmModelEntry


def model_entry() -> LlmModelEntry:
    return LlmModelEntry(
        id="openai/gpt-5",
        provider="openai",
        litellm_model="openai/gpt-5",
        enabled=True,
        display_name="GPT-5",
        use_cases=["grading_draft"],
        input_cost_per_token=0.000001,
        output_cost_per_token=0.000004,
        max_input_tokens=128000,
        max_output_tokens=8192,
        supports_response_schema=True,
        supports_vision=False,
        rpm_limit=None,
        tpm_limit=None,
        notes="",
        raw={},
    )


def test_parse_litellm_result_requires_structured_shape() -> None:
    parsed = parse_litellm_result(
        json.dumps(
            {
                "score": 87,
                "confidence": 0.82,
                "feedback": "Good evidence, but revise the conclusion.",
                "criterion_notes": [{"criterion": "Evidence", "note": "Uses examples."}],
                "flags": ["check_reasoning"],
            }
        )
    )

    assert parsed.score == 87
    assert parsed.confidence == 0.82
    assert parsed.feedback.startswith("Good evidence")
    assert parsed.flags == ["check_reasoning"]


def test_parse_litellm_result_rejects_malformed_json() -> None:
    with pytest.raises(ValueError, match="malformed_llm_response"):
        parse_litellm_result("not json")


def test_engine_calls_litellm_with_scrubbed_payload(monkeypatch) -> None:
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)

        class Choice:
            message = {
                "content": json.dumps(
                    {
                        "score": 91,
                        "confidence": 0.9,
                        "feedback": "Strong work.",
                        "criterion_notes": [],
                        "flags": [],
                    }
                )
            }

        class Response:
            choices = [Choice()]
            usage = {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140}

        return Response()

    monkeypatch.setattr("classroom_downloader.litellm_engine.litellm.completion", fake_completion)
    engine = LiteLlmGradingEngine(model=model_entry(), timeout_seconds=30, max_retries=1)

    result = engine.grade(
        GradingEngineRequest(
            job_id="job-1",
            submission_id="submission-1",
            activity_title="Essay Draft",
            rubric_mode="brief",
            teacher_loop="approve",
            student_label="student_001",
            source_label="submission_001",
            mime_type="text/plain",
            content="This is scrubbed work by [student].",
        )
    )

    assert result.score == 91
    assert result.confidence == 0.9
    assert result.feedback == "Strong work."
    assert captured["model"] == "openai/gpt-5"
    rendered = json.dumps(captured["messages"])
    assert "student_001" in rendered
    assert "This is scrubbed work" in rendered
    assert "Ana Silva" not in rendered
```

- [ ] **Step 2: Add LiteLLM dependency**

Modify `apps/api/pyproject.toml` dependencies:

```toml
  "litellm>=1.80.0",
```

Run:

```powershell
cd apps/api
uv lock
```

Expected: `apps/api/uv.lock` updates.

- [ ] **Step 3: Run tests to verify they fail on missing implementation**

Run:

```powershell
cd apps/api
uv run pytest tests/test_litellm_engine.py -q
```

Expected: FAIL because `litellm_engine.py` does not exist.

- [ ] **Step 4: Implement LiteLLM engine**

Create `apps/api/src/classroom_downloader/litellm_engine.py`:

```python
from __future__ import annotations

import json
from typing import Any

import litellm

from .grading_engine import GradingEngineRequest, GradingEngineResult
from .llm_catalog import LlmModelEntry
from .observability import get_logger, log_event, text_preview


logger = get_logger(__name__)


class LiteLlmGradingEngine:
    name = "litellm"

    def __init__(self, model: LlmModelEntry, timeout_seconds: int, max_retries: int):
        self.catalog_model = model
        self.model = model.litellm_model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.last_usage: dict[str, int] = {}
        self.last_latency_ms: int | None = None

    def grade(self, request: GradingEngineRequest) -> GradingEngineResult:
        messages = build_messages(request)
        log_event(
            logger,
            "litellm.grade.request",
            model=self.model,
            job_id=request.job_id,
            submission_id=request.submission_id,
            messages=messages,
            content_preview=text_preview(request.content),
        )
        response = litellm.completion(
            model=self.model,
            messages=messages,
            timeout=self.timeout_seconds,
            num_retries=self.max_retries,
            response_format={"type": "json_object"},
        )
        self.last_usage = _usage_dict(getattr(response, "usage", None))
        content = _response_content(response)
        log_event(
            logger,
            "litellm.grade.response",
            model=self.model,
            job_id=request.job_id,
            submission_id=request.submission_id,
            usage=self.last_usage,
            raw_content=content,
        )
        return parse_litellm_result(content)


def build_messages(request: GradingEngineRequest) -> list[dict[str, str]]:
    system = (
        "You draft grades for a teacher. Return only JSON. "
        "Do not claim the grade is final. The teacher must review it."
    )
    user = {
        "activity_title": request.activity_title,
        "rubric_mode": request.rubric_mode,
        "teacher_loop": request.teacher_loop,
        "student_label": request.student_label,
        "source_label": request.source_label,
        "mime_type": request.mime_type,
        "submission_text": request.content,
        "required_json_shape": {
            "score": "number from 0 to 100",
            "confidence": "number from 0 to 1",
            "feedback": "teacher-facing feedback draft",
            "criterion_notes": [{"criterion": "string", "note": "string"}],
            "flags": ["string"],
        },
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
    ]


def parse_litellm_result(content: str) -> GradingEngineResult:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError("malformed_llm_response") from error

    try:
        score = float(data["score"])
        confidence = float(data["confidence"])
        feedback = str(data["feedback"])
        flags = [str(flag) for flag in data.get("flags", [])]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("malformed_llm_response") from error

    if not 0 <= score <= 100 or not 0 <= confidence <= 1 or not feedback.strip():
        raise ValueError("malformed_llm_response")

    return GradingEngineResult(
        score=score,
        confidence=confidence,
        feedback=feedback,
        flags=flags,
    )


def _response_content(response: Any) -> str:
    choice = response.choices[0]
    message = getattr(choice, "message", None)
    if isinstance(message, dict):
        return str(message.get("content", ""))
    return str(getattr(message, "content", ""))


def _usage_dict(usage: Any) -> dict[str, int]:
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return {str(key): int(value) for key, value in usage.items() if value is not None}
    result = {}
    for key in ["prompt_tokens", "completion_tokens", "total_tokens"]:
        value = getattr(usage, key, None)
        if value is not None:
            result[key] = int(value)
    return result
```

- [ ] **Step 5: Run engine tests**

Run:

```powershell
cd apps/api
uv run pytest tests/test_litellm_engine.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/pyproject.toml apps/api/uv.lock apps/api/src/classroom_downloader/litellm_engine.py apps/api/tests/test_litellm_engine.py
git commit -m "Add LiteLLM grading engine"
```

---

## Task 4: Engine Factory And Attempt Cost Metadata

**Files:**
- Modify: `apps/api/src/classroom_downloader/models.py`
- Modify: `apps/api/src/classroom_downloader/schemas.py`
- Modify: `apps/api/src/classroom_downloader/grading_engine.py`
- Modify: `apps/api/src/classroom_downloader/grading.py`
- Modify: `apps/api/tests/test_grading.py`

- [ ] **Step 1: Add failing grading metadata tests**

Append to `apps/api/tests/test_grading.py`:

```python
def test_litellm_engine_attempt_metadata_is_persisted(monkeypatch, tmp_path) -> None:
    get_settings().grading_cache_path = str(tmp_path / "grading")
    settings = get_settings()
    settings.grading_engine = "litellm"
    settings.litellm_model = "openai/gpt-5"
    settings.llm_model_catalog_mode = "local_only"
    settings.llm_model_catalog_cache_path = str(tmp_path / "model-prices.json")
    settings.llm_model_overlay_path = str(tmp_path / "overlay.json")
    Path(settings.llm_model_catalog_cache_path).write_text(
        '{"openai/gpt-5":{"litellm_provider":"openai","mode":"chat","input_cost_per_token":0.000001,"output_cost_per_token":0.000004}}',
        encoding="utf-8",
    )
    Path(settings.llm_model_overlay_path).write_text(
        '{"schema_version":1,"default_model":"openai/gpt-5","models":{"openai/gpt-5":{"enabled":true,"use_cases":["grading_draft"]}}}',
        encoding="utf-8",
    )

    def fake_completion(**kwargs):
        class Choice:
            message = {"content": '{"score": 84, "confidence": 0.8, "feedback": "Solid draft.", "criterion_notes": [], "flags": []}'}

        class Response:
            choices = [Choice()]
            usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}

        return Response()

    monkeypatch.setattr("classroom_downloader.litellm_engine.litellm.completion", fake_completion)

    try:
        with TestClient(app) as client:
            job = client.post(
                "/api/grading/jobs",
                json={
                    "course_id": "course-2",
                    "activity_id": "activity-3",
                    "rubric_mode": "brief",
                    "teacher_loop": "approve",
                },
            ).json()
            body = client.post(f"/api/grading/jobs/{job['id']}/draft").json()
    finally:
        settings.grading_engine = "mock"

    submission = body["submissions"][0]
    assert submission["ai_engine"] == "litellm"
    assert submission["ai_model"] == "openai/gpt-5"
    assert submission["ai_prompt_tokens"] == 100
    assert submission["ai_completion_tokens"] == 50
    assert submission["ai_token_count"] == 150
    assert submission["ai_cost_cents"] == 0.03
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd apps/api
uv run pytest tests/test_grading.py::test_litellm_engine_attempt_metadata_is_persisted -q
```

Expected: FAIL because attempt fields/factory are not wired.

- [ ] **Step 3: Extend models**

In `apps/api/src/classroom_downloader/models.py`, update `GradingAiAttempt`:

```python
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    token_count: int | None = None
    cost_cents: float | None = None
    latency_ms: int | None = None
```

Keep existing `token_count` and `cost_cents`; add the new fields around them. `SQLModel.metadata.create_all()` will add columns only for fresh dev/test DBs. If local SQLite already exists, delete/recreate dev DB or add a tiny migration later.

- [ ] **Step 4: Extend schemas**

In `apps/api/src/classroom_downloader/schemas.py`, add to `GradingSubmissionRead`:

```python
    ai_prompt_tokens: int | None = None
    ai_completion_tokens: int | None = None
    ai_token_count: int | None = None
    ai_cost_cents: float | None = None
    ai_latency_ms: int | None = None
```

- [ ] **Step 5: Add engine factory**

In `apps/api/src/classroom_downloader/grading_engine.py`, replace the global default-only selection with:

```python
def get_grading_engine() -> GradingEngine:
    from .llm_catalog import load_llm_catalog
    from .litellm_engine import LiteLlmGradingEngine
    from .settings import get_settings

    settings = get_settings()
    if settings.grading_engine == "mock":
        return DEFAULT_GRADING_ENGINE
    if settings.grading_engine == "litellm":
        catalog = load_llm_catalog(settings)
        model = catalog.models.get(settings.litellm_model)
        if model is None or not model.enabled:
            raise ValueError("litellm_model_not_enabled")
        return LiteLlmGradingEngine(
            model=model,
            timeout_seconds=settings.litellm_timeout_seconds,
            max_retries=settings.litellm_max_retries,
        )
    raise ValueError("unknown_grading_engine")
```

- [ ] **Step 6: Wire factory and metadata in grading**

In `apps/api/src/classroom_downloader/grading.py`:

Change import:

```python
from .grading_engine import DEFAULT_GRADING_ENGINE, GradingEngine, GradingEngineRequest
```

to:

```python
from .grading_engine import GradingEngine, GradingEngineRequest, get_grading_engine
from .llm_catalog import estimate_cost_cents, load_llm_catalog
```

In `draft_grading_job()` and `retry_submission()`, replace:

```python
grading_engine = grading_engine or DEFAULT_GRADING_ENGINE
```

with:

```python
grading_engine = grading_engine or get_grading_engine()
```

After the engine call succeeds in `_draft_submission()`, compute usage:

```python
    prompt_tokens = getattr(grading_engine, "last_usage", {}).get("prompt_tokens")
    completion_tokens = getattr(grading_engine, "last_usage", {}).get("completion_tokens")
    total_tokens = getattr(grading_engine, "last_usage", {}).get("total_tokens")
    cost_cents = None
    if getattr(grading_engine, "name", "") == "litellm" and prompt_tokens is not None and completion_tokens is not None:
        catalog = load_llm_catalog()
        model_id = getattr(grading_engine, "model", None)
        if model_id and model_id in catalog.models:
            cost_cents = estimate_cost_cents(catalog.models[model_id], prompt_tokens, completion_tokens)
```

Pass these values into `_record_attempt()`.

Update `_record_attempt()` signature:

```python
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    token_count: int | None = None,
    cost_cents: float | None = None,
    latency_ms: int | None = None,
```

Set them on `GradingAiAttempt`.

Update `_submission_read()` to include:

```python
        ai_prompt_tokens=attempt.prompt_tokens if attempt else None,
        ai_completion_tokens=attempt.completion_tokens if attempt else None,
        ai_token_count=attempt.token_count if attempt else None,
        ai_cost_cents=attempt.cost_cents if attempt else None,
        ai_latency_ms=attempt.latency_ms if attempt else None,
```

- [ ] **Step 7: Run focused test**

Run:

```powershell
cd apps/api
uv run pytest tests/test_grading.py::test_litellm_engine_attempt_metadata_is_persisted -q
```

Expected: PASS.

- [ ] **Step 8: Run all backend tests**

Run:

```powershell
cd apps/api
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add apps/api/src/classroom_downloader/models.py apps/api/src/classroom_downloader/schemas.py apps/api/src/classroom_downloader/grading_engine.py apps/api/src/classroom_downloader/grading.py apps/api/tests/test_grading.py
git commit -m "Wire grading engine selection and LLM attempt costs"
```

---

## Task 5: Operator Logging And Failure Modes

**Files:**
- Modify: `apps/api/src/classroom_downloader/litellm_engine.py`
- Modify: `apps/api/src/classroom_downloader/grading.py`
- Modify: `apps/api/tests/test_litellm_engine.py`
- Modify: `apps/api/tests/test_grading.py`

- [ ] **Step 1: Add malformed response grading test**

Append to `apps/api/tests/test_grading.py`:

```python
def test_litellm_malformed_response_marks_attempt_failed(monkeypatch, tmp_path) -> None:
    get_settings().grading_cache_path = str(tmp_path / "grading")
    settings = get_settings()
    settings.grading_engine = "litellm"
    settings.litellm_model = "openai/gpt-5"
    settings.llm_model_catalog_mode = "local_only"
    settings.llm_model_catalog_cache_path = str(tmp_path / "model-prices.json")
    settings.llm_model_overlay_path = str(tmp_path / "overlay.json")
    Path(settings.llm_model_catalog_cache_path).write_text(
        '{"openai/gpt-5":{"litellm_provider":"openai","mode":"chat","input_cost_per_token":0.000001,"output_cost_per_token":0.000004}}',
        encoding="utf-8",
    )
    Path(settings.llm_model_overlay_path).write_text(
        '{"schema_version":1,"default_model":"openai/gpt-5","models":{"openai/gpt-5":{"enabled":true,"use_cases":["grading_draft"]}}}',
        encoding="utf-8",
    )

    def fake_completion(**kwargs):
        class Choice:
            message = {"content": "not-json"}

        class Response:
            choices = [Choice()]
            usage = {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15}

        return Response()

    monkeypatch.setattr("classroom_downloader.litellm_engine.litellm.completion", fake_completion)

    try:
        with TestClient(app) as client:
            job = client.post(
                "/api/grading/jobs",
                json={
                    "course_id": "course-2",
                    "activity_id": "activity-3",
                    "rubric_mode": "brief",
                    "teacher_loop": "approve",
                },
            ).json()
            body = client.post(f"/api/grading/jobs/{job['id']}/draft").json()
    finally:
        settings.grading_engine = "mock"

    submission = body["submissions"][0]
    assert submission["ai_attempt_status"] == "failed"
    assert submission["ai_safe_error"] == "grading_engine_failed"
    assert submission["error"] == "grading_engine_failed"
```

- [ ] **Step 2: Run test**

Run:

```powershell
cd apps/api
uv run pytest tests/test_grading.py::test_litellm_malformed_response_marks_attempt_failed -q
```

Expected: PASS if Task 4 preserved existing failure path; otherwise FAIL and fix by ensuring `ValueError("malformed_llm_response")` is caught by `_draft_submission()`.

- [ ] **Step 3: Improve LiteLLM logs**

In `apps/api/src/classroom_downloader/litellm_engine.py`, ensure request/response logs include:

```python
log_event(
    logger,
    "litellm.grade.catalog_model",
    model_id=self.catalog_model.id,
    provider=self.catalog_model.provider,
    input_cost_per_token=self.catalog_model.input_cost_per_token,
    output_cost_per_token=self.catalog_model.output_cost_per_token,
    max_input_tokens=self.catalog_model.max_input_tokens,
    max_output_tokens=self.catalog_model.max_output_tokens,
    rpm_limit=self.catalog_model.rpm_limit,
    tpm_limit=self.catalog_model.tpm_limit,
)
```

Place this in `grade()` before `litellm.completion()`.

- [ ] **Step 4: Run backend tests**

Run:

```powershell
cd apps/api
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/src/classroom_downloader/litellm_engine.py apps/api/src/classroom_downloader/grading.py apps/api/tests/test_litellm_engine.py apps/api/tests/test_grading.py
git commit -m "Harden LiteLLM grading failure handling"
```

---

## Task 6: Manual Verification Script For One Real Draft

**Files:**
- Create: `apps/api/scripts/smoke_litellm_grading.py`
- Modify: `README.md`

- [ ] **Step 1: Create local smoke script**

Create `apps/api/scripts/smoke_litellm_grading.py`:

```python
from classroom_downloader.grading_engine import GradingEngineRequest
from classroom_downloader.grading_engine import get_grading_engine


def main() -> None:
    engine = get_grading_engine()
    result = engine.grade(
        GradingEngineRequest(
            job_id="smoke-job",
            submission_id="smoke-submission",
            activity_title="Smoke Test Assignment",
            rubric_mode="brief",
            teacher_loop="approve",
            student_label="student_001",
            source_label="submission_001",
            mime_type="text/plain",
            content="This is a scrubbed local smoke test submission. It contains no real student data.",
        )
    )
    print(result)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Document smoke usage**

Add to README under Backend Settings:

```markdown
LiteLLM smoke test:

```powershell
cd apps/api
$env:CD_GRADING_ENGINE="litellm"
$env:CD_LITELLM_MODEL="openai/gpt-5"
uv run python scripts/smoke_litellm_grading.py
```
```

- [ ] **Step 3: Run script in mock mode**

Run:

```powershell
cd apps/api
$env:CD_GRADING_ENGINE="mock"
uv run python scripts/smoke_litellm_grading.py
```

Expected: prints a deterministic mock `GradingEngineResult`.

- [ ] **Step 4: Commit**

```powershell
git add apps/api/scripts/smoke_litellm_grading.py README.md
git commit -m "Add LiteLLM grading smoke script"
```

---

## Final Verification

- [ ] Run backend tests:

```powershell
cd apps/api
uv run pytest -q
```

Expected: all tests pass.

- [ ] Run frontend build to verify additive schema changes do not break TS:

```powershell
cd apps/web
pnpm run build
```

Expected: build passes.

- [ ] Inspect git history:

```powershell
git log --oneline -5
git status --short --branch
```

Expected: task commits are present; unrelated untracked `docs/` remains untouched unless explicitly intended.

---

## Self-Review

- Spec coverage: The plan covers dynamic LiteLLM model fetching, local overlay, model prices/context source of truth, rate-limit notes, engine wiring, structured output validation, cost/token metadata, operator logging, and smoke testing.
- Scope discipline: The plan does not add batching, Classroom posting, UI settings screens, or provider dashboards.
- Privacy boundary: The engine still receives only `GradingEngineRequest`, which is created after extraction and scrubber. Logs remain operator-visible and can include payload previews.
- Freshness: Remote catalog fetching is optional and cached; `local_only` and `remote_required` cover offline and strict modes.
- Missing future work: UI controls for model selection and scheduled catalog refresh are intentionally not in this slice.
