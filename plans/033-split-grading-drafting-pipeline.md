# Plan 033: Split the grading drafting pipeline into policy, submission, outlier, and job services

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If a STOP condition occurs, stop and report; do not improvise.
> When done, update this plan's row in `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 035af04..HEAD -- apps/api/src/classroom_downloader/grading/drafting.py apps/api/src/classroom_downloader/grading/ apps/api/tests/`
> If `drafting.py` changed, re-read it fully and compare the current function
> boundaries before proceeding.

## Status

- **Priority**: P2
- **Effort**: L
- **Risk**: HIGH
- **Depends on**: plans/028-split-grading-backend-tests.md, plans/029-extract-grading-router-services.md
- **Category**: tech-debt
- **Planned at**: commit `035af04`, 2026-06-29

## Why this matters

`grading/drafting.py` is the core grading pipeline, but it now mixes scoring
policy, per-submission drafting, cache/scrub handling, engine calls, attempt
recording, outlier review, and job orchestration. The module is important and
high-risk, so this plan is deliberately incremental: move coherent blocks
without changing behavior, relying on the smaller tests from plan 028.

## Current state

Relevant live shapes to confirm:

- `_apply_criterion_scores` is near the top and mutates
  `GradingSubmissionCriterionScore` rows while deriving scores.
- `_draft_submission` starts around line 128 and handles cache/scrub counters,
  teacher-loop policy, blocked-before-engine behavior, engine calls, attempts,
  criterion notes/scores, auto-accept, flags, and submission mutation.
- `_scrubbed_content_for_outlier_review` and `review_outliers_for_job` are later
  in the file; archived plan 024 requires outlier review failures to be
  best-effort and never block drafting.
- `draft_grading_job` orchestrates job state, provider file listing, queue
  materialization, per-submission drafting, outlier pass, cost rollup, and final
  status.

Invariants to preserve:

- AI grading is draft-only.
- Privacy/audit data must not persist sensitive extracted or scrubbed text.
- Outlier pass is advisory and failure-isolated.
- Criterion scores are persisted once per criterion and final scores derive from
  review inputs.
- Existing SSE callbacks from the router/service layer must still receive the
  same progress/submission events.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Focused grading tests | `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q tests/test_grading*.py` | all pass |
| Full backend suite | `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` | all pass |

Run from `apps/api`.

## Scope

**In scope**:

- `apps/api/src/classroom_downloader/grading/drafting.py`
- New modules under `apps/api/src/classroom_downloader/grading/`, for example:
  - `scoring.py`
  - `submission_drafting.py`
  - `outliers.py`
  - `job_drafting.py` if useful
- Focused grading tests if imports need adjustment or small characterization
  tests are missing.

**Out of scope**:

- Router/SSE extraction; plan 029 handles that.
- Engine behavior in `litellm_engine.py`.
- Provider behavior.
- Public API schemas or frontend behavior.

## Git workflow

- Branch: `advisor/033-split-grading-drafting-pipeline`.
- Use small commits. Run focused tests after each.
- Do not push or open a PR unless instructed.

## Steps

### Step 1: Baseline and characterization

Run focused grading tests and identify any missing coverage for the block you
will move first. If there is no focused test for `_apply_criterion_scores`,
outlier failure isolation, or resume idempotency, add characterization tests
before moving code.

**Verify**: focused grading tests pass.

### Step 2: Extract scoring policy

Move `_apply_criterion_scores` and any tiny helpers used only for criterion
score mutation into `grading/scoring.py`. Keep the function signature stable if
possible, or update imports in `drafting.py`.

**Verify**: criterion/review focused tests pass.

### Step 3: Extract outlier review service

Move `_scrubbed_content_for_outlier_review`, outlier completion marker helpers,
and `review_outliers_for_job` into `grading/outliers.py`.

Preserve archived plan 024 behavior: engine/parser failures must be caught,
logged, recorded as failed, and must not prevent drafting from reaching a
reviewable state.

**Verify**: outlier focused tests pass.

### Step 4: Extract per-submission drafting

Move `_draft_submission` and only the helpers it directly needs into
`grading/submission_drafting.py`. If the function has many dependencies, prefer
passing an explicit context dataclass over importing unrelated globals into the
new module.

Do not rewrite the function's internal logic in this step. This is a move, not a
cleanup.

**Verify**: focused grading tests pass.

### Step 5: Keep or extract job orchestration

After steps 2-4, evaluate `drafting.py`. If it is already a thin orchestrator,
leave `draft_grading_job` there and stop. If it still contains mixed job
orchestration plus helper logic, move orchestration into `grading/job_drafting.py`
and keep `drafting.py` as a compatibility facade.

**Verify**: full backend suite passes.

### Step 6: Final import cleanup

Remove unused imports and ensure public imports still work. If other modules
import `draft_grading_job` or `review_outliers_for_job` from `drafting.py`, keep
compatibility re-exports.

**Verify**: full backend suite passes.

## Test plan

- Existing focused grading tests from plan 028 should pass after every move.
- Add characterization tests only where a moved block lacks direct coverage.
- The final gate is the full backend suite in mock mode.

## Done criteria

- [ ] Scoring policy is no longer embedded in the main drafting orchestration
      module.
- [ ] Outlier review code lives in its own module and preserves failure
      isolation.
- [ ] Per-submission drafting code is separated from job-level orchestration.
- [ ] Public imports used by routers/tests still work.
- [ ] `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` exits 0.
- [ ] No files outside the in-scope list are modified.
- [ ] `plans/README.md` row for 033 updated.

## STOP conditions

Stop and report if:

- A move requires changing grading behavior to make tests pass.
- Sensitive extracted/scrubbed text would need to cross a new persistence or
  logging boundary.
- Transaction boundaries become unclear.
- The extraction cannot preserve public imports without circular imports.

## Maintenance notes

This is the highest-risk maintenance plan in this batch. Reviewers should check
behavioral diffs carefully and prefer small PRs over a single large rewrite.
