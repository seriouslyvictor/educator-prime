# Execution Directive: LiteLLM grading — intervention levels, batch mode & cost observability

> **For the implementing agent:** Implement task-by-task, top to bottom. Every task is
> TDD: write the failing test, run it red, implement, run it green, run the full suite,
> commit. Use checkboxes (`- [ ]`) to track. Do **not** make real provider calls — mock
> `classroom_downloader.litellm_engine.litellm.*` as the existing tests do
> (`tests/test_litellm_engine.py`, `tests/test_grading.py`).
>
> **Context:** Builds on the shipped LiteLLM wiring. Companion analysis:
> `docs/litellm-grading-batch-intervention-plan.md`. Run from `apps/api`:
> `uv run --extra dev pytest -q`. A `tests/conftest.py` autouse fixture snapshots and
> restores the `settings` singleton between tests, so tests may mutate
> `get_settings()` directly and rely on automatic restore.
>
> **Decisions locked in:** auto-accept confidence default `0.85` (unflagged rows only);
> batch output = strict JSON-schema array where supported, XML-wrapped JSON fallback;
> batch defaults size `10` / context fraction `0.8`; per-student cost split =
> token-weighted; per-submission parallelization deferred to optional Task 11.

---

## Implementation status — updated 2026-06-05

**Phases 1–3 implemented; full suite green (`66 passed`). Phases 4–5
intentionally deferred (gated until Phase 3 ships so batch can be tested
properly).**

- **Task 1 (rubric_text + policy settings) — done, with deviation.** `rubric_text`
  persisted + dev migration + flows into the engine; `grading_auto_accept_confidence`,
  `grading_batch_mode`, `grading_structured_output` added. **Deviation:** the
  `GradingPolicy`/`policy.py` abstraction was **not** created — the orchestrator and
  engine branch inline on `teacher_loop`/`request_score`. `tests/test_grading_policy.py`
  is therefore intentionally absent. **Deferred:** `grading_batch_max_submissions` /
  `grading_batch_context_fraction` belong to Phase 4 and are not yet added.
- **Task 2 (per-level prompts + nullable score) — done.** `GradingEngineRequest.request_score`
  added; `_build_messages` branches on it (cowrite forbids a numeric grade); strict score
  validation **restored** in `parse_litellm_result(content, request_score=True)` — a
  missing/null/out-of-range score in a scored level now raises `malformed_llm_response`
  instead of silently yielding a scoreless row; `request_score=False` tolerates/withholds
  the score. **Deviation:** types use `list[dict]` rather than the directive's tuple shapes.
- **Task 3 (orchestrator applies policy) — done.** `off` skips the call, `auto`
  auto-accepts only clean high-confidence drafts, `cowrite` withholds the score; criterion
  notes persisted. Negative auto-accept paths (low confidence / flagged) now covered by tests.
- **Task 4 (strict JSON-schema + cached tokens) — done, with deviation.** Schema gated on
  `supports_response_schema` + `grading_structured_output=="auto"`, json_object fallback,
  cached-token capture persisted. **Deviation:** response schema is a hand-written dict, not a
  Pydantic `GradingDraftModel`; OpenAI `prompt_tokens_details.cached_tokens` not captured.
- **Task 5 (authoritative cost + rollups) — done, with deviation.** `completion_cost` with
  catalog fallback; per-job token/cost/time rollups + `grading.job.cost.summary`. **Deviation:**
  cost computed in `grading.py` (not `engine.last_cost_cents`); rollup fields use the plan's
  names `wall_clock_ms` / `submissions_graded` (not `draft_wall_clock_ms` / `graded_submissions`);
  the summary log emits raw token counts but not an explicit cache-hit ratio.
- **Tasks 6–10 (Phases 4–5) — deferred (intentional).** No `class_batch` path, batch planner,
  `grade_batch`, batch columns, docs, or smoke extension yet.

---

## Architecture summary

- **`policy.py` (new):** derive a `GradingPolicy` from `(teacher_loop, rubric_mode,
  settings)` that the orchestrator and engine branch on. This is what makes the UI's
  intervention spectrum real.
- **`grading_engine.py`:** `GradingEngineRequest` gains rubric/policy fields; add a
  `GradingEngineResult.score: float | None` (cowrite has no score); add an optional
  `grade_batch()` capability.
