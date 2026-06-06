# Execution Plan: AI-inferred rubric criteria (real, holistic, batched)

> **For the implementing agent:** This completes **Task 4 / "B. AI-inferred rubric"**
> from `docs/grading-ux-fixes-2026-06-05/PLAN.md`, which shipped a *mechanism* that
> never fires in practice. Work task-by-task, top to bottom. Backend is TDD: write the
> failing test, run it red, implement, run it green, run the full suite, commit. One
> atomic commit per task. **Do not make real Google or LLM provider calls in tests** —
> mock the provider/engine the way `tests/test_grading.py` already does.

## Why this exists (the bug)

In `rubric_mode: "infer"`, the rubric panel always shows the placeholder
*"A IA vai sugerir os critérios após analisar as entregas"* even after grading
completes — see `docs/image.png` (`naruto.py`, score 100, motor "Concluído", criteria
never materialized).

Root cause — rubric inference is a **side-channel bolted onto the per-submission
scoring call**:

- Criteria are seeded as `DEFAULT_CRITERIA` placeholders at job creation
  (`grading.py:92` `ensure_default_criteria`, called from `main.py:915`).
- Each `grade()` call is *also* asked to return an optional `inferred_criteria` array
  (`litellm_engine.py:169`, schema `:230`; result field `grading_engine.py:34`).
- The **first** submission whose result has non-empty `inferred_criteria` *and* whose
  job criteria still equal the defaults triggers the swap
  (`grading.py:828-830` `_replace_job_criteria`).

Four structural defects fall out of that:

1. **Optional field on a scoring prompt** → the model usually returns `[]`. One empty
   array on submission #1 and the swap silently never fires; defaults persist forever.
   This is the screenshot.
2. **Single-sample basis** → even when it fires, the rubric is invented from one
   arbitrary submission (whichever graded first), not the assignment as a whole.
3. **Inconsistent grading basis** → submission #1 is graded against the *defaults*
   (criteria are still defaults when it runs); only #2…#N see the inferred rubric.
4. **`class_batch` is a label only** → the default was flipped to `class_batch`
   (`settings.py:55`, stored at `models.py:90`, `main.py:910`) but **nothing branches
   on it**; grading is still strictly per-submission.

Separately, the Google `courseWork` API returns a `description`, but the provider
**drops it** (`google_provider.py:382-388` / `:412-418` map only title/workType/state/
due). The strongest signal for a rubric — the teacher's own assignment description —
is never even fetched.

## The fix (locked design)

A **dedicated rubric-inference phase that runs once per job, before drafting**, when
`rubric_mode === "infer"`:

1. **Inputs:** the activity **description** (newly threaded through) + a **randomized
   sample of up to N=4** already-scrubbed submissions (the privacy audit has already
   cached & scrubbed them — privacy-safe, no extra Google/extraction cost).
2. **Description-first:** if the description is substantial, infer from the description
   **alone** (zero sample tokens). Only pull the sample when the description is thin or
   missing.
3. **One batched LLM call.** Sample submissions are delimited with **XML tags** in the
   prompt (clean separation, minimal escaping); the **response is JSON** matching the
   existing criteria shape (consistent parser, reuse `_normalize_inferred_criteria`).
4. **Persist once** via `_replace_job_criteria` *before* the per-submission loop, so
   every submission grades against the same stable rubric.
5. **Streamed `criteria` phase** on the existing SSE infra, shown in
   `GradingProgressModal` ahead of the `draft` phase.
6. **Graceful fallbacks** (never block grading):
   - Fewer than 4 clean submissions → use however many exist (even 0 → description-only).
   - No description **and** no usable sample → keep `DEFAULT_CRITERIA`, surface a soft
     note.
   - Inference returns nothing/garbage → keep `DEFAULT_CRITERIA`.

### Locked decisions
- **N = 4** sample cap; degrade gracefully when fewer submissions exist.
- **Description-first ON.**
- **XML-in / JSON-out.**
- **Dedicated streamed `criteria` phase** (leads the draft stream).
- Remove the per-submission `inferred_criteria` swap from the grade loop; keep
  `DEFAULT_CRITERIA` only as a last-resort fallback.

### "Substantial description" threshold
Treat the description as substantial when, after stripping/normalizing whitespace, it
has **≥ 200 characters** *and* **≥ 25 words**. Below that → sample-backed inference.
(Tunable via a `settings` knob; see Task 2.)

---

## Task 1 — Thread the activity description through provider → job

**Goal:** make the teacher's assignment description available to the inference phase.

### Changes
- `google_provider.py`: add `description: str | None = None` to the `ClassroomActivity`
  dataclass (near `:73`); map `activity.get("description")` in **both**
  `list_activities` (`:382-388`) and `get_activity` (`:412-418`).
- `schemas.py`: add `description: str | None = None` to `ActivityRead` (`:13`).
- `models.py`: add `activity_description: str | None = None` to `GradingJob` (`:81`).
- `database.py`: add `"activity_description": "VARCHAR"` to the `gradingjob` column map
  in `_ensure_grading_job_columns` (`:34-51`).
