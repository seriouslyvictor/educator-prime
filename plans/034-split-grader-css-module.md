# Plan 034: Split the shared grader CSS module by screen/component

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If a STOP condition occurs, stop and report; do not improvise.
> When done, update this plan's row in `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 035af04..HEAD -- apps/web/src/components/grader/Grader.module.css apps/web/src/components/grader/`
> If grader component files or `Grader.module.css` changed, re-read imports and
> selector usage before proceeding.

## Status

- **Priority**: P3
- **Effort**: M
- **Risk**: MED
- **Depends on**: archive/008-decompose-grader-review.md and archive/009-decompose-grader-setup-queue.md completed
- **Category**: tech-debt
- **Planned at**: commit `035af04`, 2026-06-29

## Why this matters

`Grader.module.css` is over 3000 lines and is imported by multiple grader
screens. Archived plans 008 and 009 decomposed the TypeScript components but
intentionally left CSS untouched because the repo temporarily emits CSS module
class names as plain local names. The remaining shared stylesheet makes style
ownership hard to review and increases collision risk. This plan splits CSS in
small, visual-smoke-verified steps.

## Current state

Relevant live shapes to confirm:

- `apps/web/src/components/grader/Grader.module.css` is a large shared file.
- It is imported by at least:
  - `GraderQueue.tsx`
  - `GraderReview.tsx`
  - `GraderSetup.tsx`
  - `GraderTopbar.tsx`
  - `GraderWrap.tsx`
- `apps/web/vite.config.ts` historically sets CSS modules to
  `generateScopedName: "[local]"`, so class names are effectively global during
  the transition. Do not assume hashed isolation until you verify the config.
- Archive plans 008 and 009 decomposed grader screen components and documented
  that child component files rely on an ancestor importing `Grader.module.css`.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Build/typecheck | `pnpm build` | exit 0 |
| Unit tests | `pnpm test:run` | all pass |
| E2E | `pnpm e2e` | all pass |
| Lint | `pnpm lint` | no new errors |

Run from `apps/web`.

Manual visual smoke needs the mock backend:

`uv run --extra dev python -m uvicorn classroom_downloader.main:app --app-dir src --reload --port 8000`

Run that from `apps/api`.

## Scope

**In scope**:

- `apps/web/src/components/grader/Grader.module.css`
- New CSS modules under `apps/web/src/components/grader/`, for example:
  - `GraderQueue.module.css`
  - `GraderReview.module.css`
  - `GraderSetup.module.css`
  - `GraderWrap.module.css`
  - `GraderTopbar.module.css`
- Imports in the matching grader component files.

**Out of scope**:

- Markup/class-name rewrites beyond changing the imported module object.
- User-visible layout redesign.
- Vite CSS module config changes.
- Non-grader styles.

## Git workflow

- Branch: `advisor/034-split-grader-css-module`.
- Commit one screen at a time, with build/e2e after meaningful steps.
- Do not push or open a PR unless instructed.

## Steps

### Step 1: Baseline and selector inventory

Run frontend build/tests. Then inventory selectors used by each grader screen.
Use `rg "graderStyles\\[|className=\"|className=\\{" apps/web/src/components/grader`
and group selectors by owning screen.

**Verify**: `pnpm build` and `pnpm test:run` exit 0.

### Step 2: Split topbar styles first

Create `GraderTopbar.module.css` with only selectors used by `GraderTopbar.tsx`.
Import it from `GraderTopbar.tsx`. Leave the original selectors in
`Grader.module.css` until after the screen still builds, then remove only the
moved selectors.

**Verify**: `pnpm build` exits 0.

### Step 3: Split queue styles

Move queue-only selectors to `GraderQueue.module.css` and update
`GraderQueue.tsx` plus queue child components if they import style injection.
Preserve every class name string and CSS declaration.

**Verify**: `pnpm build`, `pnpm test:run`, and `pnpm e2e` exit 0.

### Step 4: Split setup and review styles

Repeat the mechanical move for setup and review selectors. Use the folders
created by archived plans 008 and 009 as ownership boundaries:

- review-related selectors belong with `GraderReview.module.css`
- setup-related selectors belong with `GraderSetup.module.css`

Do not rename selectors or redesign layout.

**Verify**: `pnpm build` and `pnpm test:run` exit 0 after each screen.

### Step 5: Split wrap styles

Move wrap/posting/PiP-specific selectors to `GraderWrap.module.css` if they are
only used by wrap components. If a selector is shared across multiple screens,
leave it in `Grader.module.css` and document it as shared.

**Verify**: `pnpm build` exits 0.

### Step 6: Final visual and diff review

Run the full frontend gate. If possible, start the app in mock mode and smoke:

- queue screen
- setup screen
- review screen
- wrap/posting screen

Compare against baseline screenshots manually or with Playwright screenshots if
available.

**Verify**:

- `pnpm build` exits 0.
- `pnpm test:run` exits 0.
- `pnpm e2e` exits 0.
- `pnpm lint` reports no new errors.

## Test plan

This is a visual refactor. Existing tests catch routing and some screen
presence, but the important gate is visual smoke in mock mode. Do not skip the
manual or screenshot smoke if CSS ownership changed substantially.

## Done criteria

- [ ] `Grader.module.css` is materially smaller and contains only shared grader
      styles.
- [ ] Each major grader screen imports its own CSS module.
- [ ] No selectors were renamed unless all usages were updated.
- [ ] `pnpm build`, `pnpm test:run`, `pnpm e2e`, and `pnpm lint` pass from
      `apps/web` except documented pre-existing lint issues.
- [ ] Visual smoke passes for queue, setup, review, and wrap screens.
- [ ] No files outside the in-scope list are modified.
- [ ] `plans/README.md` row for 034 updated.

## STOP conditions

Stop and report if:

- The Vite CSS module config changed from the archived-plan assumption and class
  names are now hashed.
- Moving selectors causes unstyled or visibly different screens.
- A selector is used across multiple screens and ownership is unclear.
- Fixing visual regressions would require markup/layout redesign.

## Maintenance notes

After this lands, new grader styles should go into the owning screen/module
rather than back into `Grader.module.css`. Reviewers should reject broad shared
CSS additions unless the style is truly cross-screen.