- **`litellm_engine.py`:** per-level prompt templates; strict JSON-schema output when
  supported; cache-friendly message ordering; cached-token capture; batch prompt
  builder + parser; `litellm.completion_cost` for authoritative cost.
- **`grading.py`:** orchestrator applies policy (`off` skips the call, `auto`
  auto-accepts, `cowrite` stores reasoning); job-level cost/token/time rollups; the
  `class_batch` path with a context guard and a per-item quality-guard fallback.
- **`models.py` / `schemas.py` / `database.py`:** additive columns + dev migrations +
  additive API fields.
- **`settings.py`:** new env knobs.

Privacy invariant is unchanged throughout: the engine only ever sees scrubbed,
pseudonymized content; blocked/high-risk submissions never enter a batch.

---

# PHASE 1 — Make the teacher-intervention spectrum real

## Task 1: Persist `rubric_text`, add policy settings & `GradingPolicy`

**Files:** `settings.py`, `models.py`, `database.py`, `schemas.py` (no change needed —
`GradingJobCreate.rubric_text` already exists), `main.py`, new `policy.py`,
`tests/test_grading_policy.py`, `tests/test_grading.py`.

- [ ] **Step 1 — Failing test for settings + policy.** *(Not done — `policy.py`
  abstraction was intentionally inlined into the orchestrator/engine; no
  `tests/test_grading_policy.py`. See Implementation status.)* Create
  `tests/test_grading_policy.py`:
  ```python
  import os
  os.environ.setdefault("CD_DATABASE_URL", "sqlite:///:memory:")
  os.environ.setdefault("CD_GOOGLE_PROVIDER", "mock")

  from classroom_downloader.settings import Settings
  from classroom_downloader.policy import policy_for

  def test_policy_settings_defaults() -> None:
      s = Settings()
      assert s.grading_auto_accept_confidence == 0.85
      assert s.grading_batch_mode == "per_submission"

  class _Job:
      def __init__(self, loop, mode): self.teacher_loop, self.rubric_mode = loop, mode

  def test_policy_off_skips_model() -> None:
      p = policy_for(_Job("off", "infer"), Settings())
      assert p.calls_model is False

  def test_policy_cowrite_withholds_score() -> None:
      p = policy_for(_Job("cowrite", "infer"), Settings())
      assert p.calls_model is True and p.request_score is False and p.auto_accept is False

  def test_policy_auto_accepts() -> None:
      p = policy_for(_Job("auto", "infer"), Settings())
      assert p.auto_accept is True and p.auto_accept_confidence == 0.85

  def test_policy_approve_default() -> None:
      p = policy_for(_Job("approve", "brief"), Settings())
      assert p.calls_model and p.request_score and not p.auto_accept
  ```

- [ ] **Step 2 — Run red.** *(N/A — see Step 1.)* `uv run --extra dev pytest tests/test_grading_policy.py -q`.

- [x] **Step 3 — Add settings** (`settings.py`, near the grading block) — *3 of 5 added;
  `grading_batch_max_submissions` / `grading_batch_context_fraction` deferred to Phase 4:*
  ```python
  grading_auto_accept_confidence: float = 0.85
  grading_batch_mode: Literal["per_submission", "class_batch"] = "per_submission"
  grading_batch_max_submissions: int = 10
  grading_batch_context_fraction: float = 0.8
  grading_structured_output: Literal["auto", "json_object"] = "auto"
  ```

- [ ] **Step 4 — Create `policy.py`:** *(Not done — intentionally inlined; behavior
  is equivalent. The `request_score`/`auto_accept`/`calls_model` logic lives in
  `grading.py` + `litellm_engine.py`.)*
  ```python
  from __future__ import annotations
  from dataclasses import dataclass

  @dataclass(frozen=True)
  class GradingPolicy:
      teacher_loop: str
      rubric_mode: str
      calls_model: bool
      request_score: bool
      auto_accept: bool
      auto_accept_confidence: float

  def policy_for(job, settings) -> GradingPolicy:
      loop = job.teacher_loop
      return GradingPolicy(
          teacher_loop=loop,
          rubric_mode=job.rubric_mode,
          calls_model=loop != "off",
          request_score=loop != "cowrite",
          auto_accept=loop == "auto",
          auto_accept_confidence=settings.grading_auto_accept_confidence,
      )
  ```

