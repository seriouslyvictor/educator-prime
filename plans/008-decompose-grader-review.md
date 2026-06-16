# Plan 008: Decompose GraderReview.tsx into a co-located `review/` component folder

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. This is a **behavior-preserving, mechanical** refactor — the app
> must look and behave identically before and after, and the build must stay
> green after every step. If anything in the "STOP conditions" section occurs,
> stop and report — do not improvise. When done (or at a clean intermediate
> point), update the status row for this plan in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat a9713b0..HEAD -- apps/web/src/components/grader/GraderReview.tsx`
> If `GraderReview.tsx` changed since this plan was written, re-read it fully and
> map the current functions to the groupings below before proceeding; on a
> structural mismatch (a listed component renamed or gone), treat it as a STOP
> condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none (plans 001/002/006 test+e2e harness already landed and is the safety net)
- **Category**: tech-debt
- **Planned at**: commit `a9713b0`, 2026-06-16

## Why this matters

`apps/web/src/components/grader/GraderReview.tsx` is **831 lines** holding one
exported screen plus eight internal components and a pile of helpers and
constants in a single file. It is the hardest grader screen to navigate, test,
and review, and a merge-conflict magnet. The goal is **more modularity without
rewriting anything that works**: move the already-self-contained internal
components into their own co-located files under `grader/review/`, leaving the
orchestrator as a thin shell. No behavior, markup, styling, or props change.

**Why this is safe (read this — it is the load-bearing fact of the plan).**
`apps/web/vite.config.ts` sets `css.modules.generateScopedName: "[local]"`:

```ts
// apps/web/vite.config.ts:16-20
  css: {
    modules: {
      generateScopedName: "[local]",
    },
  },
