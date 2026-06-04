# AI Grading Layer

This document explains the current AI grading layer: what runs today, what is still draft-only, how privacy gates work, and which settings/operators can tweak before a real model call.

## Current State

The grader has two engines:

| Engine | Setting | What it does |
| --- | --- | --- |
| Mock | `CD_GRADING_ENGINE=mock` | Deterministic local fake grading. This is the default and makes no model/vendor call. |
| LiteLLM | `CD_GRADING_ENGINE=litellm` | Real model call through LiteLLM, using the selected catalog model. Opt-in only. |

The app remains draft-only. The AI layer creates draft scores and feedback for teacher review. It does not post grades, comments, or feedback to Google Classroom.

## Runtime Flow

The grading path is:

1. Resolve Classroom/Drive submissions for a selected course assignment.
2. Cache source files under `apps/api/.cache/grading/<job_id>/` for retry.
3. Extract gradeable text and metadata.
4. Pseudonymize and scrub the extracted content.
5. Block submissions that are unsupported, failed, or high re-identification risk.
6. Build a `GradingEngineRequest` containing only scrubbed content plus pseudonymous labels.
7. Run the configured grading engine.
8. Validate the structured result.
9. Persist a draft result and safe attempt metadata.

The engine receives `student_label` values such as `student_001` and source labels such as `submission_001`, not raw names or emails.

## Privacy Boundary

The privacy boundary sits before `GradingEngine.grade()`.

Source files may contain real student data while they are being downloaded, cached, extracted, and scrubbed locally. A real model provider should only see the scrubbed `GradingEngineRequest.content`.

The scrubber removes or replaces:

- Known student name.
- Known student email.
- Email-like strings.
- Phone-like strings.
- URLs.
- Obvious student/school ID-like strings.
- Name-bearing source filenames, replaced by safe labels.

Privacy statuses:

| Status | Meaning |
| --- | --- |
| `clean` | No direct identifiers found. |
| `redacted` | Identifiers were removed. |
| `high_reidentification_risk` | Known identifiers remain after scrubbing; engine call is blocked. |
| `failed` | Extraction or privacy processing could not safely produce model input. |

Unsupported visual/image submissions are currently blocked before the engine. In the real Naruto test, 15 files were found, 12 passed, and 3 image submissions were blocked as `unsupported_visual_submission`.

## Extraction Support

Extraction currently supports text-first submissions:

| Input | Current behavior |
| --- | --- |
| `text/*` | Supported. |
| JSON, JavaScript, Python-like code, XML, YAML | Supported when bytes decode as text. |
| PDF and DOCX MIME types | Degraded text path only if bytes decode as text. Full document/OCR extraction is not implemented yet. |
| Images | Blocked as `unsupported_visual_submission`. |
| Binary/unknown files | Blocked as unsupported. |

This is intentionally conservative. Do not enable real model grading for visual or binary work until an extraction/OCR path exists and is tested.

## Engine Selection

Engine selection lives in `apps/api/src/classroom_downloader/grading_engine.py`.

`get_grading_engine()`:

- Returns `MockGradingEngine` when `CD_GRADING_ENGINE=mock`.
- Loads the merged model catalog and returns `LiteLlmGradingEngine` when `CD_GRADING_ENGINE=litellm`.
- Requires the selected model to exist in the merged catalog and be enabled.

If the selected LiteLLM model is missing or disabled, the factory raises `grading_model_not_enabled`.

## LiteLLM Engine

The LiteLLM implementation lives in `apps/api/src/classroom_downloader/litellm_engine.py`.

It calls:

```python
litellm.completion(
    model=...,
    messages=...,
    timeout=...,
    num_retries=...,
    max_tokens=...,
    response_format={"type": "json_object"},
)
```

The engine asks for JSON with:

- `score`: number from 0 to 100.
- `confidence`: number from 0 to 1.
- `feedback`: non-empty draft feedback.
- `criterion_notes`: requested in the prompt for future use, but not persisted yet.
- `flags`: list of strings.

Malformed JSON, missing fields, invalid ranges, empty feedback, or non-string flags raise `malformed_llm_response`. The grading flow catches that and records the attempt as failed with `grading_engine_failed`.

The LiteLLM engine does not log submission text previews or raw model responses. It logs structured metadata such as job ID, submission ID, model, labels, content length, score, confidence, flags, usage, and latency.

## Model Catalog

Model catalog code lives in `apps/api/src/classroom_downloader/llm_catalog.py`.

The catalog merges:

1. LiteLLM upstream price/context data.
2. Local overlay from `apps/api/config/llm-model-overrides.json`.

The overlay is the product allow-list. Only models listed there are exposed to the app.

Current overlay:

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

To add a model, add it under `models`, set `enabled: true`, and include `grading_draft` in `use_cases`. The selected model must match `CD_LITELLM_MODEL`.

Catalog modes:

| Mode | Behavior |
| --- | --- |
| `remote_cached` | Fetch upstream when cache is stale, fall back to cache if fetch fails. Default. |
| `local_only` | Never fetch; use local cached upstream data plus overlay. |
| `remote_required` | Fetch upstream when stale/missing; fail if fetch fails. |

Cost is estimated from `input_cost_per_token` and `output_cost_per_token` and stored as cents on the AI attempt.

