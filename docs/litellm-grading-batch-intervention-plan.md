# Implementation Plan: LiteLLM AI grading — intervention levels, batch mode & cost observability

> Status: **Planned — not yet started.**
> Scope: `apps/api` grading engine + orchestration. Builds on the shipped LiteLLM
> wiring (`docs/superpowers/plans/2026-05-27-litellm-grading-wiring.md`,
> `docs/ai-grading-layer.md`).
> Goal: send a scrubbed payload, get a grade back, with **gradual teacher
> intervention** (fully automated → co-pilot only); add an **env-selectable batch
> mode** (whole class in one XML-delimited prompt) with a **context-size guard**;
> and make **cost, token usage, and time-to-complete** first-class in observability.

---

## 1. Assessment of what exists today

The pipeline is solid and privacy-first (download → cache → extract → pseudonymize →
scrub → block → engine → validate → persist). The LiteLLM engine works, validates a
JSON shape, and already records per-attempt `prompt_tokens`, `completion_tokens`,
`token_count`, `cost_cents`, `latency_ms` on `GradingAiAttempt`.

**The central gap:** the UI advertises a spectrum of teacher intervention, but the
backend treats every level identically.

- UI `TeacherLoopMode = "auto" | "approve" | "cowrite" | "off"` and
  `RubricMode = "infer" | "brief" | "structured" | "saved" | "calibrate"`
  (`apps/web/src/types.ts:158-160`, copy in `grader/GraderSetup.tsx:8-30`).
- These are stored on `GradingJob.rubric_mode` / `.teacher_loop`
  (`models.py:87-88`) and **dumped verbatim into the prompt payload**
  (`litellm_engine.py:_build_messages`), but nothing branches on them:
  - `auto` does not auto-accept high-confidence drafts; every row still lands as
    `reviewed=False`.
  - `cowrite` still asks the model for a `score`; it should withhold the score and
    return reasoning only.
  - `off` still calls the engine; it should prepare the table with **no** model call.
  - `structured`/`brief`/`saved`/`calibrate` don't change the rubric the model sees.
- **`rubric_text` is collected and sent by the UI** (`api.ts:145`, `GraderSetup`),
  **but `GradingJob` has no column to store it** and the engine never receives it —
  so "Orientação simples / brief" is currently a no-op. `GradingCriterion` rows exist
  (`models.py:98`) but `criterion_notes` are requested and discarded
  (per `ai-grading-layer.md`).

Other gaps relevant to this request:
- Grading is strictly **one API call per submission** (`_draft_submission`,
  `grading.py:496`). No batch path.
- Cost is **estimated** from catalog token prices (`estimate_cost_cents`), not
  LiteLLM's authoritative `completion_cost`. No **cached-token** capture (prompt
  caching), and no **job-level rollup** (total cost / tokens / wall-clock for a class).
- Output uses `response_format={"type":"json_object"}` even though the catalog
  already tracks `supports_response_schema` per model — strict JSON-schema is
  available and would make parsing (especially batch) far more reliable.

## 2. LiteLLM capabilities to lean on (from current docs)