- `main.py` `create_grading_job` (`:901-913`): set
  `activity_description=activity.description` on the new `GradingJob`. (The endpoint
  already fetches the activity via the provider just above — confirm it uses
  `get_activity`; if it only has the queue item, fetch `get_activity` for the
  description.)

### Acceptance criteria
- A job created for an activity that has a description persists that text in
  `GradingJob.activity_description`.
- Activities with no description still create jobs (`None`, no error).
- `GET /api/activities` (or equivalent) exposes `description` without breaking existing
  consumers.

### Tests (`tests/test_grading.py`, mock provider)
- `test_job_persists_activity_description` — mock provider returns an activity with a
  description; create a job; assert the column holds it.
- Extend the mock provider fixture so `get_activity`/`list_activities` can carry a
  description (default `None` to keep existing tests green).

---

## Task 2 — Rubric-inference engine method (XML-in / JSON-out)

**Goal:** a first-class `infer_rubric` engine call, separate from `grade`.

### Changes
- `grading_engine.py`:
  - Add a frozen `RubricInferenceRequest` dataclass: `job_id`, `activity_title`,
    `activity_description: str | None`, `rubric_text: str | None`,
    `samples: list[dict]` (each `{"label": str, "source_label": str,
    "mime_type": str, "content": str}` — already-scrubbed text), and a
    `description_only: bool` hint.
  - Add `infer_rubric(self, request: RubricInferenceRequest) -> list[dict[str,
    str | int | None]]` to the `GradingEngine` Protocol (`:37`).
  - Implement `MockGradingEngine.infer_rubric` (`:45`): deterministic, derived from a
    hash of `job_id` + description/sample presence, returning 3–4 plausible criteria
    whose weights sum to 100 (so tests are stable and assert real replacement).
- `litellm_engine.py`:
  - Add `infer_rubric`: **one** chat call. System prompt = "Design a grading rubric for
    this assignment. Respond with JSON only." User content bundles the activity title +
    description and, when not `description_only`, the sample submissions wrapped in
    `<submission label="...">…</submission>` tags inside a single string. Response uses
    a JSON schema mirroring the existing `inferred_criteria` item shape
    (`name`/`weight`/`description`, weights are integers). Reuse `_response_format`
    plumbing where practical.
  - Parse via the existing tolerant path and hand back the raw list (normalization
    happens in `grading.py`).
- `settings.py`: add knobs (defaults in parens):
  - `rubric_infer_sample_size: int = 4`
  - `rubric_description_min_chars: int = 200`
  - `rubric_description_min_words: int = 25`

### Acceptance criteria
- `MockGradingEngine.infer_rubric` returns ≥3 criteria summing to 100 deterministically.
- The litellm prompt contains the description and (when sampled) XML-delimited
  submissions; the response is parsed into the criteria list shape.
- No real network calls in tests (mock engine only).

### Tests (`tests/test_grading.py`)
- `test_mock_infer_rubric_returns_weighted_criteria` — weights sum to 100, ≥3 rows.
- A focused unit test on the XML bundle builder (pure function) asserting each sample is
  wrapped and escaped, and `description_only=True` omits samples.

---

## Task 3 — Orchestration: infer once, persist, fall back

**Goal:** a single function that selects the sample, calls the engine, normalizes, and
replaces the job criteria — with all the fallbacks.

### Changes (`grading.py`)
- Add `infer_job_criteria(session, job, provider, engine, *, on_progress=None) ->
  list[GradingCriterion]`:
  1. Decide **description-first**: if `job.activity_description` is substantial per the
     Task-2 thresholds → `description_only=True`, no sample.
  2. Otherwise build the sample: reuse the audit's scrubbed content. Select up to
     `settings.rubric_infer_sample_size` submissions, **filtered to clean extractions**
     (skip `extraction_status in {"unsupported","failed"}` and high-risk/blocked rows),
     **randomized** (seed with `job.id` for reproducible tests). If fewer than N clean
     ones exist, use all of them; if zero, fall back to description-only; if also no
     description → return defaults unchanged (soft note).
  3. Call `engine.infer_rubric(...)`, `_normalize_inferred_criteria(...)`, then
     **normalize weights to sum 100** (proportional rescale; if normalization yields
     nothing, keep defaults).
  4. `_replace_job_criteria(session, job.id, inferred)` once; `commit`.
  5. Emit `on_progress` so the SSE layer can surface a `criteria` phase
     (e.g. `("inferring", "Lendo a descrição e amostras…")` → `("done", ...)`).
- **Remove the per-submission swap** at `grading.py:828-830` (the
  `inferred_criteria`/`_criteria_match_defaults` block inside `_draft_submission`).
  Keep `_normalize_inferred_criteria`, `_replace_job_criteria`, and
  `_criteria_match_defaults` (now used by the orchestrator / FE-parity helper).
- Keep `DEFAULT_CRITERIA` strictly as the last-resort fallback.

