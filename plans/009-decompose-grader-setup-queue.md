# Plan 009: Decompose GraderSetup.tsx and GraderQueue.tsx into co-located folders

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on. This is
> a **behavior-preserving, mechanical** refactor — markup, styling, props, and
> user text must be identical before and after. If anything in "STOP conditions"
> occurs, stop and report — do not improvise. When done (or at a clean
> intermediate point), update this plan's row in `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat a9713b0..HEAD -- apps/web/src/components/grader/GraderSetup.tsx apps/web/src/components/grader/GraderQueue.tsx`
> If either file changed since this plan was written, re-read it and re-map the
> components below before proceeding; on a structural mismatch, treat as STOP.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: plans/008-decompose-grader-review.md (same recipe; do 008 first
  so the `grader/<screen>/` folder pattern is established and reviewed). Not a
  hard code dependency — 008 and 009 touch disjoint files — but sequencing keeps
  the pattern consistent.
- **Category**: tech-debt
- **Planned at**: commit `a9713b0`, 2026-06-16

## Why this matters

`GraderSetup.tsx` (608 lines) and `GraderQueue.tsx` (564 lines) are the other two
grader monoliths: each is one exported screen plus several internal components,
constants, and helpers crammed into a single file. Same goal as Plan 008 —
**more modularity, zero rewrite** — applied with the identical recipe: move the
already-self-contained internal components into a co-located `grader/setup/` and
`grader/queue/` folder, leaving each orchestrator a thin shell.

**Why it is safe (the load-bearing fact):** `apps/web/vite.config.ts:16-20` sets
`css.modules.generateScopedName: "[local]"`, so CSS-module class names are **not
hashed** — every `*.module.css` is effectively global, and string class names
like `"queue-card"` or `"rubric-panel"` resolve to the rules in
`Grader.module.css`. Both files already use this: they
`import graderStyles from "./Grader.module.css"; void graderStyles;` only to inject
the stylesheet, then use string class names. **Moving a sub-component's JSX to a
new file needs no CSS change and carries no visual risk**, as long as the
orchestrator still injects `Grader.module.css` (it will).

## Current state

### GraderSetup.tsx (608 lines)

Top imports (lines 1–9): `react`, types, `api`, `AppIcon`, **home-brewed UI
primitives** `{ Card, CardContent, CardFooter, CardHeader, CardTitle, RadioGroup,
RadioItem, Tabs, TabsList, TabsTrigger } from "../ui"`, `GraderTopbar`,
`{ extractionLabel, privacyLabel, redactionSummary, safeStatusLabel } from
"./graderStatus"`, and `graderStyles` (void). Module-level config constants
`rubricModes` (11–23) and `loopModes` (25–34). Exported `GraderSetup` (36) whose
root is `<div className="g-page">`. Internal, props-only units:

| Symbol | Lines | Notes |
|---|---|---|
| `StructuredCriteriaEditor` | 352–~417 | criteria rows + weights editor |
| `CriteriaRunningPanel` | 419–~451 | progress panel (`progress` prop) |
| `AuditRunningPanel` | 452–~487 | progress panel (`progress`, `total`) |
| `hasDefaultCriteria` | 489–493 | helper (also exists in `GraderReview.tsx`) |
| `InferIntroPanel` | 495–503 | static hint |
| `PreparedPanel` | 505–599 | audit summary + table + actions |
| `AuditStat` | 601–608 | leaf used by `PreparedPanel` |

### GraderQueue.tsx (564 lines)

Top imports (lines 1–7): `react`, `KeyboardEvent` type, types, `AppIcon`,
`{ SearchBox } from "../ui"`, `graderStyles` (void). Exported `GraderQueue` (9)
whose root is `<div className={graderStyles["g-page"]} data-screen-label="01
Grader - Queue">`. Internal units, constants, helpers:

