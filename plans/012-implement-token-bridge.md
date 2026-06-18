# Plan 012: Implement the token bridge

> **Status**: DONE
> **Spike**: `plans/011-token-bridge-spike.md` (findings in
> `apps/web/docs/token-bridge-findings.md`)
>
> This plan carries the spike's prototype to production. Read the findings doc
> first. The exact edits are known; this plan is the screenshot-gated execution
> checklist.

## Status

- **Priority**: P3
- **Effort**: S (changes are small; most time is screenshot verification)
- **Risk**: LOW-MED (visual change to the three shadcn screens is expected and
  accepted; home-brewed screens are unaffected)
- **Depends on**: plans/011-token-bridge-spike.md (done)
- **Category**: frontend / theming
- **Planned at**: spike `spike/011-token-bridge`, 2026-06-17
- **Completed at**: 2026-06-18 on `main`
- **Verification**:
  - `pnpm build` passed (rerun outside sandbox after esbuild `spawn EPERM`).
  - `pnpm e2e` passed: 4 tests.
  - Screenshot gate passed: 7 screenshots saved under
    `apps/web/docs/screenshots/after/`.

## Why this matters

Two concrete bugs the bridge fixes:

1. **Dark mode is broken on shadcn screens.** `AdminView`, `FullError`, and
   `PostingPiP` stay in light colors regardless of theme. Root cause: `theme.ts`
   sets `[data-theme="dark"]` but shadcn's `@custom-variant dark` requires a
   `.dark` class. One line fixes it.

2. **shadcn palette drifts from the brand.** New shadcn screens inherit
   independent oklch values. The bridge makes them read from `tokens.css` (hex
   brand palette) so they stay consistent automatically.

## Exact changes

All changes are on the working branch (not on `spike/011-token-bridge`).

### Change 1: `apps/web/src/lib/theme.ts`

In `useThemePreference`, inside the first `useEffect`, alongside the existing
`dataset.theme` assignment, add:

```ts
document.documentElement.classList.toggle("dark", resolvedTheme === "dark");
```

Full `useEffect` after the change:

```ts
useEffect(() => {
  localStorage.setItem(themeKey, mode);
  document.documentElement.dataset.theme = resolvedTheme;
  // Activate shadcn's @custom-variant dark (&:is(.dark *)) so shadcn screens
  // honour dark mode. The home-brewed system keys on [data-theme] only; no
  // *.module.css uses a .dark selector, so this toggle has no side-effect there.
  document.documentElement.classList.toggle("dark", resolvedTheme === "dark");
}, [mode, resolvedTheme]);
```

### Change 2: `apps/web/src/styles/tailwind.css`

Replace the `:root` and `.dark` token blocks (lines 14–81) with the bridged
version from the spike. Key substitutions:

| Token | New value |
|---|---|
| `--background` | `var(--bg)` |
| `--foreground` | `var(--ink)` |
| `--card` | `var(--surface)` |
| `--popover` | `var(--paper)` |
| `--ui-primary` | `var(--primary)` |
| `--primary-foreground` | `var(--primary-ink)` |
| `--ui-muted` | `var(--surface-2)` |
| `--muted-foreground` | `var(--muted)` |
| `--accent` | `var(--surface-2)` |
| `--accent-foreground` | `var(--ink)` |
| `--destructive` | `var(--danger)` |
| `--ui-border` | `var(--border)` |
| `--input` | `var(--border-strong)` |
| `--ring` | `var(--primary)` (light) / `var(--muted)` (dark) |
| `--sidebar-*` | corresponding surface/ink/border tokens |
| `--secondary` / `--chart-*` | keep oklch (no brand equivalent) |

The `.dark` block shrinks to only override `--secondary`, `--secondary-foreground`,
`--input`, and `--ring` (the tokens without home-brewed equivalents or that
need dark-specific values).

See the spike branch for the exact diff: `git diff main spike/011-token-bridge --
apps/web/src/styles/tailwind.css`.

## Steps

