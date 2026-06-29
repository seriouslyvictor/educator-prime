# Plan 032: Split Google provider implementation from mocks, credentials, and cache helpers

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If a STOP condition occurs, stop and report; do not improvise.
> When done, update this plan's row in `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 035af04..HEAD -- apps/api/src/classroom_downloader/google_provider.py apps/api/src/classroom_downloader/ apps/api/tests/`
> If `google_provider.py` changed, re-read it fully before proceeding.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/028-split-grading-backend-tests.md
- **Category**: tech-debt
- **Planned at**: commit `035af04`, 2026-06-29

## Why this matters

`google_provider.py` is about 1200 lines and combines provider dataclasses,
credential crypto, cache helpers, real Google API access, mock provider data,
fixture byte generation, and corpus loading. This makes tests and production
provider changes risky because unrelated concerns share one module import path.
The goal is a mechanical split that preserves public imports first, then allows
future provider work to happen in smaller files.

## Current state

Relevant live shapes to confirm:

- Mock fixture bytes/helpers appear near the top of `google_provider.py`.
- Corpus loading and TTL caches are also near the top.
- Credential encryption/decryption helpers live near lines 155-182.
- Provider dataclasses and types are defined in the same file.
- Real provider methods, including Drive metadata hydration, are later in the
  file.
- `MockGoogleProvider` starts around line 908 and contains mock courses,
  activities, submissions, and files.

Existing public imports may reference symbols directly from
`classroom_downloader.google_provider`. Preserve that import path by turning the
file into a facade after the split.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Backend suite | `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` | all pass |
| Provider import check | `python -c "from classroom_downloader.google_provider import MockGoogleProvider, GoogleProvider"` | exit 0 |

Run from `apps/api`.

## Scope

**In scope**:

- `apps/api/src/classroom_downloader/google_provider.py`
- New package or modules under `apps/api/src/classroom_downloader/google/`, for
  example:
  - `types.py`
  - `credentials.py`
  - `cache.py`
  - `real_provider.py`
  - `mock_provider.py`
  - `fixtures.py`
- Tests that need import path adjustments.

**Out of scope**:

- Changing Google API behavior, OAuth scopes, cache TTLs, or mock fixture
  semantics.
- Changing public symbols imported from `classroom_downloader.google_provider`.
- Network calls or live Google verification.

## Git workflow

- Branch: `advisor/032-split-google-provider`.
- Commit one layer at a time.
- Do not push or open a PR unless instructed.

## Steps

### Step 1: Baseline

Run the backend suite in mock mode.

**Verify**: `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` exits 0.

### Step 2: Create a compatibility facade

Before moving code, decide which symbols are public by searching imports:

`rg "from .*google_provider|import .*google_provider" apps/api/src apps/api/tests`

After each move, `google_provider.py` must re-export those symbols so existing
imports continue to work.

**Verify**: the provider import check exits 0.

### Step 3: Move dataclasses/types

Move provider data models and protocol/base types into `google/types.py`.
Re-export them from `google_provider.py`.

Do not change field names or defaults.

**Verify**: backend suite passes or, for speed, run a focused provider/import
subset if one exists, then the full suite at the end.

### Step 4: Move credential helpers

Move credential encryption/decryption helpers into `google/credentials.py`.
Preserve current cryptography behavior and error handling.

**Verify**: auth/provider-related tests pass, then run the import check.

### Step 5: Move cache helpers

Move TTL cache helper classes/functions into `google/cache.py`. Preserve cache
keys and TTL behavior.

**Verify**: backend suite or focused provider tests pass.

### Step 6: Move mock fixtures and mock provider

Move fixture byte generation/corpus loading into `google/fixtures.py` and
`MockGoogleProvider` into `google/mock_provider.py`. Keep mock course/activity
IDs and file contents unchanged, including real-file corpus additions from
archived plan 027.

**Verify**: `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` passes.

### Step 7: Move real provider

Move the production Google provider implementation into `google/real_provider.py`.
Keep API calls, pagination, Drive metadata hydration, and error handling
unchanged.

**Verify**:

- provider import check exits 0.
- full backend suite passes.

### Step 8: Trim the facade

`google_provider.py` should contain only compatibility imports/re-exports and a
short comment explaining that the implementation now lives under
`classroom_downloader.google`.

**Verify**: full backend suite passes.

## Test plan

No new tests are required for a pure move. Existing mock-provider, auth, API,
grading, and extraction tests are the safety net.

## Done criteria

- [ ] `google_provider.py` is a small compatibility facade.
- [ ] Real provider, mock provider, credentials, cache helpers, fixtures, and
      types live in separate modules.
- [ ] Existing imports from `classroom_downloader.google_provider` still work.
- [ ] `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` exits 0.
- [ ] No files outside the in-scope list are modified.
- [ ] `plans/README.md` row for 032 updated.

## STOP conditions

Stop and report if:

- Moving code changes import-time side effects in a way that breaks fixtures.
- A public import cannot be preserved without a circular import.
- Tests require behavior changes rather than import-path fixes.

## Maintenance notes

After this lands, mock-provider additions should go to `google/mock_provider.py`
or fixture helpers, not the compatibility facade. Real Google API changes should
stay isolated in `google/real_provider.py`.
