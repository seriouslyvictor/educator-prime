# Plan 011: Spike — bridge the home-brewed and shadcn token systems

> **Executor instructions**: This is a **design/spike plan**, not a
> build-everything plan. Your deliverable is (a) a written recommendation with a
> proposed token mapping, (b) a throwaway prototype on a branch, (c) before/after
> screenshots of the three shadcn screens in light **and** dark mode, and (d) a
> concrete follow-up implementation plan. Do **not** merge the prototype. If a
> STOP condition occurs, stop and report. When done, update this plan's row in
> `plans/README.md` and link the recommendation doc you produced.
>
> **Drift check (run first)**:
> `git diff --stat a9713b0..HEAD -- apps/web/src/styles apps/web/src/lib/theme.ts`
> If these changed since this plan was written, re-read them before proceeding.

## Status

- **Priority**: P3
- **Effort**: M (spike; coarse estimate — investigation-bound)
- **Risk**: MED (any real change touches the appearance of the 3 existing shadcn
  screens, in both light and dark — this is accepted, but must be screenshot-gated)
- **Depends on**: plans/010-frontend-ui-conventions-guardrail.md (the FRONTEND.md
  it produces is the home for this spike's conclusions)
- **Category**: direction
- **Planned at**: commit `a9713b0`, 2026-06-16

## Why this matters

The app themes two UI systems from two **independent** token palettes:

- Home-brewed: `styles/tokens.css` — **hex**, e.g. `--primary: #6b3fe0`, with a
  full dark set under `[data-theme="dark"]`.
- shadcn: `styles/tailwind.css` — **oklch**, e.g. `--ui-primary: oklch(0.496
  0.265 301.924)`, with a dark set under `.dark`.

Two concrete problems this spike exists to resolve:

1. **The palettes drift.** Both are purple now, but every new shadcn screen
   inherits the oklch values, which were never tied to the established hex brand
   palette. As shadcn adoption grows ("add shadcn for new screens"), the two
   halves of the app will visibly diverge.

2. **shadcn screens don't honor dark mode today.** `lib/theme.ts:26` switches
   themes by setting `document.documentElement.dataset.theme = resolvedTheme`
   (→ `[data-theme="dark"]`). But shadcn's dark mode is keyed on a **`.dark`
   class**: `styles/tailwind.css:8` declares `@custom-variant dark (&:is(.dark
   *))`, the dark token block is `.dark { … }`, and the primitives use Tailwind
   `dark:` utilities (e.g. `dark:bg-transparent` in `components/ui/button.tsx:14`).
   Nothing ever adds the `.dark` class, so the three shadcn screens
   (`admin/AdminView.tsx`, `errors/FullError.tsx`, `grader/pip/PostingPiP.tsx`)
   stay in their light token set even when the rest of the app is dark.

A token bridge makes new shadcn screens match the brand automatically and fixes
dark mode for the shadcn surface. The user has explicitly accepted that this may
change the look of the three current shadcn screens.

## Current state (read these before proposing anything)

- `apps/web/src/styles/tokens.css` — hex palette; `:root` (light) + `[data-theme="dark"]`.
- `apps/web/src/styles/tailwind.css` — oklch palette; `:root` (light) + `.dark`;
  `@custom-variant dark (&:is(.dark *))` at line 8; `@theme inline { … }` mapping
  semantic tokens to Tailwind color utilities (lines 83–125).
- `apps/web/src/lib/theme.ts:24-27` — the toggle: sets `dataset.theme` only.
- `apps/web/src/main.tsx:5-7` — load order: `tokens.css`, then `base.css`, then
  `tailwind.css` (so `tailwind.css` wins on unprefixed duplicate names — the
  reason shared names are `--ui-`-prefixed; see `tailwind.css:10-13`).
- The three shadcn screens above are the entire blast radius for visual change.

A plausible mapping (for you to validate, not to assume correct) — point shadcn
semantic tokens at the home-brewed palette so they follow one source of truth:

| shadcn token (tailwind.css) | candidate home-brewed source (tokens.css) |
|---|---|
| `--background` | `--bg` |
| `--foreground` | `--ink` |
| `--card` / `--popover` | `--surface` / `--paper` |
| `--ui-primary` | `--primary` |
| `--primary-foreground` | `--primary-ink` |
| `--ui-muted` | `--surface-2` |
| `--muted-foreground` | `--muted` |
| `--ui-border` / `--input` | `--border` / `--border-strong` |
| `--destructive` | `--danger` |

(CSS doesn't care that the source is hex and the consumer expected oklch — a color
value is a color value. `--ui-primary: var(--primary)` is valid.) The open
question the spike must answer is **dark mode**: even if the `--ui-*` vars
reference `[data-theme]`-driven home-brewed vars, the primitives' Tailwind `dark:`
utilities still need the `.dark` class present. So the bridge almost certainly
also requires toggling `.dark` in `theme.ts`.

## Commands you will need

| Purpose | Command (from `apps/web`) | Expected |
|---|---|---|
| Typecheck + build | `pnpm build` | exit 0 |
| Dev server | `pnpm dev` | :5173 |
| E2E (regression) | `pnpm e2e` | exit 0 |

Backend mock mode: from `apps/api`,
`uv run --extra dev python -m uvicorn classroom_downloader.main:app --app-dir src --reload --port 8000`.
The `chrome-devtools` or `webapp-testing` skill (if available) can capture the
screenshots.

## Suggested executor toolkit

- `shadcn` skill — for how shadcn tokens/`components.json` are meant to be themed.
- `webapp-testing` / `chrome-devtools-mcp` skill — to drive the app and capture
  the light/dark screenshots of the three shadcn screens.

## Scope

This is a spike. **In scope to produce:**
- `apps/web/docs/token-bridge-findings.md` (create — the recommendation + mapping
  + open questions + screenshots references). If `apps/web/FRONTEND.md` (Plan 010)
  exists, link it from there instead of duplicating.
- A **prototype branch** `spike/011-token-bridge` with experimental edits to
  `styles/tailwind.css` and `lib/theme.ts` — for evaluation only, **not merged**.
- A new follow-up plan `plans/012-implement-token-bridge.md` capturing the chosen
  approach as an executable, screenshot-gated change (write it only if the spike
  concludes the bridge is worth doing).

**Out of scope** (do NOT do as part of this spike):
- Merging any visual change to `main` / the working branch.
- Touching the home-brewed `tokens.css` values (the brand palette is the source
  of truth; the bridge moves shadcn toward it, not vice-versa).
- Restyling the home-brewed screens or the grader CSS.

## Steps

### Step 1: Capture the baseline

With `pnpm dev` + mock backend, screenshot the three shadcn screens
(`AdminView`, `FullError`, `PostingPiP`) in **light** and **dark** mode (toggle via
the in-app ThemeToggle). Save under `apps/web/docs/screenshots/before/`. Note
explicitly whether each currently changes at all between light/dark (expectation
from recon: they do **not**, confirming the `.dark` gap).

**Verify**: six baseline screenshots exist (3 screens × 2 modes).

### Step 2: Prototype the bridge on `spike/011-token-bridge`

On the prototype branch, try the smallest change that makes the shadcn surface (a)
adopt the brand palette and (b) honor dark mode:

1. In `lib/theme.ts`, alongside the existing `dataset.theme` assignment, toggle the
   `.dark` class: `document.documentElement.classList.toggle("dark", resolvedTheme
   === "dark")`. This activates shadcn's `@custom-variant dark` and `dark:`
   utilities.
2. In `styles/tailwind.css`, repoint the semantic tokens at the home-brewed vars
   per the mapping table above (validate each visually; adjust where the
   borrowed value reads wrong). Do this for both the `:root` and `.dark` blocks so
   light and dark both flow from one palette.

Build and re-screenshot the three screens in both modes into
`apps/web/docs/screenshots/after/`.

**Verify**: `pnpm build` → 0; six "after" screenshots exist; `pnpm e2e` → 0 (the
e2e specs assert behavior/labels, not pixels, so they should still pass — if they
don't, that's a finding).

### Step 3: Evaluate and document

In `apps/web/docs/token-bridge-findings.md`, record:
- Before/after comparison per screen and mode (embed or reference the screenshots).
- Which mapping entries worked and which produced a wrong-looking result (and your
  adjusted value).
- The dark-mode resolution: confirm whether toggling `.dark` is necessary and
  sufficient, and whether it has any side effect on the home-brewed screens (it
  should not — home-brewed CSS keys on `[data-theme]`, not `.dark`; verify by
  screenshotting one home-brewed screen in dark before/after the `.dark` toggle).
- **Open questions / risks** for the maintainer: e.g. does any home-brewed
  `*.module.css` accidentally use a `.dark` selector? (grep and report.) Does the
  `oklch`→hex switch lose any intended chroma/contrast in dark mode?
- A clear **recommendation**: bridge as prototyped / bridge with adjustments /
  don't bridge (keep palettes separate and just fix the `.dark` dark-mode gap) /
  defer.

**Verify**: the findings doc exists and contains a recommendation section and an
open-questions section.

### Step 4: Write the follow-up implementation plan (only if recommended)

If the recommendation is to proceed, write `plans/012-implement-token-bridge.md`
using the repo's plan template (model it on this file's structure and Plan 010):
exact `styles/tailwind.css` / `lib/theme.ts` edits, the screenshot-diff gate as
the done criterion, and the three shadcn screens as the review surface. Add its
row to `plans/README.md`. If the recommendation is "don't bridge", record that in
the findings doc and in the README's "considered and rejected" section instead.