### Step 1: Apply the two changes

Copy the exact edits from `spike/011-token-bridge` to the working branch:

```sh
git checkout spike/011-token-bridge -- apps/web/src/lib/theme.ts
git checkout spike/011-token-bridge -- apps/web/src/styles/tailwind.css
```

Or apply manually using the "Exact changes" section above.

### Step 2: Build and lint

From `apps/web`:

```sh
pnpm build   # must exit 0
```

**Verify**: exit 0. The spike already confirmed this works.

**Result 2026-06-18**: passed with `pnpm build`.

### Step 3: Screenshot gate (human required)

Start the dev server and mock backend, then screenshot the three shadcn screens
in **both light and dark mode**:

- `AdminView` (route: `/admin`)
- `FullError` (trigger: navigate to an invalid route, or throw in ErrorBoundary)
- `PostingPiP` (trigger: open a grading job with submissions and start posting)

For each screen verify:
- [x] Light mode: warm neutral tones matching the rest of the app
- [x] Dark mode: dark background (`--bg: #211e1a`), light text (`--ink: #f4f1ea`)
- [x] Dark mode: screen is visually different from light mode (the key regression to catch)
- [x] `AdminView` dark: cards use `--surface: #332f29` (dark brown, not near-black)

Also screenshot one home-brewed screen (e.g., the grader queue) in dark mode to
confirm it is unchanged.

Save screenshots under `apps/web/docs/screenshots/` as evidence.

**Result 2026-06-18**: saved evidence under `apps/web/docs/screenshots/after/`:

- `plan012-admin-light.png`
- `plan012-admin-dark.png`
- `plan012-full-error-light.png`
- `plan012-full-error-dark.png`
- `plan012-posting-pip-light.png`
- `plan012-posting-pip-dark.png`
- `plan012-workspace-dark.png`

### Step 4: E2E regression

```sh
pnpm e2e   # must exit 0
```

The e2e specs assert behavior/labels, not pixels, so they should pass. If they
don't, that's a finding — document and fix before merging.

### Step 5: Update docs

In `apps/web/FRONTEND.md`, under "Tokens & the `--ui-` prefix", update the
"Known dark-mode gap" note to say the gap is fixed. Add a line pointing to
`apps/web/docs/token-bridge-findings.md` for the mapping rationale.

**Result 2026-06-18**: updated `apps/web/FRONTEND.md`.

### Step 6: Commit and update README

```sh
git add apps/web/src/lib/theme.ts apps/web/src/styles/tailwind.css apps/web/FRONTEND.md
git commit -m "fix(web): bridge shadcn tokens to brand palette; fix dark mode on shadcn screens"
```

Update `plans/README.md` row 012 to DONE.

## Done criteria

- [x] `pnpm build` -> 0
- [x] `pnpm e2e` -> 0 (or failure documented)
- [x] Six screenshots exist (3 screens x 2 modes) confirming dark mode now works
- [x] One home-brewed screen screenshot confirms it is unchanged in dark mode
- [x] `apps/web/FRONTEND.md` updated
- [x] `plans/README.md` row 012 -> DONE
- [x] Not merged until human screenshot review is complete

## STOP conditions

- Any home-brewed screen changes appearance in dark mode (would mean a
  `*.module.css` has a `.dark` selector — grep found none at spike time; re-check
  if new files were added since then).
- A shadcn screen is unreadable in either mode after the bridge.
- `pnpm build` fails.

## Maintenance notes

- Keep `tokens.css` (hex) as the single source of truth. Never edit `tailwind.css`
  tokens directly — edit `tokens.css` and the bridge propagates automatically.
- `--secondary` and `--chart-*` are not bridged (no brand equivalent). If a new
  screen needs a secondary surface, discuss whether it maps to `--surface-2` or
  needs a new `tokens.css` entry.
- If `--danger` ever needs a dark-mode variant, add it to `tokens.css`
  `[data-theme="dark"]` — the bridge in `tailwind.css` will pick it up automatically.