- [x] **Step 5 — Persist `rubric_text`.** Add `rubric_text: str | None = None` to
  `GradingJob` (`models.py`). Add it to the dev migration in `database.py`
  (`_ensure_grading_job_columns`, mirroring `_ensure_cache_columns`; register it in
  `ensure_sqlite_dev_migrations`). In `main.py::create_grading_job`, pass
  `rubric_text=payload.rubric_text` into the `GradingJob(...)` constructor (line ~713).

- [x] **Step 6 — Test that create persists rubric_text.** Add to `tests/test_grading.py`
  a test that POSTs a job with `rubric_text` and asserts the persisted job carries it
  (read the job row via a session, or expose `rubric_text` on `GradingJobRead` and
  assert through the API — do both: add `rubric_text` to `GradingJobRead` and
  `grading_job_snapshot`).

- [x] **Step 7 — Run green + full suite + commit** (`Persist rubric_text and add grading policy`).
  *(Shipped as `Implement grading intervention levels`.)*

## Task 2: Per-level prompts & nullable score in the engine

**Files:** `grading_engine.py`, `litellm_engine.py`, `tests/test_litellm_engine.py`.

- [x] **Step 1 — Failing engine tests.** *(Added 2026-06-05.)* In `tests/test_litellm_engine.py`, add:
  - a cowrite request (`request_score=False`) produces a system/user prompt that
    instructs "no numeric grade" and `parse_litellm_result(..., request_score=False)`
    accepts a payload with `score` absent/null and returns `score is None`.
  - a request carrying `rubric_text` / `criteria` renders them into the messages.
  - the static instruction block is the **first** message (cache-prefix ordering).

- [x] **Step 2 — Run red.**

- [x] **Step 3 — Extend request/result types** (`grading_engine.py`) — *`request_score`
  field added; `score`/`criterion_notes` already nullable; shapes use `list[dict]`, not tuples:*
  ```python
  @dataclass(frozen=True)
  class GradingEngineRequest:
      ...                      # existing fields
      request_score: bool = True
      rubric_text: str | None = None
      criteria: tuple[tuple[str, int], ...] = ()   # (name, weight)
  @dataclass(frozen=True)
  class GradingEngineResult:
      score: float | None      # was float — now nullable for cowrite
      confidence: float
      feedback: str
      flags: list[str]
      criterion_notes: tuple[tuple[str, str], ...] = ()
  ```

- [x] **Step 4 — Per-level prompt** (`litellm_engine.py::_build_messages`). Branch on
  `request_score`: the cowrite template forbids a numeric grade and asks for reasoning +
  `criterion_notes` only; the scored template keeps today's shape. Put the static
  system + rubric/orientation (`rubric_text`, criteria, required-shape) as the **leading
  message(s)**; only the per-student `submission_text` varies at the tail. Make
  `required_json_shape.score` `"number 0-100 or null"` when `request_score` is False.

- [x] **Step 5 — Parser tolerates null score** (`parse_litellm_result`). *(Fixed
  2026-06-05: `request_score` param restores strict validation when True.)* Add a
  `request_score: bool = True` param: when False, accept missing/null `score` and return
  `score=None`; when True, keep strict validation. Always parse `criterion_notes`
  defensively. Keep all malformed paths raising `ValueError("malformed_llm_response")`.

- [x] **Step 6 — Green + full suite + commit** (`Add per-level grading prompts and nullable score`).
  *(Prompts/score shipped in `Implement grading intervention levels`; strict validation + tests added 2026-06-05.)*

## Task 3: Orchestrator applies the policy

**Files:** `grading.py`, `tests/test_grading.py`.

- [x] **Step 1 — Failing orchestration tests** (mock `litellm.completion`) — *off/auto/cowrite
  shipped earlier; the negative auto paths (low confidence / flagged → not reviewed) added 2026-06-05:*
  - `teacher_loop="off"` → draft makes **no** engine call, creates **no**
    `GradingAiAttempt`, submission `ai_score is None`, job still reaches a reviewing/
    completed state with rows present.
  - `teacher_loop="auto"` with a mocked high-confidence (`>=0.85`), no-flags response →
    submission `reviewed is True`, `final_score == ai_score`.
  - `teacher_loop="auto"` with confidence `<0.85` **or** a flag → `reviewed is False`.
  - `teacher_loop="cowrite"` → `ai_score is None`, `feedback` populated, `reviewed is False`.

