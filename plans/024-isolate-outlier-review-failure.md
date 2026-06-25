# Plan 024: Make the pass-2 outlier review best-effort so a failed exception pass never blocks drafting

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 9bac651..HEAD -- apps/api/src/classroom_downloader/grading/drafting.py apps/api/tests/test_grading.py`
> If either in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `9bac651`, 2026-06-24

## Why this matters

Plan 022 added a second, whole-class "outlier review" pass that runs **after** every
submission has been drafted. Its flags are explicitly **advisory** — they only set
`submission.flag`, never a score, and never touch `reviewed` rows. But the pass is
**not isolated from the job's success path**. The outlier pass runs inside
`draft_grading_job` *before* the job status is finalized, and neither the LiteLLM
engine call nor the JSON parser is wrapped in error handling. So any transient
network blip, timeout, or a model that returns malformed JSON during the advisory
pass throws an exception that:

1. propagates out of `draft_grading_job` before the job reaches the `reviewing` /
   `completed` status, and
2. is caught by the draft SSE handler, which emits **"Drafting failed."** to a
   teacher whose students were **all already graded successfully**.

Worse, on resume the pass-2 completion marker was never committed (the exception
aborted before it), so `_outlier_review_already_completed` is still `False` and
pass 2 re-runs — meaning a **persistent** pass-2 failure (e.g. a model that won't
emit valid JSON) **permanently blocks** the teacher from finishing review of work
the AI already produced.

The per-submission grading path (`_draft_submission`) and the vision path
(`extract_image` in `litellm_engine.py`) both carefully classify and contain their
errors. The outlier pass must do the same: fail soft, fall back to mechanical
flags, and let drafting complete.

## Current state

Files:

- `apps/api/src/classroom_downloader/grading/drafting.py` — `review_outliers_for_job`
  (the advisory pass-2 function) and its call site inside `draft_grading_job`.
- `apps/api/tests/test_grading.py` — existing outlier-review tests
  (`test_outlier_review_applies_only_returned_flags_and_clears_pass1_noise`,
  `test_outlier_review_gate_off_keeps_drafting_free_of_outlier_flags`,
  `test_outlier_review_excludes_blocked_rows`) use a `_OutlierEngine` test double.

The call site — `review_outliers_for_job` runs at `drafting.py:677`, **before** the
status is finalized at `:689-692`:

```python
# drafting.py ~675-692
    if on_outlier_progress:
        on_outlier_progress(total, total, "Analisando exceções")
    outlier_flags = review_outliers_for_job(session, job, grading_engine)   # :677
    for flag in outlier_flags:
        submission = session.get(GradingSubmission, flag["id"])
        ...
    _refresh_counts(session, job)
    _refresh_cost_rollup(session, job, grading_engine, started)
    job.status = GradingStatus.completed if job.reviewed_submissions == job.total_submissions and job.total_submissions else GradingStatus.reviewing   # :689
    job.updated_at = datetime.now(UTC)
    session.add(job)
    session.commit()   # :692
```

The unguarded engine call inside `review_outliers_for_job` (`drafting.py:488-498`):

```python
    reviewer = getattr(grading_engine, "review_outliers", None)
    if not callable(reviewer):
        flags = []
    else:
        flags = reviewer(
            OutlierBatchRequest(
                job_id=job.id,
                activity_title=job.activity_title,
                submissions=candidates,
            )
        ) or []
```

The completion marker is recorded only after the engine call, with a hardcoded
status (`drafting.py:507-529`):

```python
    marker_submission = session.get(GradingSubmission, candidates[0].id)
    if marker_submission is not None:
        metadata = _attempt_metadata(grading_engine)
        _record_attempt(
            session=session,
            job=job,
            submission=marker_submission,
            engine=grading_engine,
            status="completed",          # <- always "completed" today
            ...
            stage="outlier_review",
            ...
        )
```

The draft SSE handler that turns any propagated exception into a user-facing
failure (`apps/api/src/classroom_downloader/routers/grading.py:946-948`):

```python
        except Exception:
            log_error(logger, "grading.draft.stream.failed", job_id=job_id)
            events.put({"phase": "draft", "error": "Drafting failed."})
