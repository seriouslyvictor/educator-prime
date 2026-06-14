# Plan 005: Decompose the 1380-line App.tsx into cohesive hooks

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. This is a LARGE, incremental refactor — the build must stay green
> after every step, and you may stop at a clean intermediate point and report
> progress. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done (or at a clean stopping point), update
> the status row for this plan in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat b61ac5a..HEAD -- apps/web/src/App.tsx`
> If `App.tsx` changed since this plan was written, re-read it fully and map the
> current functions to the groupings below before proceeding; on a structural
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: L
- **Risk**: MED
- **Depends on**: plans/001-frontend-test-lint-baseline.md AND
  plans/002-frontend-core-logic-tests.md (the cache/export safety net must exist
  before refactoring the component that orchestrates them)
- **Category**: tech-debt
- **Planned at**: commit `b61ac5a`, 2026-06-13

## Why this matters

`apps/web/src/App.tsx` is 1380 lines with ~33 `useState`/`useMemo`/`useEffect`
hooks in a single component. It is the most-churned frontend file
(15 commits in the last 60) and the hub through which every feature flows: auth,
export, the grading queue, and the entire grading-job lifecycle (create → infer
→ audit → draft → review → wrap), including the SSE streaming state machine. Its
size makes it hard to test, hard to change without unintended coupling, and a
merge-conflict magnet. Decomposing it into cohesive custom hooks shrinks the
component to a view router and isolates each concern so it can be reasoned about
and (later) tested in isolation.

This is a **behavior-preserving** refactor. The app must look and act identically
before and after. Because component-level tests do not yet exist, the safety net
is: (a) the build/typecheck, (b) the Plan 002 tests for the cache/export logic
these hooks call, and (c) the manual smoke checklist below. Move in small,
independently-verifiable steps.

## Current state

`App.tsx` exports `function App()` (line 140) plus two small local components at
the bottom: `GradingHealthBanner` (line 1359) and the helper functions
`appError`, `appErrorSummary`, `readStoredJobId`, `writeStoredJobId`,
`gradingItemFromJob` (lines 73-138).

The state and functions cluster into four cohesive concerns. Map (verify against
the live file):

1. **Connection / auth** — state: `auth`, `loading`, `apiOffline`,
   `versionSkew`, `gradingHealth`. Functions: `bootstrap` (264),
   `connectClassroom` (340), `logoutClassroom` (357); derived `connected`,
   `partialConsent`, `gateError`, `handleGateAction`; the
   `subscribeConnectivity`/`subscribeVersionSkew` effects (217-219).

2. **Course/export workspace** — state: `courses`, `activities`,
   `selectedCourseId`, `selectedActivityIds`, `classQuery`, `activityQuery`,
   `dryRunOpen`, `job` (ExportJob), `lastResult`, `activitiesLoading`,
   `progress`, `progressLog`. Functions: `loadCourses` (312),
   `loadActivities` (321), `startExport` (381), `pickCourse` (447),
   `previewActivity` (458); derived `selectedCourse`, `selectedActivities`,
   `previewTree`, `deliveryMode`, `folderSupported`.

3. **Grading queue** — state: `gradingQueue`, `archivedQueue`, `pendingQueue`,
   `gradingQueueLoading`, `selectedGradingItem`. Functions:
   `loadGradingQueue` (570), `runQueueAction` (588),
   `sendActivitiesToQueue` (510), `findExistingJob` (558); derived
   `gradingByActivity`, `queueItems`.

4. **Grading job lifecycle** — state: `gradingJob`, `privacyAudit`,
   `activeGradingSubmissionId`, `draftingSubmissionId`, `graderBusy`,
   `gradingProgress`. Functions: `gradeActivity` (464),
   `beginGradingSetup` (493), `regradeActivity` (534), `openGradingJob` (686),
   `restoreGradingJob` (669), `streamGradingProgress` (713),
   `seedDraftQueue` (821), `applyDraftSubmission` (827),
   `runCriteriaStream` (845), `matchingReadyJob` (863),
   `inferGradingCriteria` (879), `startGradingAuditForItem` (929),
   `runGradingPrivacyAudit` (1005), `runInferGradingCriteria` (1016),
   `rerunGradingPrivacyAudit` (1026), `continueToGradingDraft` (1048),
   `acceptGradingDraft` (1091), `retryGradingDraft` (1120),
   `deleteGradingCache` (1135); the `writeStoredJobId` sync effect (228).

Cross-cutting: `view`/`setView` (the `AppView` router) and `error`/`setError`
are touched by all four. The big `return` (1148-1357) is the view switch.

Conventions to match:
- Custom hooks live alongside lib code; create `apps/web/src/hooks/` for them
  (no hooks dir exists yet — this is the natural home). Name files
  `useConnection.ts`, `useExportWorkspace.ts`, `useGradingQueue.ts`,
  `useGradingJob.ts`.
- The repo uses function components and plain hooks (no Redux/Zustand). Keep that.
- pt-BR user strings unchanged; English code.

## Commands you will need

| Purpose         | Command (from `apps/web`) | Expected         |
|-----------------|---------------------------|------------------|
| Typecheck+build | `pnpm build`              | exit 0           |
| Tests           | `pnpm test:run`           | exit 0           |
| Lint            | `pnpm lint`               | no NEW errors    |
| Dev server      | `pnpm dev`                | serves on :5173 for manual smoke |

The backend must run in mock mode for manual smoke: from `apps/api`,
`uv run --extra dev python -m uvicorn classroom_downloader.main:app --app-dir src --reload --port 8000`.

## Scope

**In scope**:
- `apps/web/src/App.tsx` (shrink to composition + view router)
- `apps/web/src/hooks/useConnection.ts` (create)
- `apps/web/src/hooks/useExportWorkspace.ts` (create)
- `apps/web/src/hooks/useGradingQueue.ts` (create)
- `apps/web/src/hooks/useGradingJob.ts` (create)
- Optionally `apps/web/src/hooks/*.test.ts` if you add hook tests (encouraged for
  `useGradingJob`'s stream reducer logic).

**Out of scope** (do NOT touch):
- Any child component (`GraderSetup`, `GraderReview`, `GraderQueue`,
  `GraderWrap`, `TurmasView`, etc.) — their props must not change. The hooks feed
  the same props the component currently passes.
- `src/lib/api.ts`, `folder-export.ts` behavior.
- The `AppView` type and the set of views.
- Any change to user-visible text, styling, or routing behavior.

## Git workflow

- Branch: `advisor/005-decompose-app-tsx`
- Commit per extracted hook (4-5 commits), each with a green build. Conventional
  commits, e.g. `refactor(web): extract useGradingQueue from App`.
- Do NOT push or open a PR unless instructed.

## Strategy

Extract one concern at a time, lowest-coupling first, building after each. The
hooks accept the shared `view`/`setView` and an error setter as parameters so
the cross-cutting state stays owned by `App`. Each hook returns the state values
and callbacks the JSX currently uses, named identically, so the `return` block
changes only by sourcing names from `const { ... } = useX(...)` instead of local
declarations.

Recommended order: (1) `useConnection`, (2) `useExportWorkspace`,
(3) `useGradingQueue`, (4) `useGradingJob`. The last is the largest; it depends
on `loadGradingQueue` from (3), so pass that in as a parameter.

## Steps

### Step 1: Baseline — confirm green and capture behavior

Run `pnpm build`, `pnpm test:run`, and start the app (backend in mock mode) to
walk the manual smoke checklist (see Test plan) once *before* changing anything,
so you know the target behavior. Record any pre-existing console errors.

**Verify**: `pnpm build` → exit 0; `pnpm test:run` → exit 0.

### Step 2: Extract `useConnection`

Create `src/hooks/useConnection.ts` exporting a hook that owns `auth`, `loading`,
`apiOffline`, `versionSkew`, `gradingHealth` and the functions `bootstrap`,
`connectClassroom`, `logoutClassroom`, plus derived `connected`,
`partialConsent`. It needs `setView` and a `setError`/`onResetWorkspace`
callback passed in (because `bootstrap`/`logout` set the view and clear other
state). Return everything `App` currently reads. `bootstrap` calls
`loadCourses` and `loadGradingQueue` — for this first step, accept those as
injected callbacks (or keep `bootstrap` in `App` and move only the simpler
pieces). Prefer the smallest extraction that builds.

In `App.tsx`, replace the moved local declarations with
`const { auth, loading, ... } = useConnection({ setView, ... });`.

**Verify**: `pnpm build` → exit 0; `pnpm test:run` → exit 0; manual smoke of the
connect → workspace transition still works.

### Step 3: Extract `useExportWorkspace`

Move the course/activity/export concern (state + `loadCourses`,
`loadActivities`, `startExport`, `pickCourse`, `previewActivity`, and derived
`selectedCourse`/`selectedActivities`/`previewTree`). It owns the File System
Access export flow (which calls `pickExportFolder`/`exportJobToFolder` — covered
by Plan 002 tests). Pass in `setView`, `setError`, and the history hook results
it needs (`addHistoryItem`).

**Verify**: `pnpm build` → 0; `pnpm test:run` → 0; manual smoke: pick a course,
preview, and run an export end-to-end in mock mode.

### Step 4: Extract `useGradingQueue`

Move `gradingQueue`, `archivedQueue`, `pendingQueue`, `gradingQueueLoading`,
`selectedGradingItem`, and `loadGradingQueue`, `runQueueAction`,
`sendActivitiesToQueue`, `findExistingJob`, plus derived `gradingByActivity`,
`queueItems`. `runQueueAction` clears the active job when it deletes it — pass in
a `clearActiveJob` callback that the job hook (Step 5) will provide, or keep that
branch in `App` for now and wire it in Step 5.

**Verify**: `pnpm build` → 0; `pnpm test:run` → 0; manual smoke: send activities
to queue, archive/restore/remove a queue item.

### Step 5: Extract `useGradingJob`

The largest. Move `gradingJob`, `privacyAudit`, `activeGradingSubmissionId`,
`draftingSubmissionId`, `graderBusy`, `gradingProgress`, the
`writeStoredJobId` sync effect, and all functions listed under concern 4 above,
**including the `streamGradingProgress` SSE state machine** (lines 713-817 —
move it verbatim; do not "improve" the reconnect logic). It depends on
`loadGradingQueue` (from Step 4) and `setView`/`setError` — pass them in. Provide
`clearActiveJob` back to the queue hook to close the Step 4 loop.

Consider adding `src/hooks/useGradingJob.test.ts` that unit-tests the pure
reducers `applyDraftSubmission` and `seedDraftQueue` if you export them — these
have real logic (dedupe, recompute counts) and are cheap to pin. Optional but
encouraged.

**Verify**: `pnpm build` → 0; `pnpm test:run` → 0; manual smoke: open a ready
job → setup → audit → draft (watch the streaming progress) → review → accept all
→ wrap screen. This exercises the SSE machine end-to-end.

### Step 6: Final shrink and review

`App.tsx` should now be: imports, the small pure helpers (or move them into the
relevant hook files), `const { ... } = useConnection(...)` etc., the keyboard
effect, and the `return` view router. Confirm no orphaned state or unused
imports remain (`pnpm lint` should not report new unused-var errors in
`App.tsx`).

**Verify**: `pnpm build` → 0; `pnpm test:run` → 0; `pnpm lint` shows no new
errors in `App.tsx` vs. the Step 1 baseline; full manual smoke checklist passes.

## Test plan

- Lean on Plan 002's cache/export tests as the regression net for the logic the
  hooks call.
- Optionally add `useGradingJob.test.ts` for `applyDraftSubmission`/
  `seedDraftQueue` reducers (pure, high-value).
- **Manual smoke checklist** (mock mode — `CD_GOOGLE_PROVIDER=mock`, the
  default), run before and after:
  1. Connect → lands in workspace.
  2. Pick a course; activities load; preview opens the dry-run drawer.
  3. Run a folder export → progress view → done view → history.
  4. Send activities to the grader queue; archive, restore, remove an item.
  5. Open a ready job → setup → run audit → continue to draft (streaming
     progress shows and completes) → review → accept a submission → reach wrap.
  6. Reload mid-job: the active job is restored (localStorage pointer).
  7. Logout clears everything back to connect.
- Verification: every checklist item behaves identically to the Step 1 baseline.

## Done criteria

Machine-checkable + observable. ALL must hold (from `apps/web`):

- [ ] `pnpm build` exits 0
- [ ] `pnpm test:run` exits 0
- [ ] `apps/web/src/hooks/` contains `useConnection.ts`, `useExportWorkspace.ts`,
      `useGradingQueue.ts`, `useGradingJob.ts`
- [ ] `App.tsx` line count is materially reduced (target: under ~400 lines;
      report the actual `wc -l`)
- [ ] No child-component prop signatures changed (`git diff` touches only
      `App.tsx` and the new `hooks/` files)
- [ ] The manual smoke checklist passes identically to the Step 1 baseline
- [ ] `pnpm lint` reports no new errors in `App.tsx` vs. baseline
- [ ] `plans/README.md` status row for 005 updated

## STOP conditions

Stop and report back (do not improvise) if:

- Extracting a hook requires changing a child component's props — the seam is
  wrong; report rather than reshaping the component API.
- The `streamGradingProgress` SSE machine resists a verbatim move (closures over
  `setGradingProgress`/`settled`) — report the specific coupling instead of
  rewriting its reconnect/finish logic.
- A manual smoke step behaves differently after a step and you cannot restore
  parity within one fix attempt — revert that step's commit and report.
- Plan 001/002's test harness is absent — those must land first; this refactor
  without the net is too risky.
- You reach a clean intermediate point (e.g. 2 of 4 hooks extracted, build green)
  and judge the remaining extraction needs design discussion — commit the green
  state, update the status row to IN PROGRESS with a note, and report.

## Maintenance notes

- After this lands, new grading features should extend the relevant hook, not
  re-grow `App.tsx`.
- The hooks deliberately keep `view`/`setView` and `error` in `App` as shared
  state passed down; if that wiring becomes unwieldy, a follow-up could introduce
  a small context — explicitly deferred here to keep this refactor mechanical.
- A reviewer should diff behavior, not just code: confirm the view-routing
  conditions in the `return` block are unchanged and every callback prop still
  points at the same logic.
- This is a candidate for multiple PRs (one per hook) if a single PR is too large
  to review — each step is independently green.

## Execution note - 2026-06-13

- Clean intermediate completed: extracted `apps/web/src/hooks/useConnection.ts`
  from `App.tsx` and kept the existing auth/bootstrap/connect/logout behavior.
- Follow-up progress in the resumed run: extracted
  `apps/web/src/hooks/useExportWorkspace.ts` and
  `apps/web/src/hooks/useGradingQueue.ts`. `App.tsx` line count is now 1073.
- Verification completed after the first extraction: `pnpm build` passed and
  `pnpm test:run` passed (21 tests). Verification completed after the export and
  queue extractions: `pnpm exec tsc -b` passed.
- Not marked DONE: `useGradingJob` remains in `App.tsx`, the full Vite
  build/Vitest/manual smoke checklist has not been run after the latest
  extractions, and the latest extraction is not committed yet.
- Current blocker: unsandboxed build/test/commit approvals are unavailable until
  the account usage limit clears (reported by the app as available again on
  2026-06-14 01:19). Continue with full `pnpm build`, `pnpm test:run`, then
  `useGradingJob` extraction and manual smoke when approvals are available.
- Lint status: `pnpm lint` still exits 1 because of the pre-existing
  `GraderSetup.tsx` `selectedRubric` unused-variable error; no new `App.tsx`
  lint errors were introduced.
