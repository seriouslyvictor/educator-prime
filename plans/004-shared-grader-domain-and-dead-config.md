# Plan 004: Consolidate duplicated grader helpers; resolve the dead session_secret_key

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat b61ac5a..HEAD -- apps/web/src/components/grader/ apps/api/src/classroom_downloader/settings.py`
> If any of those changed since this plan was written, compare the "Current
> state" excerpts against the live code before proceeding; on a mismatch, treat
> it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none for Part A. Part B interacts with
  plans/003-encrypt-oauth-credentials-at-rest.md (see Part B guard).
- **Category**: tech-debt
- **Planned at**: commit `b61ac5a`, 2026-06-13

## Why this matters

**Part A (duplication):** Four small grader-domain helpers are copy-pasted across
three components, with an explicit "duplicated to avoid circular deps" comment.
When the score thresholds or the Classroom URL shape change, they must be edited
in lockstep — exactly the kind of drift that silently diverges (e.g. one file
uses `>= 85` for "good", another forgets to update). A single
`grader/domain.ts` module is the project's actual domain vocabulary and removes
the drift risk for near-zero cost.

**Part B (dead config):** `session_secret_key` is defined in `settings.py:42`
but read nowhere in `src/`. Dead config is misleading — a future contributor may
assume sessions are signed with it. It should either be removed or given a
purpose. Plan 003 gives it a purpose (credential encryption). This plan handles
the case where 003 has *not* landed.

## Current state

### Part A — duplicated helpers (verified locations)

- `apps/web/src/components/grader/GraderWrap.tsx:14-28`:
  ```ts
  function scoreOf(submission: GradingSubmission): number | null {
    return submission.final_score ?? submission.ai_score ?? null;
  }
  function studentLabel(submission: GradingSubmission): string {
    return submission.student_name ?? submission.student_email ?? "Aluno desconhecido";
  }
  function classroomActivityUrl(job: GradingJob): string {
    return `https://classroom.google.com/c/${job.course_id}/a/${job.activity_id}/details`;
  }
  ```
- `apps/web/src/components/grader/pip/PostingPiP.tsx:11-30` — has the same
  `scoreOf`, `studentLabel`, `classroomActivityUrl`, **plus**:
  ```ts
  function scoreColor(g: number | null): string {
    if (g == null) return "var(--muted-2)";
    return g >= 85 ? "var(--ink)" : g >= 65 ? "var(--warning)" : "var(--danger)";
  }
  ```
  The PostingPiP comment reads `// mirrors GraderWrap helpers — duplicated to
  avoid circular deps`.
- `apps/web/src/components/grader/GraderReview.tsx:36` — its own copy of
  `studentLabel`.

These are pure functions of `GradingSubmission` / `GradingJob` (types in
`apps/web/src/types.ts`). A standalone module has no circular-dependency risk —
the "duplicated to avoid circular deps" comment is about importing between
sibling components, which a leaf `domain.ts` avoids.

Note: `PostingPiP.tsx` also defines `postingFeedbackText(submission)` returning
`submission.feedback ?? ""`. That one is local; leave it unless you find an
identical copy elsewhere.

### Part B — dead config

- `apps/api/src/classroom_downloader/settings.py:42`:
  `session_secret_key: str | None = None`
- `grep -rn "session_secret_key" apps/api/src` returns only that definition
  (plus a compiled `.pyc`). No consumer.

## Commands you will need

| Purpose             | Command                                    | Expected         |
|---------------------|--------------------------------------------|------------------|
| Web typecheck+build | `pnpm build` (from `apps/web`)             | exit 0           |
| Web tests           | `pnpm test:run` (from `apps/web`)          | exit 0 (if Plan 001 landed) |
| API tests           | `uv run --extra dev pytest -q` (from `apps/api`) | all pass   |
| Find dup helpers    | `grep -rn "function scoreOf\|function studentLabel\|function scoreColor\|function classroomActivityUrl" apps/web/src` | should shrink to the new module after Part A |

## Scope

**In scope**:
- `apps/web/src/components/grader/domain.ts` (create)
- `apps/web/src/components/grader/GraderWrap.tsx` (remove local helpers, import)
- `apps/web/src/components/grader/pip/PostingPiP.tsx` (remove local helpers, import)
- `apps/web/src/components/grader/GraderReview.tsx` (remove local `studentLabel`,
  import)
- `apps/api/src/classroom_downloader/settings.py` (Part B, conditional)

**Out of scope** (do NOT touch):
- The *behavior* of any helper — this is a pure move; the function bodies must be
  byte-for-byte identical to the existing ones (same thresholds, same strings).
- Any other component or any backend file besides `settings.py`.
- `postingFeedbackText` unless you find a verified duplicate.

## Git workflow

- Branch: `advisor/004-shared-grader-domain`
- Commit style: conventional commits, e.g.
  `refactor(web): extract shared grader domain helpers`.
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1 (Part A): Create the shared module

Create `apps/web/src/components/grader/domain.ts`:
```ts
import type { GradingJob, GradingSubmission } from "../../types";

export function scoreOf(submission: GradingSubmission): number | null {
  return submission.final_score ?? submission.ai_score ?? null;
}

export function studentLabel(submission: GradingSubmission): string {
  return submission.student_name ?? submission.student_email ?? "Aluno desconhecido";
}