```

`LiteLlmEngine.review_outliers` (`litellm_engine.py:172-228`) calls
`litellm.completion(...)` with **no** try/except, and `parse_outlier_flags`
(`litellm_engine.py:329-345`) raises `ValueError("malformed_llm_response")` on bad
JSON — both propagate up through `review_outliers_for_job` today.

Conventions to follow:

- Logging uses the helpers imported at `drafting.py:21`:
  `from ..observability import get_logger, log_debug, log_error, log_event, safe_fields, text_preview`.
  Use `log_error(logger, "grading.outlier_review.failed", job_id=job.id)` for the
  caught failure — match the `log_error(logger, "grading.draft.stream.failed", ...)`
  style already used for draft failures.
- `_record_attempt` accepts a `status=` string (it is called with `status="completed"`
  at `drafting.py:515` and the gate-off path uses the same helper). Passing
  `status="failed"` is valid and keeps `_outlier_review_already_completed`
  (`drafting.py:378-387`, which filters `status == "completed"`) returning `False`,
  so a future explicit re-draft can retry the pass without blocking the current run.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Run backend tests | `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` (from `apps/api`) | all pass (currently 234 passed, 4 skipped) + your new test |
| Run only outlier tests | `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q -k outlier` (from `apps/api`) | all pass |

(These are the repo's real commands — `apps/api` uses `uv` + pytest; the mock
provider env var keeps the suite deterministic.)

## Scope

**In scope** (the only files you should modify):
- `apps/api/src/classroom_downloader/grading/drafting.py`
- `apps/api/tests/test_grading.py` (add one test)

**Out of scope** (do NOT touch, even though they look related):
- `apps/api/src/classroom_downloader/litellm_engine.py` — do **not** add error
  handling here; the fix belongs at the orchestration layer
  (`review_outliers_for_job`) so it covers *every* engine implementation uniformly,
  including ones that raise inside `review_outliers`. Touching the engine would
  leave the parser path and future engines unguarded.
- `apps/api/src/classroom_downloader/routers/grading.py` — the SSE handler is
  correct; the fix is to stop the exception from reaching it.
- Any change to per-submission grading (`_draft_submission`) or scoring — pass 1 is
  not in scope.

## Git workflow

- Branch: `advisor/024-isolate-outlier-review-failure`
- One commit; message style matches `git log` (e.g. `fix(api): make outlier review best-effort so pass-2 errors don't fail drafting`).
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Wrap the outlier engine call so failures fall back to no flags

In `review_outliers_for_job` (`apps/api/src/classroom_downloader/grading/drafting.py`),
replace the unguarded engine call block (currently `drafting.py:488-498`) so an
exception is caught, logged, and converted into an empty flag list plus a
`review_failed` marker:

```python
    reviewer = getattr(grading_engine, "review_outliers", None)
    review_failed = False
    if not callable(reviewer):
        flags = []
    else:
        try:
            flags = reviewer(
                OutlierBatchRequest(
                    job_id=job.id,
                    activity_title=job.activity_title,
                    submissions=candidates,
                )
            ) or []
        except Exception:
            review_failed = True
            flags = []
            log_error(logger, "grading.outlier_review.failed", job_id=job.id)
```

When `flags` is empty, the existing flag-application loop already falls each
candidate back to its mechanical (privacy/extraction) flag via
`_mechanical_flag_for_attempt(...)` — so no other change is needed there.

**Verify**: `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q -k outlier` (from `apps/api`) → all existing outlier tests still pass.

### Step 2: Record the marker with a failed status when the pass errored

In the same function, change the hardcoded `status="completed"` in the
`_record_attempt(...)` call (currently `drafting.py:515`) to reflect whether the
pass failed:

```python
            status="failed" if review_failed else "completed",
```

This keeps `_outlier_review_already_completed` returning `False` after a failure
(it only counts `status == "completed"`), so the pass can be retried by a future
explicit re-draft — but the **current** draft still finishes cleanly because
`review_outliers_for_job` now returns normally.