**Verify**: either `plans/012-implement-token-bridge.md` exists, or the README
rejection note exists — not neither.

## Done criteria

- [ ] `apps/web/docs/token-bridge-findings.md` exists with a token mapping,
      before/after screenshot references (light + dark, 3 screens), open
      questions, and a recommendation
- [ ] A `spike/011-token-bridge` branch exists with the prototype (NOT merged to
      the working branch)
- [ ] `pnpm build` → 0 on the prototype branch; `pnpm e2e` → 0 (or the failure is
      documented as a finding)
- [ ] Either `plans/012-implement-token-bridge.md` was written, or a rejection
      rationale recorded in `plans/README.md`
- [ ] No visual change merged to the working branch; `git diff main --name-only`
      on the working branch shows only the docs/screenshots additions
- [ ] `plans/README.md` row for 011 updated

## STOP conditions

Stop and report (do not improvise) if:

- Toggling `.dark` changes the appearance of a **home-brewed** screen (it
  shouldn't — that would mean a home-brewed stylesheet leaks a `.dark` selector;
  report which file).
- The mapping makes a shadcn screen unreadable in either mode and no
  straightforward per-token adjustment fixes it within the spike's time box —
  document the specific tokens and stop; the maintainer decides.
- You find a third theming mechanism not described here (e.g. a `next-themes`
  provider actually mounted) — report it; the dark-mode analysis would need
  revisiting (`next-themes` is a dependency but recon found theme handled by the
  custom `lib/theme.ts` hook).

## Maintenance notes

- The brand source of truth is `tokens.css` (hex). The bridge should always flow
  shadcn → brand, never the reverse, so the established look stays canonical.
- Whatever is decided, the dark-mode `.dark`-class gap is a real bug independent
  of the palette question: the three shadcn screens don't currently dark-mode at
  all. Even a "don't bridge" outcome should fix that.
- Keep `apps/web/FRONTEND.md` (Plan 010) updated with the conclusion so future
  shadcn screens inherit the decision.