### Acceptance criteria
- Infer mode with a rich description → criteria reflect the description, no sample pulled.
- Infer mode with a thin description + ≥1 clean submission → criteria reflect the sample.
- Fewer than 4 submissions → uses all available; 0 submissions + no description → defaults.
- Final criteria weights sum to 100.
- The per-submission grade loop no longer mutates criteria.

### Tests (`tests/test_grading.py`)
- `test_infer_uses_description_only_when_substantial` — long description, monkeypatch
  engine to echo which path it took; assert no sample passed and criteria replaced.
- `test_infer_uses_sample_when_description_thin` — short/empty description, 2 clean
  submissions; assert criteria replaced from the sample.
- `test_infer_handles_fewer_than_sample_size` — 2 submissions with N=4; no error, uses 2.
- `test_infer_falls_back_to_defaults_when_no_signal` — no description, no usable sample
  → criteria remain `DEFAULT_CRITERIA`.
- `test_inferred_weights_sum_to_100`.
- `test_grade_loop_no_longer_swaps_criteria` — regression guard for the removed block.

---

## Task 4 — Wire the `criteria` phase into the draft flow + SSE

**Goal:** run inference automatically as the leading phase of "enviar para avaliação da
IA", streamed, before drafting.

### Changes (`main.py`)
- `POST .../draft` (`:1079`) and the **draft SSE worker** (`:1104-1159`): before the
  per-submission draft, if `job.rubric_mode == "infer"` **and** the job's criteria still
  match defaults, call `infer_job_criteria(...)`.
  - In the SSE worker, emit `{"phase":"criteria","processed":n,"total":m,"current":...}`
    progress events and a non-terminal phase transition, then continue into the existing
    `draft` phase events. (Do **not** emit `done` between phases — the modal stays open
    across criteria → draft; only the final draft event carries `done:true`.)
  - In the non-streaming `POST`, just run inference inline before `draft_grading_job`.
- Keep `POST .../privacy-audit` and the audit stream untouched.

### Acceptance criteria
- Starting drafting in infer mode persists real criteria *before* any submission is
  graded; the review breakdown shows them (placeholder gone).
- The draft SSE stream emits ≥1 `criteria` event then the existing `draft` events and a
  single terminal `done`.
- `POST .../draft` (non-streaming) still returns the drafted job with real criteria.

### Tests (`tests/test_grading.py`)
- `test_draft_stream_emits_criteria_then_draft_phase` — infer job; consume SSE; assert a
  `criteria` event precedes `draft` events and exactly one terminal `done`; final job
  criteria are not the defaults.
- `test_post_draft_infers_criteria_inline` — non-streaming infer draft replaces defaults.
- Confirm `test_draft_stream_emits_per_submission_progress` (existing) stays green for
  non-infer modes.

---

## Task 5 — Frontend: surface the `criteria` phase

**Goal:** the modal and review screen reflect the new phase honestly.

### Changes
- `GradingProgressModal.tsx`: extend `GradingProgressPhase` with `"criteria"` and add
  `phaseCopy.criteria` (`title: "Definindo critérios"`, `eyebrow: "Lendo a descrição e
  as entregas"`).
- `App.tsx`: add `"criteria"` to the `GradingStreamPayload.phase` union and to
  `streamGradingProgress`'s phase typing; no new EventSource — the existing draft stream
  now leads with `criteria` events and the modal renders them.
- `GraderReview.tsx`: the `hasDefaultCriteria` placeholder (`:296-300`) now clears
  itself once real criteria are persisted — verify it renders the breakdown after an
  infer draft. Optionally soften the placeholder copy to *"A IA está definindo os
  critérios…"* while the criteria phase is active.

### Acceptance criteria
- During an infer draft, the modal shows a "Definindo critérios" phase, then the draft
  progress, then hands off to review.
- The review breakdown shows the AI's criteria (names + weights summing to 100), not the
  static four.
- Non-infer modes are visually unchanged.

### Verify
Run with the mock provider: create an infer job for an activity *with* a description and
one *without*; draft both; confirm criteria differ and reflect the source. Compare
against `docs/image.png` (the broken "before"). `npx tsc -b` clean.

---

## Suggested commit order
1. Task 1 (description plumbing) — isolated, unlocks the signal.
2. Task 2 (engine method) — pure, testable.
3. Task 3 (orchestration + remove side-channel) — the core behavior change.
4. Task 4 (wire + SSE).
5. Task 5 (frontend).

## Out of scope / watch-outs
- **Cost:** exactly **+1 LLM call per job** (description-only or one batched sample
  call), never per-submission. The sample reuses already-scrubbed audit content — no new
  Google fetch or extraction.
- **Privacy:** only **scrubbed** submission text ever enters the inference prompt (same
  guarantee as grading). Never send raw originals; never send student PII.
- **Don't regress** the existing audit/draft SSE contract from
  `docs/grading-ux-fixes-2026-06-05` — keep one terminal `done`, keep the non-streaming
  POSTs green.
- A teacher-facing **editor** for inferred criteria (review/adjust before drafting) is a
  natural follow-up but **out of scope** here — this task makes the criteria real and
  correct first.