| Symbol | Lines | Notes |
|---|---|---|
| `ReferenceQueueSection` | 209–249 | renders a grid of `ReferenceQueueCard` |
| `ReferenceQueueCard` | 251–359 | the card; uses `CardMenu`, `referenceQueueStatus`, `queueItemKey` |
| `bulkActions` const | 370–403 | `QueueActionConfig[]` (type at 361–368) |
| `queueItemKey` | 405–407 | helper (used by orchestrator + cards) |
| `isDestructiveAction` | 409–411 | helper (orchestrator + `CardMenu`) |
| `isQueueActionValid` | 413–417 | helper (orchestrator) |
| `actionsForItem` | 419–422 | helper (`CardMenu`) |
| `CardMenu` | 424–509 | kebab menu; uses `isDestructiveAction`, `actionsForItem`, `bulkActions` |
| `ArchivedSection` | 511–550 | collapsible; uses `queueItemKey` |
| `referenceQueueStatus` | 552–562 | **exported** — keep it exported |

`data-screen-label="01 Grader - Queue"` on the root is asserted by the Playwright
e2e specs (Plan 006) — **do not change or remove it.**

**Conventions to match:** function components, explicit inline prop types, named
exports; shared helpers in `grader/domain.ts` / `grader/graderStatus.ts`; pt-BR
user strings unchanged; child files do **not** import `Grader.module.css` (the
orchestrator injects it); keep `data-screen-label` and all class strings verbatim.

## Commands you will need

| Purpose | Command (from `apps/web`) | Expected |
|---|---|---|
| Typecheck + build | `pnpm build` | exit 0 |
| Unit tests | `pnpm test:run` | exit 0 |
| E2E smoke | `pnpm e2e` | exit 0 (asserts the queue `data-screen-label`) |
| Lint | `pnpm lint` | no NEW errors vs. baseline |
| Dev server | `pnpm dev` | :5173 |

Backend mock mode for manual smoke: from `apps/api`,
`uv run --extra dev python -m uvicorn classroom_downloader.main:app --app-dir src --reload --port 8000`.

## Scope

**In scope** (create/modify only these):
- `apps/web/src/components/grader/GraderSetup.tsx` (shrink to orchestrator)
- `apps/web/src/components/grader/setup/StructuredCriteriaEditor.tsx` (create)
- `apps/web/src/components/grader/setup/PreparePanels.tsx` (create — holds
  `CriteriaRunningPanel`, `AuditRunningPanel`, `InferIntroPanel`, `PreparedPanel`,
  `AuditStat`)
- `apps/web/src/components/grader/GraderQueue.tsx` (shrink to orchestrator)
- `apps/web/src/components/grader/queue/queueActions.ts` (create — `bulkActions`,
  `QueueActionConfig`, `queueItemKey`, `isDestructiveAction`, `isQueueActionValid`,
  `actionsForItem`)
- `apps/web/src/components/grader/queue/ReferenceQueueCard.tsx` (create — holds
  `ReferenceQueueSection`, `ReferenceQueueCard`, `CardMenu`)
- `apps/web/src/components/grader/queue/ArchivedSection.tsx` (create)

**Out of scope** (do NOT touch):
- `apps/web/src/components/grader/index.ts` — keep both orchestrators at their
  current paths so the barrel and call sites are untouched.
- `referenceQueueStatus`'s export identity — keep it exported from
  `GraderQueue.tsx` (re-export it if you move its definition).
- `Grader.module.css`, the home-brewed `../ui` primitives, any class strings,
  `data-screen-label`, user text, or component props.
- `GraderReview.tsx` / `GraderWrap.tsx` (008 and out-of-scope respectively).

## Git workflow

- Branch: `advisor/009-decompose-grader-setup-queue`
- Conventional commits, one per extracted unit, each green. E.g.
  `refactor(web): extract ReferenceQueueCard from GraderQueue`.
- Do NOT push or open a PR unless instructed.

## Steps

Do GraderSetup first, then GraderQueue. `pnpm build` + `pnpm test:run` after each
step.

### Step 1: Baseline

`pnpm build`, `pnpm test:run`, and `pnpm e2e` all pass. Walk the smoke checklist
once (Test plan) to capture target behavior.

**Verify**: all three commands exit 0.

### Step 2: `setup/StructuredCriteriaEditor.tsx`

Move `StructuredCriteriaEditor` (and only it) verbatim as a named export. Give it
the imports it actually uses (read the function body): `react` hooks if any,
`{ AppIcon } from "../icons"`,
`import type { GradingCriterionInput } from "../../../types";`. In
`GraderSetup.tsx` add
`import { StructuredCriteriaEditor } from "./setup/StructuredCriteriaEditor";`
and delete the local definition.

