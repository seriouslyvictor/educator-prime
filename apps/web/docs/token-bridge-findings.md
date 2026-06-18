# Token bridge spike findings

> Plan: `plans/011-token-bridge-spike.md`
> Branch: `spike/011-token-bridge`
> Date: 2026-06-17

---

## Summary

The spike concluded: **bridge as prototyped, with one minor dark-mode ring
adjustment**. The two-line change is safe, correct, and independently useful
even without the full palette bridge. See the [Recommendation](#recommendation)
section.

---

## What was prototyped

Two files were edited on `spike/011-token-bridge`:

### 1. `lib/theme.ts` — toggle `.dark` class

```ts
document.documentElement.classList.toggle("dark", resolvedTheme === "dark");
```

Added alongside the existing `dataset.theme` assignment. This activates
shadcn's `@custom-variant dark (&:is(.dark *))` so the `.dark { … }` token
block in `tailwind.css` fires, and Tailwind `dark:` utilities (`dark:bg-…`,
`dark:text-…`) apply on shadcn components.

### 2. `styles/tailwind.css` — bridge semantic tokens to home-brewed palette

The `:root` shadcn token block now reads:

```css
--background: var(--bg);
--foreground: var(--ink);
--card: var(--surface);
--card-foreground: var(--ink);
--popover: var(--paper);
--popover-foreground: var(--ink);
--ui-primary: var(--primary);
--primary-foreground: var(--primary-ink);
--ui-muted: var(--surface-2);
--muted-foreground: var(--muted);
--accent: var(--surface-2);
--accent-foreground: var(--ink);
--destructive: var(--danger);
--ui-border: var(--border);
--input: var(--border-strong);
--ring: var(--primary);
--sidebar: var(--surface);
/* … sidebar tokens bridged similarly … */
```

The `.dark` block is now minimal — only the tokens with **no home-brewed
equivalent** or that need dark-specific context:

```css
.dark {
    --secondary: oklch(0.274 0.006 286.033);
    --secondary-foreground: oklch(0.985 0 0);
    --input: oklch(1 0 0 / 15%);
    --ring: var(--muted);   /* softer ring in dark; pure purple glow is harsh */
}
```

Because `tokens.css` already contains a `[data-theme="dark"]` block with dark
values for every bridged variable, the shadcn surface automatically inherits
the correct dark palette as soon as both `[data-theme="dark"]` and `.dark` are
set on `<html>`.

---

## Token mapping

| shadcn token (`tailwind.css`) | home-brewed source (`tokens.css`) | Notes |
|---|---|---|
| `--background` | `--bg` | Direct match |
| `--foreground` | `--ink` | Direct match |
| `--card` | `--surface` | White surface in light, `#332f29` in dark |
| `--popover` | `--paper` | Near-white in light, `#2a2722` in dark |
| `--ui-primary` | `--primary` | Both `#6b3fe0` — exact match already |
| `--primary-foreground` | `--primary-ink` | `#ffffff` in both modes |
| `--ui-muted` | `--surface-2` | Subtle background; correct for muted containers |
| `--muted-foreground` | `--muted` | `#6d685f` light / `#b4aea3` dark — text muted |
| `--accent` | `--surface-2` | shadcn uses accent = muted by convention |
| `--accent-foreground` | `--ink` | Standard; ink on surface-2 is readable |
| `--destructive` | `--danger` | `#c7421e` light / no dark override in tokens.css (inherits light) |
| `--ui-border` | `--border` | `#e4dfd2` light / `#49433a` dark |
| `--input` | `--border-strong` | Slightly darker border for input outlines |
| `--ring` | `--primary` (light) / `--muted` (dark) | See adjustment note below |
| `--sidebar-*` | corresponding surface/ink/border tokens | Sidebar not used yet; bridged preemptively |
| `--secondary` | (none — keep oklch neutral) | No direct brand token for "secondary" surface |
| `--chart-*` | (none — keep oklch) | Chart colors have no brand equivalent |

### Adjustment made

**`--ring` in dark mode**: the plan's proposed mapping (`--ring → --primary`)
produces an intense purple focus ring on dark surfaces. Since `--primary` stays
`#6b3fe0` in dark (unchanged in `tokens.css`), the contrast is low against the
dark `--surface`. The `.dark` block overrides `--ring` to `var(--muted)`
(`#b4aea3`), which gives a neutral, readable focus indicator. If a purple ring
in dark is desired, change back to `var(--primary)` or use `var(--primary-soft)`
(`#2b2c5a`).

---

## Dark-mode resolution

**Finding: toggling `.dark` is necessary and sufficient to activate shadcn dark mode.**

Before the prototype, `lib/theme.ts:26` set only `dataset.theme`. The shadcn
`@custom-variant dark (&:is(.dark *))` declaration (line 8 of `tailwind.css`)
requires a `.dark` ancestor class. Without it, every `dark:` utility and the
`.dark { … }` CSS variable block were dead code — the three shadcn screens
stayed in light-mode colors regardless of the user's theme preference.

After adding `classList.toggle("dark", …)`, both `[data-theme="dark"]` and
`.dark` are set on `<html>` simultaneously when dark mode is active. The home-
brewed system reads `[data-theme]`; shadcn reads `.dark`. Both work correctly
with one toggle.

**Side-effect on home-brewed screens: none.** A grep for `.dark` in all
`*.module.css` files returns zero matches. No home-brewed stylesheet uses a
`.dark` selector, so adding the `.dark` class to `<html>` does not change any
home-brewed rule's specificity or applicability.

---

## Open questions / risks

1. **`--destructive` in dark mode**: `tokens.css` does not override `--danger`
   in the `[data-theme="dark"]` block — it inherits the light value `#c7421e`.
   In dark mode this is a bright red-orange on a very dark background, which has
   sufficient contrast (WCAG AA) but may look too vivid. If a softer destructive
   color in dark is wanted, add `--danger: #e07060` (or similar) to the
   `[data-theme="dark"]` block in `tokens.css`. The spike does not require this
   but it's a natural follow-up.

2. **`next-themes` `useTheme` in `sonner.tsx`**: this is a shadcn-generated
   component that imports `useTheme` from `next-themes`. However, there is no
   `ThemeProvider` from `next-themes` mounted anywhere in the app (confirmed by
   grep: zero matches for `ThemeProvider`). Without a provider, `useTheme()`
   returns the `"system"` fallback, which means the Toaster always picks
   `theme="system"`. This is cosmetically imperfect (Sonner uses its own internal
   theming) but not a STOP condition — it is a pre-existing limitation unaffected
   by this bridge. To fix it: either mount a `next-themes` `ThemeProvider` that
   reads from `resolvedTheme`, or replace `useTheme()` in `sonner.tsx` with a
   custom hook that reads `document.documentElement.dataset.theme`.

3. **`oklch`→`hex` color-space shift**: CSS computes `var(--bg)` (hex `#f6f4ee`)
   in the `sRGB` color space, whereas the previous `oklch(1 0 0)` was computed in
   OKLab. For background/surface tokens the practical difference is negligible
   (both resolve to near-white). For `--primary` (`#6b3fe0` vs. the previous
   `oklch(0.496 0.265 301.924)`), they are already visually identical — the
   original oklch value was set to match the hex brand color. No visible chroma or
   contrast regression is expected.

4. **`--secondary` has no home-brewed token**: `secondary` is a shadcn concept
   with no direct brand equivalent. The spike leaves it at the oklch neutral
   (`oklch(0.967 0.001 286.375)` light / `oklch(0.274 0.006 286.033)` dark). If
   shadcn secondary surfaces become common, the maintainer may want to add
   `--secondary` to `tokens.css` or alias it to `--surface-2`.

5. **Module CSS is globally scoped**: `vite.config.ts` sets
   `generateScopedName: "[local]"`. If a future `*.module.css` accidentally
   defines a `.dark` selector (e.g., in a file named `dark-mode-demo.module.css`),
   it would apply globally whenever the `.dark` class is present. This was not an
   issue at the time of the spike (confirmed by grep), but should be kept in mind.

---

## Screenshots

Screenshots require a running dev server (`pnpm dev`) and a browser — not
available in this headless execution environment.

**Expected observations** (based on code analysis):

### Before (baseline — no `.dark` class ever set)

- **AdminView light**: shadcn oklch colors (near-white background, purple
  primary). Looks reasonable. No dark-mode response.
- **AdminView dark**: identical to light. The `.dark` block is never applied.
- **FullError light**: white card on white background (both `--background` and
  `--card` were `oklch(1 0 0)`).
- **FullError dark**: identical to light (same bug — no `.dark` class).
- **PostingPiP light/dark**: uses home-brewed `var(--paper)`, `var(--ink)` etc.
  directly, so it correctly responds to `[data-theme="dark"]` already. Only the
  shadcn `Button` inside it (`../../ui/button`) is affected.

### After (spike prototype)

- **AdminView light**: home-brewed warm tones (`--bg: #f6f4ee`, `--ink: #14110e`).
  The purple primary (`--primary: #6b3fe0`) is identical. Overall: slightly
  warmer, more consistent with the rest of the app.
- **AdminView dark**: dark background (`--bg: #211e1a`), light text
  (`--ink: #f4f1ea`). First time the admin screen is actually dark. Cards use
  `--surface: #332f29`.
- **FullError light**: warm white background (`--bg: #f6f4ee`), card on
  `--surface: #ffffff`.
- **FullError dark**: dark background/card, light text.
- **PostingPiP**: unchanged (it already used home-brewed tokens directly).

The maintainer should visually verify these against the actual running app
before merging `plans/012-implement-token-bridge.md`.

---

## Build verification

`pnpm build` on the `spike/011-token-bridge` branch: **exit 0**.

```
✓ 1749 modules transformed.
dist/assets/index-BcNhm0oY.css  135.91 kB │ gzip: 22.62 kB
dist/assets/index-Bn8zmBTn.js   484.25 kB │ gzip: 145.80 kB
✓ built in 22.80s
```

TypeScript (`tsc -b`) and Vite both passed. No type errors introduced by the
changes (the only TS change is `classList.toggle`, which is a standard DOM API).

`pnpm test:run` / `pnpm lint`: no such scripts exist in `apps/web/package.json`
at the time of the spike (Plan 010 added `utils.test.ts` but the Vitest harness
lives at workspace level, not in `apps/web` directly). `pnpm e2e` requires a
browser and a running dev server; not feasible in headless execution — listed as
a pending human verification step.

---

## Recommendation

**Bridge as prototyped.** Proceed to `plans/012-implement-token-bridge.md`.

Rationale:

1. **The dark-mode `.dark` gap is a real bug** regardless of the palette
   question: shadcn screens don't dark-mode at all today. The one-line
   `classList.toggle` fix is the minimum change and has zero risk.

2. **The palette bridge is clean.** CSS `var()` references work across color
   spaces. Every bridged token has a clear semantic home in `tokens.css`. The
   two previously independent palettes become one.

3. **Build passes** with no errors or warnings.

4. **No module CSS uses `.dark`**, so the `classList.toggle` change is safe for
   home-brewed screens.

5. **Risk is screenshot-gated**: the maintainer should verify the three shadcn
   screens visually before merging. The plan explicitly accepts visual change to
   those screens. No home-brewed screen is affected.

The one item that still needs a human decision: whether the `--secondary` /
`--accent` oklch neutrals should eventually be aliased to brand tokens or left
as-is. For this spike's scope, leaving them as oklch neutrals is correct.

---

## Follow-up

See `plans/012-implement-token-bridge.md` for the executable implementation plan.

This document's conclusions should be linked from `apps/web/FRONTEND.md` under
the "Tokens & the `--ui-` prefix" section.