export function scoreColor(g: number | null): string {
  if (g == null) return "var(--muted-2)";
  return g >= 85 ? "var(--ink)" : g >= 65 ? "var(--warning)" : "var(--danger)";
}

export function classroomActivityUrl(job: GradingJob): string {
  return `https://classroom.google.com/c/${job.course_id}/a/${job.activity_id}/details`;
}
```
Copy the bodies **exactly** from the existing definitions (verify against the
excerpts above and the live files). Adjust the relative import path for `types`
to match the file's location (`../../types` from `grader/domain.ts`).

**Verify**: `pnpm build` (from `apps/web`) → exit 0.

### Step 2 (Part A): Switch `PostingPiP.tsx` to the shared module

In `apps/web/src/components/grader/pip/PostingPiP.tsx`, delete the local
`scoreOf`, `studentLabel`, `scoreColor`, `classroomActivityUrl` definitions
(lines ~11-30) and the "duplicated to avoid circular deps" comment, and add:
```ts
import { classroomActivityUrl, scoreColor, scoreOf, studentLabel } from "../domain";
```
Keep `postingFeedbackText` local. Leave all JSX and behavior unchanged.

**Verify**: `pnpm build` → exit 0. `grep -n "function scoreOf\|function studentLabel\|function scoreColor\|function classroomActivityUrl" apps/web/src/components/grader/pip/PostingPiP.tsx` → no matches.

### Step 3 (Part A): Switch `GraderWrap.tsx` to the shared module

In `apps/web/src/components/grader/GraderWrap.tsx`, delete local `scoreOf`,
`studentLabel`, `classroomActivityUrl` (lines ~14-28) and add:
```ts
import { classroomActivityUrl, scoreOf, studentLabel } from "./domain";
```
`GraderWrap` also defines `postingClipboardText` which *calls* `scoreOf` — that
keeps working via the import. Leave it. Do not remove `scoreColor` here (it isn't
defined in this file).

**Verify**: `pnpm build` → exit 0. `grep -n "function scoreOf\|function studentLabel\|function classroomActivityUrl" apps/web/src/components/grader/GraderWrap.tsx` → no matches.

### Step 4 (Part A): Switch `GraderReview.tsx`

In `apps/web/src/components/grader/GraderReview.tsx`, remove the local
`studentLabel` (line ~36) and import it from `./domain`. Check whether this file
also defines `scoreOf`/`scoreColor` (read the top ~50 lines); if so, remove and
import those too. Only remove helpers whose body is identical to the shared one —
if a body differs, STOP and report (the behavior must not change silently).

**Verify**: `pnpm build` → exit 0. `pnpm test:run` → exit 0 (if Plan 001's
harness exists; if not, skip this and note it).

### Step 5 (Part B): Resolve `session_secret_key` — GUARDED

First check whether Plan 003 has landed:
`grep -rn "session_secret_key" apps/api/src/classroom_downloader/google_provider.py apps/api/src/classroom_downloader/routers/auth.py`

- **If there ARE matches** (Plan 003 wired it for credential encryption): the
  setting is now live. Do **nothing** to it — Part B is already resolved. Note
  this in your report.
- **If there are NO matches** (Plan 003 has not landed): remove the dead setting.
  Delete the `session_secret_key: str | None = None` line from `settings.py:42`,
  and confirm nothing references it:
  `grep -rn "session_secret_key" apps/api/src` → only `.pyc` matches (ignore
  those) or nothing.

**Verify**: `uv run --extra dev pytest -q` (from `apps/api`) → all pass either
way.

## Test plan

- No new tests required — Part A is a behavior-preserving move covered by
  `pnpm build` (typecheck) and any component tests; Part B is config removal
  covered by the existing suite.
- If Plan 001's harness exists, optionally add a tiny `domain.test.ts` asserting
  `scoreColor(90)`, `scoreColor(70)`, `scoreColor(50)`, `scoreColor(null)` map to
  the four expected CSS vars, and `scoreOf`/`studentLabel` fallbacks. This locks
  the thresholds that previously drifted across copies.
- Verification: `pnpm build` + `uv run --extra dev pytest -q` → both clean.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `apps/web/src/components/grader/domain.ts` exists exporting `scoreOf`,
      `studentLabel`, `scoreColor`, `classroomActivityUrl`
- [ ] `grep -rn "function scoreOf\|function studentLabel\|function scoreColor\|function classroomActivityUrl" apps/web/src/components/grader`
      returns no matches outside `domain.ts`
- [ ] `pnpm build` (from `apps/web`) exits 0
- [ ] `uv run --extra dev pytest -q` (from `apps/api`) exits 0
- [ ] Part B handled per the guard (either left wired by Plan 003, or removed) —
      stated explicitly in the executor's report
- [ ] `plans/README.md` status row for 004 updated

## STOP conditions

Stop and report back (do not improvise) if:

- A helper body in any source file differs from the shared version (different
  thresholds, different fallback string) — that is a latent behavior difference,
  not a clean duplicate; report it rather than picking one.
- `pnpm build` fails after a move (likely an import-path mistake — fix once; if
  it persists, STOP).
- You are unsure whether Plan 003 landed — run the Step 5 grep; if the result is
  ambiguous, leave `session_secret_key` untouched and report.

## Maintenance notes

- New grader components should import from `grader/domain.ts` rather than
  re-declaring these helpers. A reviewer should reject new local copies.
- If `scoreColor` thresholds change, they now change in one place — confirm the
  optional `domain.test.ts` (if added) is updated alongside.
