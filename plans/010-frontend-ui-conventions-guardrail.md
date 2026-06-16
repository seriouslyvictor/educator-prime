# Plan 010: Frontend UI conventions guardrail (doc + safe `cn` consolidation)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on. The
> code change here is deliberately tiny and behavior-preserving; the main
> deliverable is a documentation file. If anything in "STOP conditions" occurs,
> stop and report. When done, update this plan's row in `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat a9713b0..HEAD -- apps/web/src/components/ui.tsx apps/web/src/lib/utils.ts`
> If either changed since this plan was written, compare the excerpts below to the
> live code before proceeding; on a mismatch, treat as STOP.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none (independent of 008/009 — touches disjoint files; can run
  in parallel)
- **Category**: dx / docs
- **Planned at**: commit `a9713b0`, 2026-06-16

## Why this matters

The web app runs **two parallel UI systems** with no written boundary, so a
contributor (human or agent) adding a screen has no guidance on which to use and
the two drift apart:

1. **Home-brewed** (older screens): primitives in `apps/web/src/components/ui.tsx`
   backed by global CSS in `styles/base.css` + per-screen `*.module.css`, themed
   by **hex** tokens in `styles/tokens.css` (`--primary: #6b3fe0`), icons via the
   `AppIcon` wrapper (`components/icons.tsx`), relative imports.
2. **shadcn** (newer screens — `admin/AdminView.tsx`, `errors/FullError.tsx`,
   `grader/pip/PostingPiP.tsx`): primitives in `apps/web/src/components/ui/*`
   built with CVA + Tailwind utilities, themed by **oklch** tokens in
   `styles/tailwind.css` (`--ui-primary`, etc.), icons via `lucide-react`, `@/`
   alias imports, `cn` from `@/lib/utils`.

Symptoms of the missing boundary: **two `cn()` functions** (`ui.tsx:7` naive join
vs `lib/utils.ts:4` clsx+tailwind-merge), **two `Card` components** (`../ui` vs
`@/components/ui/card`), two icon conventions, two import styles, and two token
palettes that are both purple but defined independently. The stated direction is
"keep what works, add shadcn for new screens" — that is a perfectly good strategy,
but only if it's written down. This plan writes it down and removes the one piece
of duplication that is safe to remove now: the redundant `cn`.

## Current state

The naive home-brewed `cn` (only consumer is `ui.tsx` itself — no other file
imports it; verified by grep):

```ts
// apps/web/src/components/ui.tsx:7-9
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}
```

The canonical `cn` every shadcn primitive already uses:

```ts
// apps/web/src/lib/utils.ts:1-6
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

Inside `ui.tsx`, `cn` is called only with global CSS-module/base class strings
and conditionals — e.g. `cn("tabs-trigger", active && "active", className)` and
`cn(uiStyles.card, className)`. Because `generateScopedName: "[local]"` keeps
class names unhashed, `uiStyles.card === "card"`. None of these inputs are
Tailwind utility classes, so `twMerge` leaves them untouched and `clsx` resolves
conditionals exactly as `filter(Boolean).join(" ")` did → **output is
behavior-equivalent** for every call site in `ui.tsx`.

The token split the doc must describe:

```css
/* styles/tokens.css:13 (home-brewed, hex) */     --primary: #6b3fe0;
/* styles/tailwind.css:21 (shadcn, oklch) */      --ui-primary: oklch(0.496 0.265 301.924);
```

`styles/tailwind.css:10-13` already documents the `--ui-` prefixing convention
(shared names like `--primary`/`--muted`/`--border`/`--radius` are prefixed to
avoid overriding the home-brewed palette, since `tailwind.css` loads after
`tokens.css` in `main.tsx:5-7`).

## Commands you will need

| Purpose | Command (from `apps/web`) | Expected |
|---|---|---|
| Typecheck + build | `pnpm build` | exit 0 |
| Unit tests | `pnpm test:run` | exit 0 |
| Lint | `pnpm lint` | no NEW errors vs. baseline |
| Dev server (visual check) | `pnpm dev` | :5173 |

## Scope

**In scope** (create/modify only these):
- `apps/web/FRONTEND.md` (create — the conventions doc)
- `apps/web/src/components/ui.tsx` (replace the local `cn` body with a re-export
  of the canonical one — the only code change)
- `apps/web/CLAUDE.md` **or** the repo root `CLAUDE.md` — add a one-line pointer
  to `FRONTEND.md` **only if** a `CLAUDE.md` already exists at that path; do not
  create one.

**Out of scope** (do NOT touch):
- The grader screen files (`GraderReview/Setup/Queue/Wrap.tsx`) — owned by plans
  008/009; editing them here causes merge conflicts.
- The `void graderStyles` side-effect-import idiom — document it as a convention
  in `FRONTEND.md`; do **not** rewrite it in source here.
- Any token values, any `*.module.css`, any shadcn `ui/*` primitive.
- The home-brewed `Card`/`Tabs`/etc. — keep them; they back working screens.

## Git workflow

- Branch: `advisor/010-frontend-ui-conventions`
- Conventional commits, e.g. `docs(web): document UI system boundary` and
  `refactor(web): consolidate cn onto lib/utils`.
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Baseline

`pnpm build` and `pnpm test:run` pass. Note the current `pnpm lint` output (there
is a known pre-existing `GraderSetup.tsx` `selectedRubric` warning).

**Verify**: `pnpm build` → 0; `pnpm test:run` → 0.

### Step 2: Write `apps/web/FRONTEND.md`

Create the file with these sections (write them out fully — this is the
deliverable, not a stub):

1. **Two UI systems — which to use.** A short table:

   | | Home-brewed (existing screens) | shadcn (new screens) |
   |---|---|---|
   | Primitives | `components/ui.tsx` (`Card`, `Tabs`, `RadioGroup`, `SearchBox`, `EmptyState`, `InlineError`, …) | `components/ui/*` (`button`, `card`, `field`, `select`, `sheet`, …) |
   | Styling | global classes in `styles/base.css` + `*.module.css` | Tailwind utilities + CVA variants |
   | Tokens | `styles/tokens.css` (hex, `--primary`) | `styles/tailwind.css` (oklch, `--ui-primary`) |
   | Icons | `AppIcon` from `components/icons.tsx` | `lucide-react` directly |
   | `cn` | `@/lib/utils` (canonical — after this plan) | `@/lib/utils` |
   | Imports | relative (`../lib/api`) | `@/` alias |

2. **The rule.** New screens: build with shadcn (`@/components/ui/*`). Existing
   home-brewed screens: leave them on the home-brewed system — do **not** rewrite
   working screens just to migrate them. When editing a home-brewed screen, stay
   in its system; don't mix a shadcn `Button` into a `base.css` layout.

3. **CSS modules are global here.** Document that `apps/web/vite.config.ts` sets
   `css.modules.generateScopedName: "[local]"`, so every `*.module.css` is
   effectively a **global stylesheet** — class names are not hashed, and two
   modules defining the same class name will collide app-wide. Explain the
   `import graderStyles from "./Grader.module.css"; void graderStyles;` idiom:
   it injects the stylesheet for its side effect; the string class names in JSX
   resolve to its global rules. New CSS-module files must use unique,
   screen-prefixed class names (e.g. `g-` for grader) to avoid collisions.

4. **Tokens & the `--ui-` prefix.** Explain that `tokens.css` (hex) themes the
   home-brewed system and `tailwind.css` (oklch) themes shadcn; shared names are
   `--ui-`-prefixed (cite `tailwind.css:10-13`) because `tailwind.css` loads after
   `tokens.css`. Note the two palettes are currently independent and **will
   drift**; reconciling them is tracked in `plans/011-token-bridge-spike.md`.

5. **Adding a shadcn component.** One line: use the `shadcn` skill / CLI against
   `components.json` (already configured: style `radix-rhea`, base color `mauve`,
   `cssVariables: true`), which writes into `components/ui/`.

**Verify**: `apps/web/FRONTEND.md` exists and contains the five sections above
(`grep -c "Two UI systems" apps/web/FRONTEND.md` → 1).

### Step 3: Consolidate `cn` onto the canonical implementation

In `apps/web/src/components/ui.tsx`, delete the local `cn` definition (lines 7–9)
and instead re-export the canonical one. Add at the top:
`import { cn } from "../lib/utils";` and, to preserve the existing public export
(in case anything imports `cn` from `./ui` later), add `export { cn };`. Leave
every `cn(...)` call site in the file unchanged.

**Verify**:
- `pnpm build` → 0; `pnpm test:run` → 0.
- `grep -n "filter(Boolean).join" apps/web/src/components/ui.tsx` → no match.
- **Visual smoke** (`pnpm dev`, backend mock mode): open a home-brewed screen that
  uses these primitives — the Grader **Setup** screen (Card/Tabs/RadioGroup) and
  any screen with `SearchBox`/`EmptyState` — and confirm spacing, active-tab
  styling, and radio selection look identical to before. (This is the guard that
  twMerge didn't reorder/drop a class.)

### Step 4: Optional CLAUDE.md pointer

If `apps/web/CLAUDE.md` or the repo-root `CLAUDE.md` exists, add a single bullet
pointing at `apps/web/FRONTEND.md` ("Frontend UI system boundary & conventions").
If neither exists, skip — do not create a `CLAUDE.md`.

**Verify**: `pnpm build` → 0 (docs change is inert).

## Test plan

- No new automated tests (doc + a behavior-equivalent one-liner). The regression
  guard is the **visual smoke** in Step 3: home-brewed primitives render
  identically.
- If you want belt-and-suspenders, the existing `apps/web/src/lib/utils` has no
  test; you may add `apps/web/src/lib/utils.test.ts` asserting
  `cn("a", false && "b", "c") === "a c"` and that a duplicate Tailwind class is
  merged (`cn("p-2", "p-4")` ends with `p-4`), modeled on
  `apps/web/src/lib/folder-export.test.ts`. Optional.

## Done criteria

ALL must hold (from `apps/web`):

- [ ] `apps/web/FRONTEND.md` exists with the five documented sections
- [ ] `apps/web/src/components/ui.tsx` no longer defines its own `cn`
      (`grep -n "filter(Boolean).join" apps/web/src/components/ui.tsx` → empty)
      and re-exports `cn` from `../lib/utils`
- [ ] `pnpm build` exits 0; `pnpm test:run` exits 0
- [ ] `pnpm lint` reports no new errors vs. baseline
- [ ] Visual smoke: home-brewed Card/Tabs/RadioGroup/SearchBox render identically
- [ ] `git diff --name-only` lists only in-scope files
- [ ] `plans/README.md` row for 010 updated

## STOP conditions

Stop and report (do not improvise) if:

- The visual smoke shows ANY home-brewed primitive rendering differently after
  the `cn` swap — revert the `ui.tsx` change, keep the doc, and report (the doc is
  still worth landing; the `cn` swap is not worth a regression).
- Grep finds an external importer of `cn` from `./ui` whose call passes Tailwind
  utility classes that twMerge would merge differently — report it; the
  consolidation may need that call site adjusted first.
- `apps/web/vite.config.ts` no longer sets `generateScopedName: "[local]"` (the
  doc's CSS-modules section would be wrong) — re-read it and correct the doc.

## Maintenance notes

- This doc is the reference Plan 011 (token bridge) and any future shadcn
  migration should build on. Keep the "two systems" table current as primitives
  move.
- Deliberately **not** done here (to honor "don't rewrite what works"): migrating
  any home-brewed screen to shadcn, deduplicating the two `Card` components, or
  changing the `void graderStyles` idiom in source. Those are larger, screen-by-
  screen efforts to take on only when a screen is being substantially reworked
  anyway.
- Reviewer focus: the `cn` swap is behavior-equivalent only because `ui.tsx`
  passes non-Tailwind global class strings — confirm no Tailwind utilities were
  introduced into `ui.tsx` call sites alongside this change.
