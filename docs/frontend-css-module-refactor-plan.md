# Implementation Plan: Decompose the frontend into co-located CSS-Module components

> Status: **Planned — not yet started.** Deferred until token budget is available.
> Target branch: `claude/frontend-component-refactor-mXlu9`
> CSS strategy: **CSS Modules (co-located).** Component scope: **Split the monoliths** (no `features/` restructure).

## Goal
Replace the single 2,751-line global `apps/web/src/styles.css` with co-located
`*.module.css` files, one per component, and split the monolithic view files so
each component owns its own styles. Clean up dead/drifted styling code along the way.

## Current state (findings)
- **`styles.css`** — 2,751 lines, all global class names, imported once in `main.tsx`.
  No section comments, but source order already groups loosely by feature:
  tokens/reset → shell/rail → workspace → buttons → connect → progress → done →
  history → grader (queue/setup/review/audit/wrap) → drawer/tree → empty/skeleton.
- **`Grader.tsx`** — 983 lines exporting **5 separate views** (`GraderQueue`,
  `GraderSetup`, `GraderReview`, `GraderAudit`, `GraderWrap`) plus `GraderTopbar`,
  ~15 helpers, and **dead code** (`LegacyGraderQueue` + `QueueSection`, never referenced —
  the live path uses `ReferenceQueueSection`).
- **`Workspace.tsx`** — 200 lines mixing `ClassroomList`, `ActivityList`, and shared
  `SearchBox`/`EmptyState`/`SkeletonRows`.
- **`ui.tsx`** — only `Grader.tsx` imports it, and only `Card*`/`Radio*`/`Tabs*` are used.
  `Button` and `Progress` reference CSS classes (`.button`, `.progress-bar`) that
  **don't exist**; `Badge`/`Empty`/`Skeleton` are never imported anywhere. Dead.
- **The design system lives in `:root` / `[data-theme="dark"]` CSS variables**
  (lines 1–64) — colors, radii, shadows, transitions. These must stay global;
  CSS Modules reference them via `var(--…)`.

## Strategy
CSS Modules per the decision. The `:root` token block and base reset (`*`,
`html/body`, generic `button`/`input` resets, `.ico`/`.spin` keyframes) become a
small **global `tokens.css` + `base.css`** still imported in `main.tsx`. Everything
component-specific moves into `Component.module.css` next to its `.tsx`, with
classNames rewritten from `"class-row"` to `styles.classRow`.

## Phased steps

### Phase 0 — Safety net
- Confirm `pnpm install` + `pnpm build` (`tsc -b && vite build`) is green **before**
  touching anything, so we have a baseline. No test suite exists for the web app, so
  the typecheck + build is our guardrail.

### Phase 1 — Establish the global layer
- Create `src/styles/tokens.css` (the `:root` + `[data-theme="dark"]` variable blocks)
  and `src/styles/base.css` (reset, `body`, generic element resets, `.ico`/`.spin`/
  keyframes — the truly global helpers).
- Import both in `main.tsx`. Leave the rest of `styles.css` in place temporarily so the
  app keeps rendering during the migration.

### Phase 2 — Split the component files (prerequisite for co-location)
- `components/grader/` folder: `GraderQueue.tsx`, `GraderSetup.tsx`, `GraderReview.tsx`,
  `GraderAudit.tsx`, `GraderWrap.tsx`, plus `GraderTopbar.tsx` and a `graderStatus.ts`
  for the pure label/tone helpers. Update the barrel import in `App.tsx` (it imports all
  five from `./components/Grader`).
- **Delete `LegacyGraderQueue` + `QueueSection`** (verified unreferenced).
- `components/workspace/`: `ClassroomList.tsx`, `ActivityList.tsx`. Move
  `SearchBox`/`EmptyState`/`SkeletonRows` into shared `ui.tsx` (they're genuinely shared
  primitives).
- **Prune `ui.tsx`**: remove unused `Button`, `Progress`, `Badge`, `Empty`, `Skeleton`
  (or, if preferred, fix `Button` to the existing `.btn` classes — see sub-decision 1).

### Phase 3 — Co-locate CSS as Modules, one component at a time
For each component, in dependency order (leaf components first: `ThemeToggle`, `icons`
→ `ui` primitives → views → `Rail`/`App`):
1. Create `Component.module.css`, move that component's rules out of `styles.css`.
2. Rename kebab-case selectors to camelCase, rewrite `className="x"` →
   `className={styles.x}`; compose conditionals with a small `cn()` helper (already
   exists in `ui.tsx` — promote it to `lib/cn.ts`).
3. Keep `var(--token)` references as-is (they resolve from the global `tokens.css`).
4. Handle the handful of cross-component selectors (e.g. `.rubric-panel .card-header`,
   `.context-card .card-title`) by either `:global()` escapes or a shared module —
   enumerate these during the pass; there are ~6.
5. Build after each component to catch breakage early.

### Phase 4 — Delete the husk
- Once every rule is migrated, `styles.css` should be empty (or only the global bits
  already moved). Remove it and its import.
- Final `pnpm build` + a manual smoke run (`pnpm dev`) across each view: connect →
  workspace → progress → done → history → all five grader screens, in both light and
  dark theme.

### Phase 5 — Commit & push
- Commit in logical chunks (global layer, component splits, per-feature CSS migration)
  on `claude/frontend-component-refactor-mXlu9` and push. No PR unless requested.

## Risk notes
- **Pure mechanical refactor — zero behavior change is the bar.** Easiest regression
  source is the ~6 descendant selectors that cross component boundaries and the
  dark-theme overrides keyed on `[data-theme="dark"] .selector`; grep those out
  explicitly and handle each.
- CSS Modules camelCase: keep a consistent convention and a `cn()` helper so
  multi-class/conditional cases stay readable.
- No automated tests means the build + manual screen-by-screen check is the
  verification; do both themes.

## Sub-decisions (defaults, override if desired)
1. **`ui.tsx` dead primitives** → delete them (not used; two are broken). Alternative:
   repair `Button` to the real `.btn` classes and keep it.
2. **Folder layout** → `components/grader/` and `components/workspace/` subfolders, no
   `features/` restructure (per chosen scope).

## Quick reference — CSS section line ranges (in current `styles.css`)
- Tokens / theme vars: ~1–64
- Reset / base / `.ico` / `.spin`: ~66–117
- Shell / rail / nav / account: ~119–342
- Workspace / class-row: ~343–619
- Buttons (`.btn*`): ~620–720
- Connect: ~723–878
- Progress view: ~880–1062
- Done view: ~1063–1130
- History view: ~1131–1183
- Grader (topbar, queue, cards, setup, review, audit, wrap): ~1184–2540
- Drawer / tree: ~2542–2651
- Empty state / skeleton: ~2653–end