- [x] **Step 2 — Run red.**

- [x] **Step 3 — Build the request with policy** in `_draft_submission`
  (`grading.py:570`): compute `policy = policy_for(job, get_settings())`. If
  `not policy.calls_model`: skip the engine, do **not** call `_record_attempt`, leave
  `submission.ai_score=None`, `reviewed=False`, `error=None`, and return. Otherwise pass
  `request_score=policy.request_score`, `rubric_text=job.rubric_text`, and the job's
  criteria into `GradingEngineRequest`.

- [x] **Step 4 — Apply outcome by level** after a `completed` result:
  - cowrite (`not policy.request_score`): set `ai_score=None`, keep `confidence`,
    `feedback=result.feedback`, `final_score=None`, `reviewed=False`.
  - auto (`policy.auto_accept`): if `result.score is not None and not flags and
    result.confidence >= policy.auto_accept_confidence`: `reviewed=True`,
    `final_score=result.score`. Else leave as a normal draft.
  - approve: today's behavior.
  - Persist `criterion_notes` onto the job's `GradingCriterion` rows where names match.

- [x] **Step 5 — Update `_refresh_counts`** so `reviewed_submissions`/status reflect
  auto-accepted rows (it already counts `reviewed`; verify auto path increments it).

- [x] **Step 6 — Green + full suite + commit** (`Wire teacher-intervention levels into drafting`).
  *(Shipped in `Implement grading intervention levels`.)*

---

# PHASE 2 — Structured output + prompt caching

## Task 4: Strict JSON-schema output, cached-token capture

**Files:** `litellm_engine.py`, `models.py`, `database.py`, `schemas.py`, `grading.py`,
`tests/test_litellm_engine.py`, `tests/test_grading.py`.

