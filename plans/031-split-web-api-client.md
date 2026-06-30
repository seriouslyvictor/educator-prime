# Plan 031: Split the web API client into transport, cache, and endpoint modules

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If a STOP condition occurs, stop and report; do not improvise.
> When done, update this plan's row in `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 035af04..HEAD -- apps/web/src/lib/api.ts apps/web/src/lib/ apps/web/src/hooks/`
> If `api.ts` changed, re-read it and preserve all public method names.

## Status

**Status**: DONE

Note: `pnpm e2e` could not run locally — the playwright harness requires a live
backend server on port 8000 (real Google credentials). Gates `pnpm test:run`,
`pnpm build`, and `pnpm lint` all passed (51/51 tests, clean build, 0 new lint
errors).

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/030-extract-grading-eventsource-client.md recommended
- **Category**: tech-debt
- **Planned at**: commit `035af04`, 2026-06-29

## Why this matters

`apps/web/src/lib/api.ts` mixes transport, response caching, in-flight request
dedupe, offline/version-skew events, cache invalidation, and the endpoint
catalog. Adding or changing one endpoint requires understanding global cache
behavior and repeated invalidation strings. Splitting the file creates clearer
ownership without changing the exported `api` object used by the app.

## Current state

Relevant live shapes to confirm:

- `api.ts` is about 420 lines.
- Global state near the top includes `responseCache`, `inFlight`, listeners,
  revalidation failures, offline state, and version-skew state.
- `request<T>` and `fetchJson` implement transport/cache behavior.
- The exported `api` object starts around the middle of the file and contains
  course, auth, export, grading, queue, admin, and cache deletion methods.
- Several grading mutations manually call `clearApiCache` with route prefixes.

Conventions:

- Callers import `{ api } from "../lib/api"` or similar. Preserve that public
  import path.
- Use TypeScript modules with named exports.
- Do not introduce a new HTTP library.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Unit tests | `pnpm test:run` | all pass |
| Build/typecheck | `pnpm build` | exit 0 |
| Lint | `pnpm lint` | no new errors |
| E2E | `pnpm e2e` | all pass |

Run from `apps/web`.

## Scope

**In scope**:

- `apps/web/src/lib/api.ts`
- New files under `apps/web/src/lib/api/`, for example:
  - `client.ts`
  - `cache.ts`
  - `auth.ts`
  - `courses.ts`
  - `grading.ts`
  - `admin.ts`
  - `types.ts`
- Existing tests that import API helpers, if any.

**Out of scope**:

- Endpoint URLs, request/response shapes, or cache TTL values.
- Hook behavior.
- Backend routes.
- New state-management libraries.

## Git workflow

- Branch: `advisor/031-split-web-api-client`.
- Commit by layer: cache/client extraction, then endpoint grouping.
- Do not push or open a PR unless instructed.

## Steps

### Step 1: Baseline

Run frontend tests and build.

**Verify**: `pnpm test:run` and `pnpm build` exit 0.

### Step 2: Extract cache and connectivity state

Create `lib/api/cache.ts` for response cache, in-flight map, listeners,
connectivity/version-skew state, and `clearApiCache`. Export the same functions
currently used by callers.

Keep behavior and default TTLs identical.

**Verify**: `pnpm test:run` and `pnpm build` exit 0.

### Step 3: Extract transport client

Create `lib/api/client.ts` for `request<T>` and `fetchJson`. It should import
cache helpers from `cache.ts` and preserve existing error handling, stale
revalidation, and version-skew/offline notifications.

**Verify**: `pnpm build` exits 0.

### Step 4: Split endpoint groups

Move endpoint methods into focused modules such as `auth.ts`, `courses.ts`,
`grading.ts`, and `admin.ts`. Each module should export a plain object of
methods. Reassemble the public `api` object in `lib/api.ts` so callers do not
change imports.

**Verify**: `pnpm test:run` and `pnpm build` exit 0.

### Step 5: Centralize invalidation helpers

In the grading endpoint module, replace repeated string lists with small named
helpers such as `invalidateGradingList()` and `invalidateGradingJob(jobId)` if
that can be done without behavior changes. Keep the exact same route prefixes.

**Verify**: `pnpm test:run` exits 0.

### Step 6: Full frontend verification

Run the full frontend gate.

**Verify**:

- `pnpm test:run` exits 0.
- `pnpm build` exits 0.
- `pnpm lint` reports no new errors.
- `pnpm e2e` exits 0.

## Test plan

No new tests are required if all endpoint exports and cache behavior are pure
moves. Add tests only if you create new invalidation helper functions with
non-trivial branching.

## Done criteria

- [ ] `apps/web/src/lib/api.ts` is a public facade, not the home of all
      transport/cache/endpoint implementation.
- [ ] Existing imports of `{ api } from ".../lib/api"` still work.
- [ ] Cache invalidation route prefixes are unchanged.
- [ ] `pnpm test:run`, `pnpm build`, `pnpm lint`, and `pnpm e2e` pass from
      `apps/web` except for documented pre-existing lint issues.
- [ ] No files outside the in-scope list are modified.
- [ ] `plans/README.md` row for 031 updated.

## STOP conditions

Stop and report if:

- A caller import must change outside the in-scope area.
- Splitting transport changes cache/offline behavior.
- E2E failures suggest stale cache invalidation changed.

## Maintenance notes

After this lands, new endpoints should be added to their domain module and
re-exported through the facade. Reviewers should check cache invalidation
explicitly for every mutation.