```

That means CSS-module class names are **not hashed** — every `*.module.css` is
effectively a global stylesheet, and a string like `className="student-row"`
resolves to the same `.student-row` rule defined in `Grader.module.css`. The
component already relies on this: it does `import graderStyles from
"./Grader.module.css"; void graderStyles;` purely to inject the stylesheet, then
uses plain string class names everywhere. **Consequence: moving a sub-component's
JSX to another file requires zero CSS changes and carries zero visual risk**, as
long as `Grader.module.css` is still injected by an ancestor module that renders
it (the orchestrator below keeps that import).

## Current state

`apps/web/src/components/grader/GraderReview.tsx` (831 lines). Its top imports:

```ts
// GraderReview.tsx:1-16
import { useEffect, useMemo, useState } from "react";
import { api } from "../../lib/api";
import type { GradingJob, GradingSubmission, GradingSubmissionFile, PrivacyAudit } from "../../types";
import { AppIcon } from "../icons";
import { GraderTopbar } from "./GraderTopbar";
import { studentLabel } from "./domain";
import {
  privacyLabel, privacyTone, redactionLabel, redactionSummary,
  errorLayerLabel, safeStatusLabel,
} from "./graderStatus";
import graderStyles from "./Grader.module.css";
void graderStyles;
```

The exported component is `function GraderReview(...)` at line 43; its root JSX is
`<div className={graderStyles["grader-review"]}>`. Below it live these
**already-componentized, props-only** units (each is a `function` with an explicit
props object — pure to move):

| Symbol | Lines | Depends on |
|---|---|---|
| `AuditStrip` | 409–429 | `AppIcon` |
| `AuditReport` | 431–480 | `AppIcon`, `safeStatusLabel`, `privacyLabel`, `redactionSummary` |
| `PrivacyBlock` | 482–517 | `AppIcon`, `privacyTone`, `privacyLabel`, `redactionLabel` |
| `StudentRow` | 519–571 | `AppIcon`, `studentLabel`, + helpers `initials`/`isBlocked`/`isVisualSubmission` |
| `SubmissionFiles` | 649–680 | `AppIcon`, `GradingSubmissionFile`, calls `SubmissionPreview` |
| `SubmissionPreview` | 682–720 | `api`, `studentLabel`, mime consts/helpers, calls `SubmissionTextPreview` |
| `SubmissionTextPreview` | 722–790 | `AppIcon` |
| `BlockedEvidence` | 792–830 | `api`, `AppIcon`, `errorLayerLabel`, `safeStatusLabel` |

Plus module-private helpers/constants that move **with** their only consumers:

- `initials` (20), `isBlocked` (28), `isVisualSubmission` (32) — used by
  `StudentRow` and by the orchestrator's inline JSX. → shared `reviewHelpers.ts`.
- `hasDefaultCriteria` (37) — used **only** by the orchestrator's suggestion
  aside; leave it in `GraderReview.tsx`.
- `INLINE_IMAGE_MIME` (575), `INLINE_TEXT_MIME` (576), `INLINE_TEXT_EXTENSIONS`
  (599), `extensionOf` (638), `isInlineTextSubmission` (643) — used only by the
  submission-preview cluster. → move into `SubmissionPreview.tsx`.

The orchestrator's own `return` (165–406) contains two inline `<aside>` blocks
(the student list and the suggestion panel) wired to local `useState`
(`scoreText`, `feedback`, `filter`, `reportOpen`) and the keyboard effect. **These
stay inline** in this plan (extracting them means threading state through props —
out of scope here; see Maintenance notes).

**Conventions to match:**
- Shared grader domain helpers live in `grader/domain.ts` (e.g. `studentLabel`,
  `scoreOf`); shared status-label helpers in `grader/graderStatus.ts`. Follow that
  split — but the three review-only predicates (`initials`/`isBlocked`/
  `isVisualSubmission`) are review-specific, so they go in a new
  `grader/review/reviewHelpers.ts`, not `domain.ts`.
- Function components, explicit prop object types inline, named exports.
- pt-BR user-facing strings unchanged; English identifiers/comments.
- Child component files do **not** import `Grader.module.css` — the orchestrator
  already injects it as their rendered ancestor. Keep string class names as-is.

## Commands you will need

| Purpose | Command (run from `apps/web`) | Expected |
|---|---|---|
| Typecheck + build | `pnpm build` | exit 0 |
| Unit tests | `pnpm test:run` | exit 0 |
| Lint | `pnpm lint` | no NEW errors vs. baseline (a pre-existing `GraderSetup.tsx` `selectedRubric` warning may remain) |
| E2E smoke (optional) | `pnpm e2e` | exit 0 (mock mode) |
| Dev server (manual smoke) | `pnpm dev` | serves on :5173 |

Manual smoke needs the backend in mock mode: from `apps/api`,
`uv run --extra dev python -m uvicorn classroom_downloader.main:app --app-dir src --reload --port 8000`.

## Scope

**In scope** (the only files you create or modify):
- `apps/web/src/components/grader/GraderReview.tsx` (shrink to orchestrator)
- `apps/web/src/components/grader/review/reviewHelpers.ts` (create)
- `apps/web/src/components/grader/review/AuditStrip.tsx` (create — holds `AuditStrip` + `AuditReport`)
- `apps/web/src/components/grader/review/PrivacyBlock.tsx` (create)
- `apps/web/src/components/grader/review/StudentRow.tsx` (create)
- `apps/web/src/components/grader/review/SubmissionPreview.tsx` (create — holds `SubmissionFiles`, `SubmissionPreview`, `SubmissionTextPreview`, `BlockedEvidence` + mime consts/helpers)

**Out of scope** (do NOT touch):
- `apps/web/src/components/grader/index.ts` — keep `GraderReview.tsx` at its
  current path so the barrel and every call site stay untouched.
- `Grader.module.css` — no CSS changes at all (splitting it is a separate,
  deferred effort).
- Any change to `GraderReview`'s exported props, the markup/class names, user
  text, or the two inline `<aside>` blocks and their local state.
- Any other grader screen (`GraderSetup`, `GraderQueue`, `GraderWrap`) — those
  are Plan 009.

## Git workflow

- Branch: `advisor/008-decompose-grader-review`
- Conventional commits, one per extracted unit, each with a green build. Example
  from `git log`: `refactor(web): extract grading-job lifecycle hook from app`.
  Use e.g. `refactor(web): extract StudentRow from GraderReview`.
- Do NOT push or open a PR unless instructed.

## Steps

Order: leaves first, each an independently-green move. After **every** step run
`pnpm build` and `pnpm test:run`.

### Step 1: Baseline

Run `pnpm build` and `pnpm test:run` and record they pass. Start the app in mock
mode and walk the smoke checklist (Test plan) once so you know the target
behavior. Record any pre-existing console errors.

**Verify**: `pnpm build` → exit 0; `pnpm test:run` → exit 0.

### Step 2: Create `review/reviewHelpers.ts`

Create `apps/web/src/components/grader/review/reviewHelpers.ts` and move
`initials` (20–26), `isBlocked` (28–30), and `isVisualSubmission` (32–35)
verbatim, each `export`ed. Add the needed import:
`import type { GradingSubmission } from "../../../types";`. In `GraderReview.tsx`,
delete those three local definitions and add
`import { initials, isBlocked, isVisualSubmission } from "./review/reviewHelpers";`.

**Verify**: `pnpm build` → 0; `pnpm test:run` → 0; `grep -n "function initials" apps/web/src/components/grader/GraderReview.tsx` → no match.

### Step 3: Extract `review/AuditStrip.tsx`

Create the file; move `AuditStrip` (409–429) and `AuditReport` (431–480) verbatim
as named exports. Imports it needs:
`import { AppIcon } from "../icons";`,
`import { privacyLabel, redactionSummary, safeStatusLabel } from "../graderStatus";`,
`import type { PrivacyAudit } from "../../../types";`. In `GraderReview.tsx`,
delete those two functions and add
`import { AuditStrip, AuditReport } from "./review/AuditStrip";`.

**Verify**: `pnpm build` → 0; `pnpm test:run` → 0.

### Step 4: Extract `review/PrivacyBlock.tsx`

Move `PrivacyBlock` (482–517) verbatim. Imports:
`import { AppIcon } from "../icons";`,
`import { privacyTone, privacyLabel, redactionLabel } from "../graderStatus";`,
`import type { GradingSubmission } from "../../../types";`. Replace in
`GraderReview.tsx` with `import { PrivacyBlock } from "./review/PrivacyBlock";`.

**Verify**: `pnpm build` → 0; `pnpm test:run` → 0.

### Step 5: Extract `review/StudentRow.tsx`

Move `StudentRow` (519–571) verbatim. Imports:
`import { AppIcon } from "../icons";`,
`import { studentLabel } from "../domain";`,
`import { initials, isBlocked, isVisualSubmission } from "./reviewHelpers";`,
`import type { GradingSubmission } from "../../../types";`. Replace in
`GraderReview.tsx` with `import { StudentRow } from "./review/StudentRow";`.

**Verify**: `pnpm build` → 0; `pnpm test:run` → 0.

### Step 6: Extract `review/SubmissionPreview.tsx`

Move, verbatim and together (they form one cluster): `INLINE_IMAGE_MIME` (575),
`INLINE_TEXT_MIME` (576–598), `INLINE_TEXT_EXTENSIONS` (599–636), `extensionOf`
(638–641), `isInlineTextSubmission` (643–646), `SubmissionFiles` (649–680),
`SubmissionPreview` (682–720), `SubmissionTextPreview` (722–790), `BlockedEvidence`
(792–830). Export at least `SubmissionFiles` and `BlockedEvidence` (the two the
orchestrator calls directly — check `GraderReview.tsx` lines 279–282); the others
can stay file-private. Imports:
`import { useEffect, useState } from "react";`,
`import { api } from "../../../lib/api";`,
`import { AppIcon } from "../icons";`,
`import { studentLabel } from "../domain";`,
`import { errorLayerLabel, safeStatusLabel } from "../graderStatus";`,
`import type { GradingJob, GradingSubmission, GradingSubmissionFile } from "../../../types";`.
Replace in `GraderReview.tsx` with
`import { SubmissionFiles, BlockedEvidence } from "./review/SubmissionPreview";`.

**Verify**: `pnpm build` → 0; `pnpm test:run` → 0.

### Step 7: Final shrink, lint, and clean imports

`GraderReview.tsx` should now be: imports, the small `hasDefaultCriteria` helper,
the `GraderReview` component (state, derived values, keyboard effect, and the
`return` with its two inline asides), nothing else. Remove now-unused imports
(e.g. `GradingSubmissionFile` if no longer referenced; `api` if the preview
cluster was its only user — verify with grep before deleting). Keep
`import graderStyles from "./Grader.module.css"; void graderStyles;` and
`className={graderStyles["grader-review"]}` exactly.

**Verify**:
- `pnpm build` → 0; `pnpm test:run` → 0.
- `pnpm lint` → no new errors in `GraderReview.tsx` or the new `review/` files vs. the Step 1 baseline.
- `wc -l apps/web/src/components/grader/GraderReview.tsx` → materially reduced (target ≤ ~440 lines; report the actual count).
- `git diff --name-only` touches only the six in-scope files.

## Test plan

- No new unit tests are required (pure mechanical moves; the Plan 002/006 nets
  cover the logic these components call). If you want a cheap pin, add
  `apps/web/src/components/grader/review/reviewHelpers.test.ts` testing `initials`
  (two-word → first letters; single word → first two chars; empty → fallback),
  modeled on `apps/web/src/components/grader/domain.test.ts`.
- **Manual smoke checklist** (mock mode), run before (Step 1) and after (Step 7),
  must be identical:
  1. Open a ready job → run audit → continue to draft → the **Review** screen
     renders: student list (left), document preview (center), suggestion panel
     (right).
  2. The privacy **AuditStrip** shows above the grid; clicking "Ver relatório"
     opens the **AuditReport** drawer; close it.
  3. Click students in the list (`StudentRow`) — avatar initials, status meta,
     and score render; J/K keys move selection, Enter accepts.
  4. A multi-file submission shows file tabs (`SubmissionFiles`); image/text/PDF
     previews render (`SubmissionPreview`/`SubmissionTextPreview`); a blocked
     submission shows the `BlockedEvidence` card.
- Verification: every item looks and behaves exactly as the Step 1 baseline (same
  styling — confirming the global-CSS assumption held).

## Done criteria

Machine-checkable + observable. ALL must hold (from `apps/web`):

- [ ] `pnpm build` exits 0
- [ ] `pnpm test:run` exits 0
- [ ] `apps/web/src/components/grader/review/` contains `reviewHelpers.ts`,
      `AuditStrip.tsx`, `PrivacyBlock.tsx`, `StudentRow.tsx`, `SubmissionPreview.tsx`
- [ ] `GraderReview.tsx` line count materially reduced (report `wc -l`)
- [ ] `git diff --name-only` lists only the six in-scope files
- [ ] `pnpm lint` reports no new errors vs. Step 1 baseline
- [ ] Manual smoke checklist passes identically to baseline
- [ ] `plans/README.md` status row for 008 updated

## STOP conditions

Stop and report back (do not improvise) if:

- The drift check shows `GraderReview.tsx` changed structurally since `a9713b0`
  (a listed component renamed/removed/relocated).
- Any moved component turns out to reference a local variable from the
  orchestrator's closure that isn't already one of its declared props — that
  means the seam is not as clean as assumed; report the specific coupling rather
  than threading new props.
- After a move, a smoke item renders **unstyled** or visually different — that
  would contradict the global-CSS assumption; revert that step's commit and
  report (do not start editing `Grader.module.css`).
- `pnpm build` or `pnpm test:run` fails twice after a reasonable fix attempt.

## Maintenance notes

- New review sub-features should be added as files under `grader/review/`, not by
  re-growing `GraderReview.tsx`.
- **Deferred (intentionally):** extracting the two inline `<aside>` blocks (the
  student-list panel and the suggestion/score panel). They're coupled to the
  orchestrator's `scoreText`/`feedback`/`filter` state and the keyboard effect;
  extracting them is a props-threading refactor worth its own plan, not a
  mechanical move.
- **Reuse opportunity for later:** `AuditReport`'s privacy table markup
  (`.audit-table`/`.audit-row`) is near-identical to the one inside
  `GraderSetup.tsx`'s `PreparedPanel`. A shared `AuditTable` component is a good
  follow-up once both screens are decomposed (Plan 009) — not in this plan.
- A reviewer should diff for behavior: confirm no class-name strings changed, the
  orchestrator still injects `Grader.module.css`, and the moved components' props
  match their original call sites.
