# Plan 002: Characterization tests for the API cache layer and folder export

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat b61ac5a..HEAD -- apps/web/src/lib/api.ts apps/web/src/lib/folder-export.ts`
> If either file changed since this plan was written, compare the "Current
> state" excerpts against the live code before proceeding; on a mismatch, treat
> it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: plans/001-frontend-test-lint-baseline.md (the Vitest harness
  must exist first)
- **Category**: tests
- **Planned at**: commit `b61ac5a`, 2026-06-13

## Why this matters

`src/lib/api.ts` and `src/lib/folder-export.ts` hold the trickiest non-UI logic
in the frontend, and both are untested. `api.ts` implements a hand-rolled
stale-while-revalidate cache with in-flight request de-duplication, an
offline/connectivity signal, and version-skew detection — all stateful module
globals that are easy to break silently. `folder-export.ts` drives the File
System Access API and has subtle failure semantics: some errors abort the whole
export, others are collected per-file and reported. These are exactly the
behaviors that should be locked down with characterization tests *before* anyone
refactors `App.tsx` (Plan 005), which consumes both.

This plan writes focused unit tests that pin the *current* observable behavior.
It does not change production code. If a test reveals a genuine bug, do **not**
fix it here — record it and keep the test asserting current behavior (that is
what "characterization" means), unless the behavior is so clearly wrong that an
assertion would be meaningless; in that case STOP and report.

## Current state

### `src/lib/api.ts` (key behaviors to pin)

Module-level mutable state (top of file):
```ts
const responseCache = new Map<string, CacheEntry<unknown>>();
const inFlight = new Map<string, Promise<unknown>>();
const connectivityListeners = new Set<(offline: boolean) => void>();
const versionSkewListeners = new Set<(skewed: boolean) => void>();
let revalidationFailures = 0;
let offline = false;
let versionSkewNotified = false;
```

Exports that are directly testable without React:
- `class ApiError extends Error` (fields `status`, `code`, `message`).
- `apiErrorFromUnknown(caught, fallback)` — pass-through for `ApiError`, wraps
  `Error`, falls back otherwise (api.ts:54-58).
- `subscribeConnectivity(listener)` / `subscribeVersionSkew(listener)` — call
  the listener immediately with current state, return an unsubscribe fn
  (api.ts:60-70).
- The whole `api` object (api.ts:210-432) whose methods call `request()` →
  `fetchJson()` → global `fetch`.

The cache contract (`request()`, api.ts:119-164):
- GET responses are cached under key `` `GET ${path}` `` (api.ts:95-97).
- Default `ttlMs` is `30_000`; default `staleMs` is `ttlMs * 4` (api.ts:149-150).
- Within `freshUntil`: returns cached value, **no fetch**.
- Between `freshUntil` and `staleUntil`: returns cached value **and** triggers a
  background revalidation (api.ts:131-140).
- Concurrent identical GETs share one in-flight promise (api.ts:141-143,162).
- Non-GET methods are not cached unless an explicit `cacheKey` is passed.

`fetchJson()` (api.ts:166-208):
- On `fetch` throwing (network down): marks connectivity failure and throws
  `new ApiError(0, "unreachable", ...)` (api.ts:176-183).
- On `!response.ok`: parses `body.detail`; if `detail` is an object, uses
  `detail.code`/`detail.message`; else uses string detail or a status fallback
  (api.ts:185-200).
- `204` returns `undefined` (api.ts:204-206).
- Calls `checkAppVersion(response)` which compares header `X-App-Version` to the
  `__APP_VERSION__` build constant and notifies skew listeners once
  (api.ts:88-93).

Connectivity (api.ts:78-86): `markConnectivityFailure` sets `offline = true`
after `revalidationFailures >= 1`; `markConnectivitySuccess` resets to online.

### `src/lib/folder-export.ts` (full file — key behaviors)

- `isFolderExportSupported()` → `typeof window.showDirectoryPicker === "function"`.
- `exportJobToFolder(job, root, onProgress)` (folder-export.ts:68-87):
  - Iterates `job.files`; writes each via `writeExportFile`.
  - On success: `completed += 1`, calls `onProgress(completed, total, path)`.
  - On a **fatal** error (`isFatalExportError`: `DOMException` with name
    `NotAllowedError` or `QuotaExceededError`): re-throws, aborting the export.
  - On any other error: pushes `{ path, reason }` to `failed`, calls
    `onProgress(completed, total, "Falhou: <path>")`, continues.
  - Returns `{ completed, failed }`.
- `writeExportFile` (folder-export.ts:35-55): splits `file.output_path` on `/`,
  pops the filename, throws if empty, creates nested dirs via `ensureDirectory`,
  fetches `api.fileUrl(jobId, file.id)`, throws `Falha ao baixar ...` if the
  response is not ok or has no body, writes the blob, closes the writable.

## Commands you will need

| Purpose        | Command (from `apps/web`)     | Expected               |
|----------------|-------------------------------|------------------------|
| Install        | `pnpm install`                | exit 0                 |
| Run tests      | `pnpm test:run`               | exit 0, all pass       |
| Single file    | `pnpm vitest --run src/lib/api.test.ts` | that file passes |
| Typecheck+build| `pnpm build`                  | exit 0                 |

## Scope

**In scope** (create only):
- `apps/web/src/lib/api.test.ts`
- `apps/web/src/lib/folder-export.test.ts`

**Out of scope** (do NOT modify):
- `src/lib/api.ts`, `src/lib/folder-export.ts` — characterization only; no
  production changes. If you believe a test forces a code change, STOP.
- Any component test (`App.tsx`, grader components) — that's later work.
- The Vitest/ESLint config from Plan 001.

## Git workflow

- Branch: `advisor/002-frontend-core-logic-tests`
- Commit style: conventional commits, e.g.
  `test(web): characterize api cache layer and folder export`.
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Reset module state between tests

`api.ts` holds module-level singletons (the cache Map, `offline`, listener
sets). Vitest runs all tests in a file against one module instance, so tests
must avoid cross-contamination. Use `vi.resetModules()` + dynamic `import()` in
a `beforeEach`, or design each test to use distinct cache keys (distinct paths)
and always restore `globalThis.fetch`. Prefer dynamic re-import for the
connectivity/skew tests (which mutate global flags) and shared import for the
pure-function tests.

Pattern for a fresh module per test:
```ts
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