**Verify**: `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q -k outlier` (from `apps/api`) → all pass.

### Step 3: Add a regression test for the failing pass

In `apps/api/tests/test_grading.py`, add a test that uses a `review_outliers`
engine which **raises**, and asserts drafting still completes with the job in a
reviewable state and pass-1 drafts intact. Model it on the existing
`test_outlier_review_applies_only_returned_flags_and_clears_pass1_noise` (same
file) for fixture/setup shape. The engine double should subclass or mirror the
existing `_OutlierEngine` (defined near `test_grading.py:453`) but raise inside
`review_outliers`:

```python
class _RaisingOutlierEngine(_OutlierEngine):
    def review_outliers(self, request):
        raise RuntimeError("simulated outlier-pass failure")
```

Assertions (adapt names to the helper functions the neighboring tests use to build
and run a job):

- The draft run completes without raising (no exception escapes `draft_grading_job`).
- The job status is `reviewing` (or `completed` if all auto-accepted) — i.e. **not**
  left in a failed/processing state.
- Each previously drafted submission still has its `ai_score` / `feedback` from
  pass 1 (drafts not lost).
- No submission carries an outlier flag (flags fell back to mechanical / `None`).
- `_outlier_review_already_completed(session, job.id)` is `False` (the marker was
  recorded with `status="failed"`), confirming a retry is still possible.

**Verify**: `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q -k outlier` (from `apps/api`) → your new test passes alongside the others.

### Step 4: Full backend suite stays green

**Verify**: `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` (from `apps/api`) → all pass (was 234 passed, 4 skipped; now +1 from your new test).

## Test plan

- New test in `apps/api/tests/test_grading.py`:
  `test_outlier_review_failure_does_not_fail_drafting` — covers the regression
  (engine raises → drafting still completes, drafts intact, no flags, marker
  recorded as failed). Pattern source:
  `test_outlier_review_applies_only_returned_flags_and_clears_pass1_noise`.
- Verification: `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` → all pass.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` (from `apps/api`) exits 0; the new failure test exists and passes.
- [ ] The engine call inside `review_outliers_for_job` is wrapped in `try/except` and logs `grading.outlier_review.failed` on error (`grep -n "grading.outlier_review.failed" apps/api/src/classroom_downloader/grading/drafting.py` returns a match).
- [ ] The `_record_attempt` for `stage="outlier_review"` uses a `failed`/`completed` status conditioned on `review_failed` (no longer a bare `status="completed"`).
- [ ] No files outside the in-scope list are modified (`git status`).
- [ ] `plans/README.md` status row for plan 024 updated.

## STOP conditions

Stop and report back (do not improvise) if:

- The `drafting.py` excerpts in "Current state" don't match the live code (the file
  drifted since this plan was written — e.g. the call site or marker block moved).
- Adding the `try/except` causes existing outlier tests to fail in a way a small fix
  doesn't resolve — it may mean a test depends on the exception propagating, which
  would change the intended behavior; report it.
- You find that `_draft_submission` results are **not** persisted before
  `review_outliers_for_job` runs (i.e. a pass-2 failure would actually lose pass-1
  drafts via an uncommitted-then-rolled-back session). If so, the fix must also
  ensure pass-1 work is committed before pass 2 — STOP and report this rather than
  silently expanding scope.

## Maintenance notes

- The outlier pass is **advisory**. Any future change to `review_outliers_for_job`
  must preserve the invariant that a pass-2 failure can never prevent drafting from
  reaching a reviewable state — keep the engine call inside the `try`.
- A failure is recorded with `status="failed"`, so `_outlier_review_already_completed`
  stays `False` and a later explicit re-draft retries the pass. If you ever want a
  failed pass to *not* retry (to avoid repeated cost on a persistently broken
  model), change the recorded status — but never at the cost of blocking the
  current draft.
- Reviewer should confirm the new test actually exercises the raise path (the
  engine double's `review_outliers` is reached — i.e. there are eligible candidates
  with scrubbed content, gate is `on`).
