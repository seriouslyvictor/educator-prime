# Plan 029: Extract grading router services and shared SSE runner

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If a STOP condition occurs, stop and report; do not improvise.
> When done, update this plan's row in `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 035af04..HEAD -- apps/api/src/classroom_downloader/routers/grading.py apps/api/src/classroom_downloader/grading/ apps/api/tests/`
> If any in-scope file changed, compare this plan's current-state notes with
> live code before proceeding.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/028-split-grading-backend-tests.md
- **Category**: tech-debt
- **Planned at**: commit `035af04`, 2026-06-29

## Why this matters

`routers/grading.py` is over 1100 lines and mixes HTTP routing, SSE threading,
preview-file response policy, workflow helpers, and domain mutation for manual
review. This makes the router the place every grading change must touch, even
when the change is not HTTP-specific. The goal is to keep public endpoints
unchanged while moving reusable behavior into service modules that can be tested
without FastAPI request plumbing.

## Current state

Relevant live shapes to confirm:

- `apps/api/src/classroom_downloader/routers/grading.py` imports `Queue` and
  `Thread` near the top and defines three separate streaming endpoint bodies:
  `stream_grading_privacy_audit`, `stream_grading_criteria`, and
  `stream_draft_job`. Each builds a queue, inner worker, progress callback, and
  SSE event loop.
- Preview policy constants such as `SAFE_INLINE_MIME_TYPES`,
  `SAFE_TEXT_MIME_TYPES`, and `SAFE_TEXT_EXTENSIONS` live in the router, along
  with `_preview_response_mode` and `preview_grading_submission`.
- `review_submission` validates criterion IDs, deletes and recreates
  `GradingSubmissionCriterionScore` rows, derives `final_score`, updates
  reviewed counts, and commits from inside the router.
- Helper functions `ensure_privacy_audit_allows_draft` and
  `maybe_infer_job_criteria` are workflow helpers, not HTTP route definitions.

Existing product invariants to preserve:

- AI grading remains draft-only.
- Privacy audit data must not store extracted/scrubbed text, prompts, names, or
  emails.
- Outlier review is advisory and must not block drafting; see archived plan 024.
- `scope: "remaining"` on job creation and grade-aware queue behavior from
  archived plans 016-023 must remain intact.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Grading tests | `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q tests/test_grading*.py` | all pass |
| Backend suite | `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` | all pass |
| OpenAPI drift | Included in backend suite | snapshot passes or tells you how to regenerate |

Run from `apps/api`.

## Scope

**In scope**:

- `apps/api/src/classroom_downloader/routers/grading.py`
- New modules under `apps/api/src/classroom_downloader/grading/`, for example:
  - `streaming.py`
  - `review.py`
  - `preview.py`
  - `workflow.py`
- Focused grading tests under `apps/api/tests/`.

**Out of scope**:

- Public endpoint paths, request schemas, response schemas, and SSE payload
  shapes.
- `litellm_engine.py` or provider behavior.
- Drafting algorithm changes in `grading/drafting.py`; those belong to plan 033.

## Git workflow

- Branch: `advisor/029-extract-grading-router-services`.
- Prefer one commit per extraction: preview, review mutation, SSE runner.
- Do not push or open a PR unless instructed.

## Steps

### Step 1: Baseline after plan 028

Run the focused grading suite. If plan 028 was not executed, stop and run/finish
it first unless the operator explicitly accepts the higher review cost.

**Verify**: `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q tests/test_grading*.py`
exits 0.

### Step 2: Extract preview response policy

Create `classroom_downloader/grading/preview.py`. Move only preview-related
constants and pure helpers from the router:

- safe inline MIME set
- safe text MIME set
- safe text extension set
- extension/response-mode helpers

Keep the FastAPI `FileResponse`/`Response` construction in the router unless a
clean service function can return a simple value object without pulling FastAPI
into the domain module.

**Verify**: backend grading tests pass.

### Step 3: Extract manual review mutation

Create `classroom_downloader/grading/review.py` with a function that performs
the domain mutation currently embedded in `review_submission`: validate the
submission belongs to the job, validate criterion IDs, replace criterion score
rows, derive `final_score`, update feedback/reviewed/flags, refresh job counts,
and commit.

The router should parse the request and call this service, then return the same
snapshot response it returns today.

**Verify**: run the review/criterion tests from plan 028, then the focused
grading suite.

### Step 4: Extract workflow helpers

Move `ensure_privacy_audit_allows_draft` and `maybe_infer_job_criteria` into a
module such as `grading/workflow.py` if they are still in the router. Keep names
the same unless imports become clearer with a different name.

**Verify**: grading tests pass.

### Step 5: Introduce a shared SSE runner

Create a small helper in `grading/streaming.py` or `routers/sse.py` that owns
the repeated queue/thread/event-stream mechanics. It should accept:

- a worker callback that receives an event-publish function
- an optional seed function for initial queued events
- the terminal event shape expected by the caller

Do not change event names, fields, ordering guarantees, or reconnect behavior.
Start with the smallest shared abstraction that removes the repeated
`Queue`/`Thread`/`thread.join(timeout=1)` loop from the three endpoints.

**Verify**: run stream tests, then all grading tests.

### Step 6: Final router cleanup

Remove unused imports from `routers/grading.py`. The router should still define
the same endpoints, dependencies, and response models, but its endpoint bodies
should be thinner and delegate domain behavior.

**Verify**: full backend suite exits 0.

## Test plan

- Existing tests should continue to pass unchanged.
- If plan 028 split test files, run the focused files for review, streaming, and
  privacy after their matching extraction steps.
- Add one small unit test for the new review service only if the existing review
  endpoint tests do not cover criterion ID validation and derived final score.

## Done criteria

- [ ] `routers/grading.py` no longer contains duplicated `Queue`/`Thread` SSE
      worker loops for all three streaming endpoints.
- [ ] Manual review criterion-score mutation is in a service module, not inline
      in the router.
- [ ] Preview MIME/extension policy is outside the router.
- [ ] Public API and SSE payload shapes are unchanged.
- [ ] `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` exits 0.
- [ ] No files outside the in-scope list are modified.
- [ ] `plans/README.md` row for 029 updated.

## STOP conditions

Stop and report if:

- Extracting the SSE runner requires changing client-visible event ordering or
  field names.
- The review service extraction reveals ambiguous transaction boundaries.
- OpenAPI snapshot changes for reasons other than imports/refactoring.
- Existing grading behavior tests fail for non-import reasons.

## Maintenance notes

After this lands, new grading endpoints should delegate domain work to service
modules. Reviewers should scrutinize that the router remains a transport layer
and that no privacy-sensitive text starts getting logged or persisted.