- **Strict structured output:** `response_format={"type":"json_schema",
  "json_schema":{...},"strict":true}` (or pass a Pydantic model), plus
  `litellm.enable_json_schema_validation=True`. Gate on
  `litellm.supports_response_schema(model)` / our catalog `supports_response_schema`.
  [json_mode](https://docs.litellm.ai/docs/completion/json_mode)
- **Pre-send token counting:** `litellm.token_counter(model=..., messages=...)`
  (tiktoken fallback) and `litellm.get_max_tokens(model)` / `litellm.get_model_info(model)`
  for the context window — the basis of the batch context guard.
  [token_usage](https://docs.litellm.ai/docs/completion/token_usage)
- **Authoritative cost:** `litellm.completion_cost(completion_response=...)` and
  `litellm.cost_per_token(...)` return USD for a call; usage carries
  `prompt_tokens`/`completion_tokens` and, when caching applies,
  `cache_creation_input_tokens` / `cache_read_input_tokens`.
  [token_usage](https://docs.litellm.ai/docs/completion/token_usage)
- **Parallel batch (note the distinction):** `litellm.batch_completion(...)` runs N
  **separate** calls concurrently — it cuts wall-clock time, **not** token cost. The
  user's "batch" is different: **one prompt containing the whole class**. We will
  implement the single-prompt class batch ourselves and *optionally* use
  `batch_completion` to parallelize per-submission mode.
  [batching](https://docs.litellm.ai/docs/completion/batching)

---

## 3. Wire the teacher-intervention spectrum (the core ask)

Make `teacher_loop` actually change behavior. Introduce a `GradingPolicy` derived from
`(teacher_loop, rubric_mode, confidence thresholds)` consumed by the orchestrator:

| Level | Model call | Output requested | Persisted state |
| --- | --- | --- | --- |
| `auto` | yes | score + confidence + feedback | auto-accept (`reviewed=True`) when `confidence >= CD_GRADING_AUTO_ACCEPT_CONFIDENCE` **and** no flags; otherwise leave for review and flag |
| `approve` (default) | yes | score + confidence + feedback | draft, `reviewed=False` (today's behavior) |
| `cowrite` | yes | **reasoning + criterion_notes only, no score** | `ai_score=None`, feedback holds reasoning, teacher writes the grade |
| `off` | **no** | — | prepare submission rows only; no `GradingAiAttempt`, no cost |

- The prompt builder selects a system/template per level (e.g. cowrite explicitly
  forbids a numeric grade; auto asks for a calibrated confidence).
- `auto` auto-accept threshold is an env knob; flagged/blocked rows never auto-accept.
- Surface the resulting state so the existing review UI's "review only flagged"
  (`auto`) and "AI shows reasoning" (`cowrite`) copy becomes truthful.

**Rubric wiring (prerequisite for meaningful grades):**
- Add `GradingJob.rubric_text` (persist the brief) + a small dev migration.
- Feed `rubric_text` (brief/saved), `GradingCriterion` rows with weights (structured),
  or calibration exemplars (calibrate) into the prompt as a **stable prefix** (see
  caching, §6). `infer` keeps today's behavior.
- Persist `criterion_notes` from the response onto criteria (stop discarding them).

---

## 4. Two execution modes via env: `per_submission` vs `class_batch`

Add `CD_GRADING_BATCH_MODE: Literal["per_submission","class_batch"] = "per_submission"`.

### 4a. `per_submission` (default, current behavior, hardened)
- One call per student. Strongest grading fidelity; best prompt-cache hit rate (static
  rubric prefix reused across calls). Optionally parallelize with
  `litellm.batch_completion` to cut wall-clock (a separate `CD_GRADING_CONCURRENCY`).

### 4b. `class_batch` (new — cost reduction when input caching fails)
One API call grades many students:
- **Prompt shape:** shared system + orientation/rubric once, then each scrubbed
  submission wrapped in unambiguous XML carrying the pseudonymous id, e.g.
  `<submission id="student_001"> …scrubbed text… </submission>`, with explicit
  "grade each submission independently; output one result per id" instructions.
- **Output shape:** strict JSON-schema array (or XML-wrapped JSON) keyed by
  `student_label`. Parse, map each result to its submission by id, validate per item.
- **Privacy unchanged:** blocked/high-risk submissions are filtered out *before*
  assembly and recorded as blocked exactly as today; only scrubbed content enters the
  batch.
- **Why it saves money:** amortizes the shared rubric/orientation tokens across N
  students in a single input instead of paying for them N times. This matters most
  **when prompt caching is unavailable or cold** (provider without caching, expired
  cache, first call) — the per-submission path leans on caching for the same saving.

**The quality cost (must be managed):** one long prompt invites attention dilution,
position bias, cross-contamination between students, truncated reasoning, and weaker
per-student calibration. Mitigations:
- Cap students per call (`CD_GRADING_BATCH_MAX_SUBMISSIONS`), chunk the class into
  sub-batches.
- Strong delimiters + per-id required schema + low temperature.
- **Quality guard:** any id missing from the response, failing validation, or below a
  confidence floor is **automatically re-graded individually** (`per_submission`
  fallback for that student), so batch never silently degrades a grade.
- Keep `class_batch` opt-in and documented as "cheaper, slightly lower fidelity."

## 5. Context-size precalculation (gate before sending — required for batch)

Before any `class_batch` call:
1. Assemble candidate messages for the chunk.
2. `prompt_tokens = litellm.token_counter(model, messages=...)`.
3. `ctx = catalog.max_input_tokens or litellm.get_max_tokens(model)`;
   `reserve = max_output_per_student * n + safety_margin`.
4. If `prompt_tokens + reserve > ctx * CD_GRADING_BATCH_CONTEXT_FRACTION` (e.g. 0.8),
   **split the chunk** (binary/greedy pack) and recompute; if a *single* submission
   can't fit, route it to `per_submission` (or block as `too_large`).
5. Log the computed budget (`grading.batch.plan`: model, ctx, est_prompt_tokens,
   reserve, n, chunks) so operators see the packing decision before spend.

A greedy bin-packer over per-submission token estimates yields the chunk set; the guard
guarantees we never overflow context or starve the output budget.

## 6. Structured output + prompt caching upgrades (both modes)

- **Strict JSON schema** when `model.supports_response_schema`: define Pydantic models
  (`GradingDraft`, `GradingBatchResult`) and pass them as `response_format` with
  `strict=true` + `litellm.enable_json_schema_validation=True`; fall back to today's
  `json_object` for models without support. Reduces `malformed_llm_response` and makes
  batch parsing dependable.
- **Cache-friendly message layout:** put the static system + rubric/orientation as a
  stable leading block and only vary the per-student tail. For providers needing
  explicit breakpoints (Anthropic), add `cache_control`. Capture
  `cache_read_input_tokens` / `cache_creation_input_tokens` from usage so we can *see*
  whether caching is actually working (directly informs the batch-vs-per-submission
  cost decision).

## 7. Observability: cost, tokens, time-to-complete (explicit asks)

**Per attempt** (extend `GradingAiAttempt`): keep existing fields; add
`cached_prompt_tokens`, `cache_write_tokens`, `batch_id`, `batch_size`, and replace the
estimated cost with `litellm.completion_cost(...)` (catalog estimate as fallback).

**Per job (new `GradingJobCostRollup` or fields on `GradingJob`):**
`total_prompt_tokens`, `total_completion_tokens`, `total_cached_tokens`,
`total_cost_cents`, `wall_clock_ms` (draft start→finish), `submissions_graded`,
`engine`, `mode`, `model`. Surface on the job/wrap API so the "wrap-up" screen can show
**class cost, tokens, and time**.

**Logging events** (align with the logging plan's taxonomy):
- `grading.batch.plan` (context budget & chunking), `grading.batch.request` /
  `.response` (n, usage, latency), `grading.batch.item_fallback` (quality-guard
  re-grades).
- `grading.job.cost.summary` at draft completion: totals for cost/tokens/time +
  cache-hit ratio. This is the one line an operator greps to answer "what did grading
  this class cost and how long did it take?"
- Continue to **never** log raw submission text or raw model responses.

---

## 8. Settings (new)

```
CD_GRADING_BATCH_MODE=per_submission        # per_submission | class_batch
CD_GRADING_BATCH_MAX_SUBMISSIONS=10         # cap students per class_batch call
CD_GRADING_BATCH_CONTEXT_FRACTION=0.8       # max share of context window to fill
CD_GRADING_CONCURRENCY=4                     # parallel calls in per_submission mode
CD_GRADING_AUTO_ACCEPT_CONFIDENCE=0.85       # auto-loop auto-accept threshold
CD_GRADING_STRUCTURED_OUTPUT=auto            # auto (use schema if supported) | json_object
```
Reuse existing `CD_GRADING_ENGINE`, `CD_LITELLM_MODEL`, timeout/retries, catalog
settings.

## 9. Data-model changes (additive + dev migrations)

- `GradingJob`: `+ rubric_text`, `+ batch_mode`, cost/token/time rollup fields.
- `GradingAiAttempt`: `+ cached_prompt_tokens`, `+ cache_write_tokens`, `+ batch_id`,
  `+ batch_size`.
- Wire columns into the existing startup dev-migration (`database.py
  _ensure_*_columns`) the same way Tier-3 caching did.

---

## 10. Phased delivery

1. **Phase 1 — Intervention levels (no batch).** `GradingPolicy`, per-level prompts,
   `off` skips the call, `auto` auto-accept, `cowrite` no-score, persist+use
   `rubric_text`/criteria. Highest user value; unblocks the UI promises.
2. **Phase 2 — Structured output + caching.** Pydantic schemas, schema-gated
   `response_format`, cache-friendly layout, capture cached tokens. Reliability + cost
   visibility groundwork.
3. **Phase 3 — Cost/time observability.** `completion_cost`, per-job rollups,
   `grading.job.cost.summary`, expose on wrap API. Answers the cost/token/time ask
   independently of batch.
4. **Phase 4 — `class_batch` mode.** XML assembly, batch schema + parser, context
   guard (§5), quality-guard fallback, per-item cost attribution. Gated behind the env
   flag and the context calculation.
5. **Phase 5 — Docs + smoke.** Extend `ai-grading-layer.md`, add a `class_batch`
   smoke script, document the cost/quality tradeoff and the safe-tweak checklist.

Each phase: TDD against mocked `litellm.completion` (the repo already mocks it in
`test_grading.py` / `test_litellm_engine.py`), full `pytest`, no real provider calls in
CI.

## 11. Risks & tradeoffs

- **Batch fidelity vs cost** is the core tension; the quality-guard + size cap + opt-in
  flag keep it safe, but document clearly that `class_batch` trades some grading
  fidelity for cost.
- **Batch blast radius:** one failed call fails a whole chunk → retry then fall back to
  per-submission for that chunk.
- **Per-student cost attribution in batch** is approximate (one usage object for N
  students): store the true total at batch/job level and split per-student by token
  share for display.
- **Prompt-caching variance** across providers: measure via cached-token capture rather
  than assume; let the data drive batch-vs-per-submission guidance.
- **Privacy invariant unchanged:** batching only ever concatenates already-scrubbed
  content; blocked/high-risk students never enter a batch.

## 12. Open questions (need your call)

1. **Auto-accept default confidence** (0.85?) and whether `auto` should still hold back
   flagged rows only (assumed yes).
2. **`class_batch` output format:** strict-JSON-schema array vs XML-wrapped JSON —
   recommend JSON-schema where supported, XML fallback otherwise.
3. **Per-student cost split** in batch: even split vs token-weighted (recommend
   token-weighted).
4. **Default batch size / context fraction** (10 / 0.8 proposed).
5. Whether to also parallelize `per_submission` now (`batch_completion`) or defer.

## Quick reference — current grading touchpoints

| Concern | Location |
| --- | --- |
| Engine call (single) | `grading.py:_draft_submission` (~496-661) |
| Prompt builder | `litellm_engine.py:_build_messages` (125-155) |
| Response parse/validate | `litellm_engine.py:parse_litellm_result` (96-122) |
| Attempt metadata | `grading.py:_record_attempt` (664+), `models.py:GradingAiAttempt` (149) |
| Cost estimate | `llm_catalog.py:estimate_cost_cents` |
| Modes (source of truth) | `apps/web/src/types.ts:158-160`, `grader/GraderSetup.tsx:8-30` |
| Job fields | `models.py:GradingJob` (81-95) |
| Settings | `settings.py:18-28` |
