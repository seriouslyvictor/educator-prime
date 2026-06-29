# Plan 030: Extract a testable grading EventSource client and reducer

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If a STOP condition occurs, stop and report; do not improvise.
> When done, update this plan's row in `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 035af04..HEAD -- apps/web/src/hooks/useGradingJob.ts apps/web/src/lib/ apps/web/src/hooks/`
> If `useGradingJob.ts` changed, re-read it fully before proceeding.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `035af04`, 2026-06-29

## Why this matters

`useGradingJob.ts` owns grading workflow state, API commands, navigation, and the
EventSource streaming implementation. The streaming code has reconnect/resume
behavior that is important but hard to test while nested inside the hook. This
plan extracts the stream client and pure state transitions without changing the
grading UI or endpoint calls.

## Current state

Relevant live shapes to confirm:

- `apps/web/src/hooks/useGradingJob.ts` is about 690 lines.
- `streamGradingProgress` lives near lines 152-256 and creates an
  `EventSource`, parses JSON events, updates progress, calls `onPayload`, and
  handles reconnect delays.
- Workflow functions in the same hook include `inferGradingCriteria`,
  `startGradingAuditForItem`, `continueToGradingDraft`, and
  `acceptGradingDraft`.
- Existing tests in `useGradingJob.test.ts` cover pure helpers such as
  `mergeDraftSubmission`, not the streaming orchestration.

Conventions:

- Frontend uses React hooks and Vitest.
- Pure helpers can be exported from hook modules for direct Vitest coverage.
- User-facing strings are pt-BR; code identifiers are English.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Unit tests | `pnpm test:run` | all pass |
| Build/typecheck | `pnpm build` | exit 0 |
| Lint | `pnpm lint` | no new errors |

Run from `apps/web`.

## Scope

**In scope**:

- `apps/web/src/hooks/useGradingJob.ts`
- New focused files such as:
  - `apps/web/src/hooks/gradingProgress.ts`
  - `apps/web/src/lib/gradingEventSource.ts`
  - `apps/web/src/hooks/useGradingJob.test.ts`
  - New test files next to the extracted helpers.

**Out of scope**:

- Endpoint paths and API client behavior.
- Child component props.
- `App.tsx` hook wiring, except import path adjustments if required.
- Any styling or copy change.

## Git workflow

- Branch: `advisor/030-extract-grading-eventsource-client`.
- Commit the pure reducer extraction before the EventSource client extraction.
- Do not push or open a PR unless instructed.

## Steps

### Step 1: Baseline

Run frontend tests and build before editing.

**Verify**: `pnpm test:run` and `pnpm build` both exit 0. If they do not, stop
and report the pre-existing failure.

### Step 2: Extract pure progress/job merge helpers

Move pure helpers such as `mergeDraftSubmission`, queue seeding logic, and any
payload-to-state transformation into `hooks/gradingProgress.ts` or a similarly
named module. Keep behavior identical and re-export as needed so existing tests
still pass.

Add or update Vitest tests to cover:

- merging a drafted submission into an existing job
- adding a new streamed submission without duplicating existing rows
- progress completion/error payloads if represented by pure helpers

**Verify**: `pnpm test:run` exits 0.

### Step 3: Extract EventSource transport

Create `lib/gradingEventSource.ts` with a small function or class that owns:

- constructing `EventSource`
- parsing JSON messages
- invoking callbacks for payload/error/done
- closing the stream
- reconnect delay behavior currently in `streamGradingProgress`

Keep the public behavior identical. The hook should call this helper and keep
owning React state/navigation decisions.

**Verify**: `pnpm build` exits 0.

### Step 4: Add deterministic tests for the extracted stream client

Use Vitest with a fake `EventSource` implementation. Test at least:

- a valid JSON message calls the payload callback
- malformed JSON calls the error path or is ignored exactly as today
- `close` is called when the stream settles
- reconnect/resume callback behavior matches the existing implementation

Do not add browser/e2e tests for this plan unless unit tests cannot express the
behavior.

**Verify**: `pnpm test:run` exits 0.

### Step 5: Shrink `useGradingJob`

Remove now-unused local transport code and import the new helpers. The hook
should still own workflow commands and state, but the raw EventSource mechanics
should live outside it.

**Verify**:

- `pnpm test:run` exits 0.
- `pnpm build` exits 0.
- `pnpm lint` reports no new errors.

## Test plan

- New or expanded Vitest coverage for pure grading progress helpers.
- New Vitest coverage for the EventSource client using a fake EventSource.
- Existing app tests and build remain green.

## Done criteria

- [ ] Raw `new EventSource(...)` construction no longer lives inside
      `useGradingJob.ts`.
- [ ] Stream parsing/reconnect behavior is covered by Vitest.
- [ ] `useGradingJob.ts` is materially smaller and still exports/returns the
      same workflow surface to callers.
- [ ] `pnpm test:run`, `pnpm build`, and `pnpm lint` pass from `apps/web`
      except for documented pre-existing lint warnings/errors.
- [ ] No files outside the in-scope list are modified.
- [ ] `plans/README.md` row for 030 updated.

## STOP conditions

Stop and report if:

- Extracting the stream client requires changing endpoint URLs or SSE event
  payload shapes.
- Fake EventSource tests cannot reproduce the existing reconnect behavior
  without changing production code.
- Any child component prop signature would need to change.

## Maintenance notes

Future streaming workflows should reuse the extracted EventSource helper instead
of embedding a second stream loop inside another hook.