## Settings

Main settings live in `apps/api/.env.example`.

| Setting | Default | Notes |
| --- | --- | --- |
| `CD_GRADING_ENGINE` | `mock` | Use `litellm` only when ready to make real provider calls. |
| `CD_LITELLM_MODEL` | `openai/gpt-5` | Must exist and be enabled in the merged catalog. |
| `CD_LITELLM_TIMEOUT_SECONDS` | `60` | Passed to LiteLLM completion. |
| `CD_LITELLM_MAX_RETRIES` | `2` | Passed to LiteLLM as `num_retries`. |
| `CD_LLM_MODEL_CATALOG_MODE` | `remote_cached` | Controls dynamic upstream catalog fetching. |
| `CD_LLM_MODEL_CATALOG_URL` | LiteLLM GitHub raw price map | Source for model pricing/context metadata. |
| `CD_LLM_MODEL_CATALOG_CACHE_PATH` | `.cache/llm/model-prices.json` | Local upstream cache. |
| `CD_LLM_MODEL_OVERLAY_PATH` | `config/llm-model-overrides.json` | Local model allow-list and product labels. |
| `CD_LLM_MODEL_CATALOG_MAX_AGE_HOURS` | `24` | Staleness threshold for upstream price map. |

LiteLLM provider API keys are read by LiteLLM from its normal provider environment variables, not from the catalog overlay.

## Attempt Metadata

Each run records a `GradingAiAttempt` row with:

- Engine name.
- Model name.
- Attempt status.
- Extraction status.
- Privacy status.
- Safe error code.
- Flags.
- Prompt tokens.
- Completion tokens.
- Total tokens.
- Estimated cost in cents.
- Latency in milliseconds.
- Retry count.

These fields are exposed additively on grading submission API responses as:

- `ai_engine`
- `ai_model`
- `ai_attempt_status`
- `ai_prompt_tokens`
- `ai_completion_tokens`
- `ai_token_count`
- `ai_cost_cents`
- `ai_latency_ms`
- `ai_safe_error`
- `ai_flags`

Existing SQLite dev databases are migrated at startup for the additive attempt metadata columns. This is a small dev migration, not a general migration framework.

## Logging

The backend uses Rich console logging for local operator visibility.

Useful event families:

- `auth.*`: Google OAuth and identity state.
- `google.*`: Classroom, Drive, roster, metadata, and file reads.
- `content.extract.*`: extraction start/status.
- `privacy.*`: pseudonym and scrub status.
- `grading.submission.*`: cache, extraction, privacy, engine-call lifecycle.
- `grading_engine.mock.*`: mock engine request/response.
- `grading_engine.litellm.*`: LiteLLM request/response metadata.
- `litellm.grade.catalog_model`: selected model catalog/pricing metadata.
- `llm_catalog.*`: model catalog load/fetch/cache behavior.

`CD_LOG_PAYLOAD_PREVIEWS=true` allows local text previews in extraction/privacy/grading orchestration logs. The LiteLLM engine itself avoids text previews and raw responses. Turn previews off when you want quieter logs:

```powershell
$env:CD_LOG_PAYLOAD_PREVIEWS="false"
```

## Smoke Testing

Mock smoke test:

```powershell
cd apps/api
$env:CD_GRADING_ENGINE="mock"
uv run python scripts/smoke_litellm_grading.py
```

Real LiteLLM smoke test:

```powershell
cd apps/api
$env:CD_GRADING_ENGINE="litellm"
$env:CD_LITELLM_MODEL="openai/gpt-5"
uv run python scripts/smoke_litellm_grading.py
```

Only run the real smoke test after the matching provider key is configured for LiteLLM.

## Real Classroom Testing Notes

During the first real-data test:

- Backend ran in `CD_GOOGLE_PROVIDER=google`.
- `/api/auth/me` confirmed Google mode and Classroom/Drive scopes.
- Course reads worked.
- Assignment reads worked.
- A real job for `[SÁB]SUPER PÍTON` / `Entrega - Naruto` was created.
- Privacy audit completed with 15 files, 12 passed, 3 blocked image submissions, 0 high-risk files.
- Drafting ran with the mock engine and produced a reviewing job with 12 mock drafts and 3 blocked rows.

The global grading queue timed out against real Classroom data because it currently scans too much submission/Drive metadata. Prefer selecting course and assignment directly until the queue is optimized.

## Safe Tweak Checklist

Before enabling a real model:

1. Confirm `CD_GOOGLE_PROVIDER=google` only when you intend to use real Classroom data.
2. Confirm `CD_GRADING_ENGINE=litellm`.
3. Confirm `CD_LITELLM_MODEL` is enabled in `apps/api/config/llm-model-overrides.json`.
4. Confirm the provider API key is present in the environment expected by LiteLLM.
5. Run the mock smoke test.
6. Run the real LiteLLM smoke test with scrubbed fake text.
7. Run a privacy audit on the target assignment.
8. Review blocked/high-risk rows before drafting.
9. Draft one small assignment first.
10. Inspect token/cost/latency metadata in the resulting attempts.

Do not enable real LLM grading for assignments dominated by unsupported images, PDFs requiring OCR, videos, or archives until extraction support is stronger.