**Verify**: `pnpm build` → 0; `pnpm test:run` → 0.

### Step 3: `setup/PreparePanels.tsx`

Move `CriteriaRunningPanel`, `AuditRunningPanel`, `InferIntroPanel`,
`PreparedPanel`, and `AuditStat` verbatim (named exports for the four used by the
orchestrator; `AuditStat` may stay file-private). Imports to add (verify against
bodies): `{ api } from "../../../lib/api"`, `{ AppIcon } from "../icons"`,
`{ extractionLabel, privacyLabel, redactionSummary, safeStatusLabel } from "../graderStatus"`,
`import type { PrivacyAudit } from "../../../types";`, and the shared progress
type. **The `progress` prop type** is the inline object type
`{ phase: "audit" | "criteria" | "draft"; processed: number; total: number;
current: string; done: boolean; error: string | null }` — copy it as a local
`type Progress = {...}` in the new file (it is currently inlined in
`GraderSetup`'s props at lines 52–59); do not invent a new shape. Update
`GraderSetup.tsx` imports and delete the moved definitions. Leave
`hasDefaultCriteria` in `GraderSetup.tsx` (its callers stay there).

**Verify**: `pnpm build` → 0; `pnpm test:run` → 0.

### Step 4: Shrink GraderSetup, lint

`GraderSetup.tsx` is now: imports, `rubricModes`/`loopModes` consts,
`hasDefaultCriteria`, and the `GraderSetup` component. Remove now-unused imports.
Keep the home-brewed `../ui` imports that the orchestrator's own JSX still uses
(Card/Tabs/RadioGroup etc.) and the `graderStyles` void-import.

**Verify**: `pnpm build` → 0; `pnpm test:run` → 0; `pnpm lint` → no new errors;
`wc -l GraderSetup.tsx` reduced (report it).

### Step 5: `queue/queueActions.ts`

Move `QueueActionConfig` type (361–368), `bulkActions` (370–403), `queueItemKey`
(405–407), `isDestructiveAction` (409–411), `isQueueActionValid` (413–417),
`actionsForItem` (419–422) verbatim, all exported. Add
`import type { GradingQueueItem, QueueAction } from "../../../types";`. In
`GraderQueue.tsx` import what the orchestrator uses
(`queueItemKey`, `isDestructiveAction`, `isQueueActionValid`, `bulkActions`) and
delete the local defs.

**Verify**: `pnpm build` → 0; `pnpm test:run` → 0.

### Step 6: `queue/ReferenceQueueCard.tsx`

Move `ReferenceQueueSection`, `ReferenceQueueCard`, and `CardMenu` verbatim
(`ReferenceQueueSection` exported; the others can be co-exported or file-private
as needed). Imports (verify against bodies): `react` hooks (`useEffect`,
`useRef`, `useState`) and `KeyboardEvent` type, `{ AppIcon } from "../icons"`,
`import type { GradingQueueItem, QueueAction } from "../../../types";`,
`{ queueItemKey, isDestructiveAction, actionsForItem, bulkActions } from "./queueActions"`,
and `referenceQueueStatus`. **`referenceQueueStatus` stays defined/exported in
`GraderQueue.tsx`** — import it here via
`import { referenceQueueStatus } from "../GraderQueue";` (a sibling-up import) OR,
to avoid a back-import cycle, move `referenceQueueStatus` into `queueActions.ts`
and **re-export it from `GraderQueue.tsx`** (`export { referenceQueueStatus } from
"./queue/queueActions";`). Prefer the re-export route — it keeps the public export
path stable and avoids the cycle. In `GraderQueue.tsx` import
`{ ReferenceQueueSection }` and delete the moved defs.

**Verify**: `pnpm build` → 0; `pnpm test:run` → 0;
`grep -rn "referenceQueueStatus" apps/web/src` still resolves (no broken import).

### Step 7: `queue/ArchivedSection.tsx`

Move `ArchivedSection` verbatim as a named export. Imports: `useState`,
`{ AppIcon } from "../icons"`,
`import type { GradingQueueItem, QueueAction } from "../../../types";`,
`{ queueItemKey } from "./queueActions"`. Import it into `GraderQueue.tsx`; delete
the local def.

**Verify**: `pnpm build` → 0; `pnpm test:run` → 0.

### Step 8: Final shrink, lint, e2e

`GraderQueue.tsx` is now: imports, the `GraderQueue` component, and the
`referenceQueueStatus` re-export. Remove unused imports. Confirm the root still
has `data-screen-label="01 Grader - Queue"` and `graderStyles["g-page"]`.

**Verify**:
- `pnpm build` → 0; `pnpm test:run` → 0.
- `pnpm e2e` → 0 (the queue screen-label assertion still passes — proves the root
  attribute and routing are intact).
- `pnpm lint` → no new errors.
- `wc -l` for both orchestrators reduced (report both).
- `git diff --name-only` touches only the in-scope files.

## Test plan

- No new unit tests required (mechanical moves). Optional cheap pin:
  `apps/web/src/components/grader/queue/queueActions.test.ts` for
  `isQueueActionValid` (e.g. `remove` always valid; `restore` requires
  `latest_job_id`) and `queueItemKey` stability, modeled on
  `apps/web/src/components/grader/domain.test.ts`.
- **Manual smoke checklist** (mock mode), identical before/after:
  1. **Setup**: open a queue item → "Preparar correção" renders; switch rubric
     tabs (`infer`/`brief`/`structured`); structured mode shows the criteria
     editor (`StructuredCriteriaEditor`) with weight totals; "Inferir critérios"
     and "Auditar e preparar" run their progress panels (`CriteriaRunningPanel`/
     `AuditRunningPanel`); after audit the `PreparedPanel` summary + table show;
     "Detalhes da auditoria" expands.
  2. **Queue**: the queue lists sections (Continue/Prontas/Concluídos) of
     `ReferenceQueueCard`s; the kebab `CardMenu` opens and its destructive items
     arm-then-confirm; "Gerenciar" bulk mode selects cards and the bulk bar acts;
     the `ArchivedSection` expands and "Restaurar" works.
- Verification: every item looks and behaves exactly as the Step 1 baseline.

## Done criteria

ALL must hold (from `apps/web`):

- [ ] `pnpm build` exits 0
- [ ] `pnpm test:run` exits 0
- [ ] `pnpm e2e` exits 0
- [ ] `setup/` has `StructuredCriteriaEditor.tsx`, `PreparePanels.tsx`; `queue/`
      has `queueActions.ts`, `ReferenceQueueCard.tsx`, `ArchivedSection.tsx`
- [ ] `referenceQueueStatus` is still importable from the grader queue module
- [ ] Both orchestrators' line counts materially reduced (report `wc -l`)
- [ ] `git diff --name-only` lists only in-scope files
- [ ] `pnpm lint` no new errors vs. baseline
- [ ] Manual smoke checklist passes identically to baseline
- [ ] `plans/README.md` row for 009 updated

## STOP conditions

Stop and report (do not improvise) if:

- The drift check shows either file changed structurally since `a9713b0`.
- A moved component references an orchestrator-closure variable that isn't one of
  its declared props (seam is not clean) — report the coupling.
- Moving `referenceQueueStatus` creates an import cycle the re-export route
  doesn't resolve — report rather than restructuring further.
- After a move, a smoke item renders unstyled/different (contradicts the
  global-CSS assumption) — revert that commit, report, do not edit
  `Grader.module.css`.
- `pnpm build`, `pnpm test:run`, or `pnpm e2e` fails twice after a reasonable fix.

## Maintenance notes

- **GraderWrap.tsx (342 lines) was intentionally left out** of this plan: it is
  mostly one component plus the `PostingPiP` integration and has only two trivial
  internal units (`postingClipboardText` helper, `WrapStat` leaf at ~332), so the
  decomposition payoff is small. Revisit only if it grows.
- The duplicated `hasDefaultCriteria` (in both `GraderReview.tsx` and
  `GraderSetup.tsx`) is a candidate to lift into `grader/domain.ts` later — left
  in place here to keep both decompositions independent and conflict-free.
- After this, new setup/queue sub-features extend the relevant folder, not the
  orchestrator.
- Reviewer focus: no class strings or `data-screen-label` changed; the queue
  `referenceQueueStatus` export path is stable; moved components' props match
  their call sites.