- [x] **Step 1 — Failing tests:** *(schema + cached-token tests shipped earlier; the
  json_object fallback test added 2026-06-05.)*
  - When the catalog model has `supports_response_schema=True` and
    `grading_structured_output="auto"`, the engine passes
    `response_format={"type":"json_schema", ...}` (assert the captured kwarg) and sets
    `litellm.enable_json_schema_validation=True`.
  - When unsupported, it falls back to `{"type":"json_object"}` (today's behavior).
  - Usage carrying `cache_read_input_tokens`/`cache_creation_input_tokens` is captured
    into `last_usage` and persisted as `cached_prompt_tokens`/`cache_write_tokens`.

- [x] **Step 2 — Run red.**

- [x] **Step 3 — Define Pydantic output models** (`litellm_engine.py`) — *deviation: implemented
  as a hand-written JSON-schema dict, not a Pydantic `GradingDraftModel` (equivalent for the schema path):*
  `GradingDraftModel` (`score: float | None`, `confidence: float`, `feedback: str`,
  `criterion_notes: list[...]`, `flags: list[str]`). Build `response_format` from it
  with `strict=True` when `self.catalog_model.supports_response_schema` and
  `settings.grading_structured_output == "auto"`; else `{"type":"json_object"}`. Set
  `litellm.enable_json_schema_validation = True` once at module import or in `__init__`.

- [x] **Step 4 — Capture cached tokens.** *(Deviation: OpenAI `prompt_tokens_details.cached_tokens`
  not yet captured — only Anthropic-style `cache_read_input_tokens`/`cache_creation_input_tokens`.)*
  Extend `_usage_dict` to also read
  `cache_read_input_tokens` and `cache_creation_input_tokens` (and OpenAI's
  `prompt_tokens_details.cached_tokens` if present). Surface them on `last_usage`.

- [x] **Step 5 — Persist new attempt columns.** Add
  `cached_prompt_tokens: int | None`, `cache_write_tokens: int | None` to
  `GradingAiAttempt` (`models.py`), to the dev migration
  (`_ensure_grading_ai_attempt_columns` required_columns), to `_record_attempt` +
  `_attempt_metadata`, and additively to `GradingSubmissionRead` + `_submission_read`
  (`ai_cached_prompt_tokens`, `ai_cache_write_tokens`).

- [x] **Step 6 — Green + full suite + commit** (`Add strict JSON-schema output and cached-token capture`).
  *(Shipped in `Add structured LiteLLM output metadata`.)*

---

# PHASE 3 — Cost, token & time observability

## Task 5: Authoritative cost + per-job rollups + summary

**Files:** `litellm_engine.py`, `llm_catalog.py`, `models.py`, `database.py`,
`schemas.py`, `grading.py`, `tests/test_grading.py`.

- [x] **Step 1 — Failing tests:** *(Done — rollup fields shipped as `wall_clock_ms` /
  `submissions_graded`, not the `draft_wall_clock_ms` / `graded_submissions` named here.)*
  - After a litellm draft of a multi-submission job, `GradingJobRead` exposes
    `total_prompt_tokens`, `total_completion_tokens`, `total_cached_tokens`,
    `total_cost_cents`, `draft_wall_clock_ms`, `graded_submissions` with the expected
    summed values (from mocked usage).
  - A `grading.job.cost.summary` event is emitted on draft completion (assert via a
    caplog or a spy — or just assert the rollup fields; keep it simple).

- [x] **Step 2 — Run red.**

- [x] **Step 3 — Authoritative cost.** *(Deviation: computed in `grading.py`
  (`_completion_cost_cents` reads `engine.last_response`), not as `engine.last_cost_cents`.)*
  In `litellm_engine.grade`, after the call,
  compute `self.last_cost_cents = litellm.completion_cost(completion_response=response)
  * 100` inside a try/except; on failure fall back to `estimate_cost_cents`. Surface
  `last_cost_cents`; have `_attempt_metadata` prefer it over the estimate.

- [x] **Step 4 — Job rollup fields.** *(Deviation: the `grading.job.cost.summary` log
  emits raw token counts but not an explicit cache-hit ratio.)* Add to `GradingJob` (`models.py`) +
  dev migration: `total_prompt_tokens`, `total_completion_tokens`,
  `total_cached_tokens`, `total_cost_cents` (float), `draft_wall_clock_ms`,
  `graded_submissions`, `batch_mode`. In `draft_grading_job` (`grading.py:154`), wrap the
  submission loop with a `time.monotonic()` start/stop, then after the loop sum the
  latest attempts for the job and set the rollups; emit `grading.job.cost.summary`
  (totals + cache-hit ratio = cached/(prompt+cached)). Expose all rollups additively on
  `GradingJobRead` + `grading_job_snapshot`.

- [x] **Step 5 — Green + full suite + commit** (`Add authoritative cost and per-job grading rollups`).
  *(Shipped in `Add grading cost rollups`.)*

---

# PHASE 4 — `class_batch` mode (env-gated)

> ⏸ **Deferred (intentional)** — gated until Phase 3 ships so batch can be tested
> properly. Tasks 6–8 below are not yet implemented.

## Task 6: Batch prompt builder + parser

**Files:** `litellm_engine.py`, `tests/test_litellm_engine.py`.

- [ ] **Step 1 — Failing tests:**
  - `build_batch_messages([req_a, req_b])` wraps each scrubbed submission in
    `<submission id="student_001">…</submission>` with a shared rubric/orientation
    prefix, and instructs one result per id.
  - `parse_litellm_batch(content, expected_ids)` parses a JSON array (schema mode) **and**
    an XML-wrapped JSON fallback, returning `{student_label: GradingEngineResult}`;
    missing/malformed ids come back as errors, not exceptions.

- [ ] **Step 2 — Run red.**

- [ ] **Step 3 — Implement** `build_batch_messages`, `parse_litellm_batch`, and
  `GradingBatchItem` (`submission_id`, `student_label`, `result: GradingEngineResult |
  None`, `error: str | None`, `token_share: int`). Output schema = a strict JSON-schema
  **array** of per-id objects when supported; otherwise instruct the model to emit
  `<results>…</results>` containing the JSON array (parse defensively). Reuse
  `parse_litellm_result` per item.

- [ ] **Step 4 — Green + commit** (`Add class-batch prompt builder and parser`).

## Task 7: Context-size guard + greedy packer

**Files:** `litellm_engine.py` (or new `batch_planner.py`), `tests/test_batch_planner.py`.

- [ ] **Step 1 — Failing tests:**
  - `plan_batches(model, requests, settings)` returns chunks whose estimated prompt
    tokens + output reserve stay under `max_input_tokens * grading_batch_context_fraction`
    and never exceed `grading_batch_max_submissions` per chunk.
  - A single submission too large for the window is returned as its own
    `oversize`-flagged chunk (routed to per-submission/`too_large` by the orchestrator).
  - Token counting uses `litellm.token_counter` (monkeypatch it in the test to a
    deterministic fake).

- [ ] **Step 2 — Run red.**

- [ ] **Step 3 — Implement the planner:** per-request token estimate via
  `litellm.token_counter(model, text=submission_text)`; `ctx =
  catalog.max_input_tokens or litellm.get_max_tokens(model)`; `reserve =
  max_output_tokens * n + margin`. Greedy bin-pack respecting both the token budget and
  the size cap; emit a `grading.batch.plan` log (model, ctx, est_prompt_tokens, reserve,
  n, chunk_count) **before** any call. Record each request's `token_share` for cost
  splitting.

- [ ] **Step 4 — Green + commit** (`Add batch context-size guard and packer`).

## Task 8: Orchestrator batch path + quality guard + cost attribution

**Files:** `grading_engine.py` (add optional `grade_batch`), `litellm_engine.py`,
`grading.py`, `tests/test_grading.py`.

- [ ] **Step 1 — Failing tests** (mock `litellm.completion` to return a batch payload):
  - With `CD_GRADING_BATCH_MODE=class_batch`, a job drafts all submissions in **one**
    mocked call; each submission gets its result; one `batch_id` is shared and
    `batch_size` is set on attempts.
  - **Quality guard:** if the batch response omits one id (or returns it below the
    confidence floor / malformed), that submission is **re-graded individually** via a
    second mocked single call and still ends up graded.
  - **Cost attribution:** the batch's total cost (mocked `completion_cost`) is split
    across submissions token-weighted by `token_share`; the job rollup equals the batch
    total.
  - Blocked/high-risk submissions are excluded from the batch and recorded as blocked.

- [ ] **Step 2 — Run red.**

- [ ] **Step 3 — Add `grade_batch`** to `LiteLlmGradingEngine`: assemble via
  `build_batch_messages`, call `litellm.completion` once, capture usage + cost, parse via
  `parse_litellm_batch`, return `list[GradingBatchItem]` plus shared
  `last_usage`/`last_cost_cents`/`last_latency_ms`. Leave `MockGradingEngine` without it
  (orchestrator falls back to per-submission when absent).

- [ ] **Step 4 — Branch in `draft_grading_job`:** when `settings.grading_batch_mode ==
  "class_batch"` and the engine has `grade_batch` and policy `calls_model`:
  1. Build the gradeable set (scrub + privacy-block filtering reused from
     `_draft_submission`; blocked rows recorded as today).
  2. `plan_batches(...)` → chunks (Task 7).
  3. For each chunk call `grade_batch`; map results by `student_label`.
  4. **Quality guard:** any missing/malformed/low-confidence item → call the existing
     single-submission path for that submission.
  5. Persist each submission applying the **same policy outcome logic** as Task 3
     (auto/cowrite/approve), and record one attempt per submission with
     `batch_id`/`batch_size` and a **token-weighted** slice of the batch cost/tokens.
  6. Roll up to the job (Phase 3) with `batch_mode="class_batch"`.
  - `off` policy still skips entirely (no batch). `per_submission` mode keeps Phase-1
    behavior unchanged.

- [ ] **Step 5 — Add `batch_id`, `batch_size`** to `GradingAiAttempt` + dev migration +
  `_record_attempt`; optionally surface on `GradingSubmissionRead`.

- [ ] **Step 6 — Green + full suite + commit** (`Add class-batch drafting with quality guard and cost split`).

---

# PHASE 5 — Docs & smoke

> ⏸ **Deferred (intentional)** — follows Phase 4. Task 9 not yet implemented.

## Task 9: Documentation + class-batch smoke

**Files:** `docs/ai-grading-layer.md`, `apps/api/scripts/smoke_litellm_grading.py`
(extend), `README.md`, `apps/api/.env.example`.

- [ ] **Step 1 — Update `ai-grading-layer.md`:** document the intervention-level →
  behavior table, the two modes, the context guard, the cost/token/time rollups, the
  new env knobs, and the safe-tweak checklist additions ("inspect job cost summary",
  "verify cache-hit ratio", "start class_batch on one small assignment").
- [ ] **Step 2 — Extend the smoke script** with a `class_batch` path (mock-safe) and a
  per_submission path; print the job cost summary.
- [ ] **Step 3 — Document all new `CD_GRADING_*` settings** in `.env.example` + README.
- [ ] **Step 4 — Commit** (`Document grading intervention levels, batch mode, and cost rollups`).

## Task 10 (optional, deferred): parallelize `per_submission`

- [ ] Add `CD_GRADING_CONCURRENCY` and optionally use `litellm.batch_completion` to run
  per-submission calls concurrently (wall-clock only). Keep behind a flag; skip unless
  explicitly requested.

## Task 11 (TODO, future): in-app model picker via `get_valid_models`

> Spawned 2026-06-05 from the provider-key health-check work. Today `CD_LITELLM_MODEL`
> selects the single active grading model; the overlay (`config/llm-model-overrides.json`)
> enables several (gpt-5, gemini, grok, deepseek) but teachers can't choose per job. This
> augments — does **not** replace — the static catalog (which stays the source of truth for
> cost/context/`supports_response_schema`).

- [ ] **Backend reachability helper** (`grading_engine.py` / `llm_catalog.py`): wrap
  `litellm.get_valid_models(check_provider_endpoint=True)` (cached, ~5–15 min TTL; it hits
  the provider) to compute which **enabled** catalog models are actually reachable with the
  present keys. Reuse `_missing_provider_keys` for the offline "key present" signal.
- [ ] **`GET /api/grading/models`** → list of enabled `grading_draft` catalog models, each
  annotated `{ id, display_name, provider, supports_response_schema, key_present: bool,
  reachable: bool | null }`. `reachable` is null when the provider endpoint isn't probed.
- [ ] **UI dropdown in `GraderSetup`**: populate from `/api/grading/models`; disable/flag
  models without a key (lean on the existing health banner copy). Default to
  `CD_LITELLM_MODEL`.
- [ ] **Per-job model**: add `GradingJob.model` (additive column + dev migration) so the
  chosen model is persisted and passed into `get_grading_engine`/the request instead of the
  global setting. `inspect_grading_readiness` should accept an explicit model override.
- [ ] Tests: reachability helper (monkeypatch `get_valid_models`), endpoint annotation
  shape, and draft using a per-job model. Keep the catalog as metadata source of truth.
- [ ] Note: this is the check that would have auto-caught the `openai/gemini-3.1-flash-lite`
  misconfiguration (wrong prefix + not enabled) at setup time.

---

## Final verification

- [x] `cd apps/api && uv run --extra dev pytest -q` — all green (`66 passed`, 2026-06-05).
  *(Note: a local `apps/api/.env` with `CD_GOOGLE_PROVIDER=google` forces the real provider
  into the cached settings singleton and fails ~27 tests with `FileNotFoundError: .tokens/...`;
  run with `CD_GOOGLE_PROVIDER=mock` — CI has no `.env`, so its default `mock` applies.)*
- [x] `cd apps/web && pnpm build` — additive schema fields don't break TS *(green 2026-06-05,
  during the health-check work)*.
- [ ] Mock smoke: `per_submission` and `class_batch` both print a job cost summary.
  *(Deferred — `class_batch` is Phase 4.)*
- [x] `git log --oneline` shows per-phase commits (`Implement grading intervention levels`,
  `Add structured LiteLLM output metadata`, `Add grading cost rollups`) — compressed from the
  5 prescribed per-task commits into 3 per-phase commits.

## Guardrails (every task)

- No real provider calls in tests; always mock `litellm.*`.
- Privacy boundary unchanged: engine sees only scrubbed/pseudonymized content; blocked
  rows never enter a batch; never log raw submission text or raw model responses.
- All new DB columns are additive with a startup dev migration (mirror
  `database.py` patterns); no destructive migrations.
- All API fields are additive; existing fields keep their names and meaning.