let mod: typeof import("./api");

beforeEach(async () => {
  vi.resetModules();
  mod = await import("./api");
});

afterEach(() => {
  vi.restoreAllMocks();
});
```

**Verify**: a trivial `it("imports", () => expect(mod.api).toBeDefined())`
passes under `pnpm vitest --run src/lib/api.test.ts`.

### Step 2: Test the pure helpers and subscriptions

In `src/lib/api.test.ts`, cover:
- `apiErrorFromUnknown`: returns the same `ApiError` instance when given one;
  wraps a plain `Error` (preserving `.message`, `status === 0`, `code` undefined);
  uses the fallback string for non-Error input.
- `subscribeConnectivity`: the listener is invoked **immediately** with the
  current offline state (false on a fresh module); the returned function
  unsubscribes (after calling it, a later state change does not call the
  listener). To drive a state change, mock `fetch` to reject and call an `api`
  GET method, then assert the listener saw `true`.
- `subscribeVersionSkew`: listener invoked immediately with `false`.

**Verify**: `pnpm vitest --run src/lib/api.test.ts` → these pass.

### Step 3: Test the cache + in-flight behavior

Mock the global `fetch` with `vi.stubGlobal("fetch", vi.fn())` returning a
`Response`-like object. Helper:
```ts
function jsonResponse(body: unknown, init: { status?: number; headers?: Record<string,string> } = {}) {
  return {
    ok: (init.status ?? 200) < 400,
    status: init.status ?? 200,
    headers: { get: (k: string) => init.headers?.[k] ?? null },
    json: async () => body,
  } as unknown as Response;
}
```
Cover, using an `api` GET method (e.g. `api.courses()` hits `/api/courses` with
`ttlMs: 120_000`):
- **Fresh hit**: two sequential `api.courses()` calls → `fetch` called once
  (second served from cache).
- **In-flight dedup**: two *concurrent* `api.courses()` (don't await the first)
  → `fetch` called once; both resolve to the same value.
- **Stale-while-revalidate**: use `vi.useFakeTimers()` and `vi.setSystemTime` to
  advance past `freshUntil` but before `staleUntil`; assert the call returns the
  cached value synchronously *and* a background `fetch` fires. (If faking time
  against `Date.now()` proves brittle, assert the simpler fresh/dedup behaviors
  and note SWR as covered-by-inspection in your report — do not change source.)

**Verify**: `pnpm vitest --run src/lib/api.test.ts` → all pass.

### Step 4: Test `fetchJson` error mapping

Through any `api` method, with `fetch` mocked:
- Network throw → rejects with `ApiError` whose `code === "unreachable"` and
  `status === 0`.
- `{ ok:false, status:404, json: { detail: { code:"x", message:"m" } } }` →
  `ApiError(404, "x", "m")`.
- `{ ok:false, status:500, json: { detail: "plain string" } }` →
  `ApiError(500, undefined, "plain string")`.
- `204` response on a method that can return 204 (e.g. `deleteGradingJob`) →
  resolves to `undefined`.

**Verify**: `pnpm vitest --run src/lib/api.test.ts` → all pass.

### Step 5: Test folder export semantics

In `src/lib/folder-export.test.ts`, build fakes for the File System Access
handles (plain objects with `vi.fn()` methods) and stub `fetch`:
```ts
function fakeDir() {
  const dir: any = {
    getDirectoryHandle: vi.fn(async () => fakeDir()),
    getFileHandle: vi.fn(async () => ({
      createWritable: vi.fn(async () => ({
        write: vi.fn(async () => {}),
        close: vi.fn(async () => {}),
      })),
    })),
  };
  return dir;
}
```
Cover `exportJobToFolder`:
- **All succeed**: a job with 2 files, `fetch` returns `{ ok:true, body:{}, blob:async()=>new Blob() }`
  → returns `{ completed: 2, failed: [] }`; `onProgress` called twice with
  increasing `completed`.
- **Per-file failure is collected**: make `fetch` reject for one file (or return
  `ok:false`) → that file appears in `failed` with its `output_path`, the other
  completes, no throw. `onProgress` is called with a `"Falhou: ..."` label.
- **Fatal error aborts**: make a write throw `new DOMException("nope","NotAllowedError")`
  → `exportJobToFolder` rejects (does not resolve with a summary).
- **Empty filename guard**: a file whose `output_path` ends in `/` → that file
  lands in `failed` (its `writeExportFile` throws "Caminho de saída inválido"),
  not a crash. Construct `ExportFile`/`ExportJob` shapes minimally; import the
  types from `../types` and satisfy only the fields the code reads
  (`job.id`, `job.files`, `file.id`, `file.output_path`).

**Verify**: `pnpm vitest --run src/lib/folder-export.test.ts` → all pass.

### Step 6: Full suite + build

**Verify**: `pnpm test:run` → exit 0, all tests pass (smoke from 001 + new).
`pnpm build` → exit 0.

## Test plan

- `src/lib/api.test.ts`: pure helpers, subscriptions, cache fresh-hit, in-flight
  dedup, SWR (best-effort), error mapping, 204.
- `src/lib/folder-export.test.ts`: all-succeed, per-file failure collection,
  fatal-abort, invalid-path guard.
- Structural pattern: the smoke test from Plan 001; mock globals with
  `vi.stubGlobal` and restore in `afterEach`.
- Verification: `pnpm test:run` → all pass.

## Done criteria

Machine-checkable. ALL must hold (from `apps/web`):

- [ ] `pnpm test:run` exits 0
- [ ] `src/lib/api.test.ts` exists and contains tests for: error mapping,
      cache fresh-hit, in-flight dedup, and `apiErrorFromUnknown`
- [ ] `src/lib/folder-export.test.ts` exists and contains tests for: all-succeed,
      per-file failure, and fatal-abort
- [ ] `pnpm build` exits 0
- [ ] No production source modified — only the two test files added (`git status`)
- [ ] `plans/README.md` status row for 002 updated

## STOP conditions

Stop and report back (do not improvise) if:

- A test can only pass by changing `api.ts` or `folder-export.ts` (production
  code is out of scope here).
- The Vitest harness from Plan 001 is absent or broken (`pnpm test:run` errors
  on config) — Plan 001 must land first.
- Faking time for the SWR test causes flakiness you cannot stabilize in two
  attempts — assert the deterministic behaviors, document SWR as
  inspected-not-automated, and continue (this is not a hard failure).
- A characterization test surfaces behavior so clearly broken that asserting it
  would encode a bug — report it instead of asserting.

## Maintenance notes

- These are characterization tests: they encode *current* behavior. If a future
  change intentionally alters cache TTLs or export error handling, the test
  expectations must be updated deliberately, not deleted.
- When Plan 005 decomposes `App.tsx`, these tests are the safety net for the
  cache/export logic it relies on — keep them green throughout that refactor.
- A reviewer should check that global `fetch` and FS handles are restored after
  each test (no leakage between tests via `responseCache`/`offline`).
