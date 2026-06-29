# Plan 028: Split the monolithic grading backend test module

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the STOP conditions occurs, stop and report; do not
> improvise. When done, update this plan's row in `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 035af04..HEAD -- apps/api/tests/test_grading.py apps/api/tests/conftest.py`
> If `test_grading.py` changed since this plan was written, re-read it and adjust
> the extraction map before proceeding. If helpers or fixtures no longer match
> this plan, stop and report.

## Status

**Status**: DONE

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: tests
- **Planned at**: commit `035af04`, 2026-06-29

## Why this matters

`apps/api/tests/test_grading.py` is the main safety net for grading behavior, but
it has grown to roughly 2400 lines and mixes privacy gates, draft streaming,
outlier review, review mutation, criterion scoring, and queue behavior. That
makes backend refactors harder than they need to be: a change to one behavior
requires navigating unrelated tests, and future characterization tests will keep
making the file larger. This plan is a behavior-preserving test split only. It
does not change product code.

## Current state

Relevant files:

- `apps/api/tests/test_grading.py` - currently holds most grading tests.
- `apps/api/tests/test_grading_resume.py` - already separates resume-specific
  behavior; leave it in place.
- `apps/api/tests/conftest.py` - use this only if shared fixtures need a common
  home.

Known clusters in `test_grading.py`:

- Outlier tests are near lines 490, 514, 531, and 566.
- Stream/SSE draft tests are near lines 842, 1122, and 1153.
- Privacy/audit tests are near lines 822, 1215, and 1248.
- Criterion scoring/review tests are near line 2346.

Repo conventions:

- Backend tests run from `apps/api`.
- Tests use pytest, FastAPI `TestClient`, SQLModel sessions, and mock Google by
  default.
- Keep test names descriptive and behavior-oriented.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Scoped grading tests | `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q tests/test_grading*.py` | all pass |
| Full backend suite | `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` | all pass |
| Count remaining file size | `Get-Content tests/test_grading.py | Measure-Object -Line` | materially below the current ~2400 lines |

Run commands from `apps/api` unless noted.

## Scope

**In scope**:

- `apps/api/tests/test_grading.py`
- New files under `apps/api/tests/`, for example:
  - `test_grading_privacy.py`
  - `test_grading_streams.py`
  - `test_grading_outliers.py`
  - `test_grading_review.py`
  - `test_grading_criteria.py`
  - `grading_helpers.py` if shared helper code is needed
- `apps/api/tests/conftest.py` only for shared fixtures used by multiple files.

**Out of scope**:

- Any file under `apps/api/src/`.
- Any behavior, assertion meaning, fixture data, or endpoint contract.
- Renaming tests unless needed to resolve duplicate names after moves.

## Git workflow

- Branch: `advisor/028-split-grading-backend-tests`.
- Commit one logical split at a time if possible.
- Do not push or open a PR unless instructed.

## Steps

### Step 1: Establish the current baseline

Run the scoped grading tests before moving anything.

**Verify**: `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q tests/test_grading*.py`
exits 0. If it does not, stop and report the pre-existing failure.

### Step 2: Inventory helpers and fixtures

Read the top of `test_grading.py` and identify helper classes/functions shared
by more than one cluster. Move only clearly shared helpers into either
`conftest.py` or `tests/grading_helpers.py`. Prefer `grading_helpers.py` for
plain helpers and `conftest.py` for pytest fixtures.

Do not change helper bodies except import paths.

**Verify**: scoped grading tests still pass.

### Step 3: Move outlier-review tests

Move outlier-specific tests and their local test doubles into
`test_grading_outliers.py`. Keep test names and assertions unchanged.

**Verify**: `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q tests/test_grading_outliers.py`
passes, then run the scoped grading suite.

### Step 4: Move privacy and audit tests

Move privacy audit, redaction, blocked-content, and privacy-gate tests into
`test_grading_privacy.py`.

**Verify**: the new privacy file passes, then run the scoped grading suite.

### Step 5: Move streaming and draft-progress tests

Move SSE/draft stream tests into `test_grading_streams.py`. Preserve any event
parsing helpers exactly.

**Verify**: the new streams file passes, then run the scoped grading suite.

### Step 6: Move review and criterion scoring tests

Move manual review mutation, criterion score persistence, derived final score,
and related tests into `test_grading_review.py` or `test_grading_criteria.py`.
Choose one file if the tests are tightly coupled; choose two if the split is
obvious from the existing names.

**Verify**: the new files pass, then run the scoped grading suite.

### Step 7: Final cleanup

Leave `test_grading.py` with only tests that are truly broad integration tests
or that do not clearly belong to a new file. Remove unused imports from every
touched file.

**Verify**:

- `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q tests/test_grading*.py`
  exits 0.
- `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` exits 0.

## Test plan

No new behavior tests are required. This is a mechanical split. The regression
guard is that the same grading suite still passes after each move and the full
backend suite passes at the end.

## Done criteria

- [ ] `test_grading.py` is materially smaller and no longer holds every grading
      behavior cluster.
- [ ] New focused grading test files exist for at least outliers, privacy, and
      streams.
- [ ] `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q tests/test_grading*.py`
      exits 0 from `apps/api`.
- [ ] `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` exits 0 from
      `apps/api`.
- [ ] No files outside the in-scope list are modified.
- [ ] `plans/README.md` row for 028 updated.

## STOP conditions

Stop and report if:

- Moving tests requires changing application code.
- A helper has hidden global state and moving it changes test behavior.
- The baseline test suite is already failing before any move.
- More than import-path changes are needed to preserve a moved test.

## Maintenance notes

After this lands, new grading tests should go into the focused file matching the
behavior under test. Reviewers should reject new unrelated additions to
`test_grading.py` unless they are true cross-flow integration tests.
