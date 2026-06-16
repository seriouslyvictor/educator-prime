# Frontend conventions

This app currently runs **two parallel UI systems** with no enforced boundary. This
document writes down the boundary so it doesn't keep drifting.

## Two UI systems — which to use

| Concern | Home-brewed (older screens) | shadcn (newer screens) |
| --- | --- | --- |
| Primitives | `components/ui.tsx` — `Card`, `Tabs`, `RadioGroup`, `SearchBox`, `EmptyState`, `InlineError` | `components/ui/*` — `button`, `card`, `field`, `select`, `sheet` |
| Styling | Global classes in `styles/base.css` + per-screen `*.module.css` | Tailwind utilities + CVA variants |
| Tokens | `styles/tokens.css`, hex (`--primary: #6b3fe0`) | `styles/tailwind.css`, oklch (`--ui-primary: oklch(...)`) |
| Icons | `AppIcon` wrapper from `components/icons.tsx` | `lucide-react` directly |
| `cn` | `@/lib/utils` (canonical — `ui.tsx` re-exports it after this plan) | `@/lib/utils` |
| Imports | Relative (`../lib/api`) | `@/` alias |

Screens currently on shadcn: `admin/AdminView.tsx`, `errors/FullError.tsx`,
`grader/pip/PostingPiP.tsx`.

## The rule

- **New screens**: build with shadcn (`@/components/ui/*`).
- **Existing home-brewed screens**: leave them on the home-brewed system. Do **not**
  rewrite a working screen just to migrate it to shadcn.
- When editing a home-brewed screen, stay inside its system — don't mix a shadcn
  `Button` into a `base.css`-driven layout. Mixing systems on one screen is how the
  two palettes and two `Card` components end up colliding visually.

## CSS modules are global here

`apps/web/vite.config.ts` sets:

```ts
css: {
  modules: {
    generateScopedName: "[local]",
  },
},
```

This means every `*.module.css` file is, in practice, a **global** stylesheet — class
names are emitted unhashed. Two different `*.module.css` files that define the same
class name (e.g. `.card`) collide app-wide, not just within their own component.

This is why some grader files do:

```ts
import graderStyles from "./Grader.module.css";
void graderStyles;
```

The import is kept purely for its **side effect** — it injects the stylesheet into the
page. The `void` marks the binding as intentionally unused (so lint doesn't flag it),
because the JSX in that file references the class names as plain strings (e.g.
`className="g-panel"`) rather than through `graderStyles.panel`. Since the rules are
global anyway, referencing them via the module object isn't required for them to apply.

**Convention for new CSS-module files**: use unique, screen-prefixed class names (e.g.
`g-` for grader screens) so a new module's classes can't collide with another screen's
classes that happen to share a name.

## Tokens & the `--ui-` prefix

- `styles/tokens.css` (hex) themes the home-brewed system.
- `styles/tailwind.css` (oklch) themes shadcn.
- `tailwind.css` loads after `tokens.css` (see `main.tsx:5-7`), so any variable name
  shared between the two files would have the shadcn value win and silently override
  the home-brewed palette. To prevent that, shared names are prefixed with `--ui-` in
  `tailwind.css` — see the comment at `tailwind.css:10-13`:

  ```css
  /* Shared variable names that also exist in tokens.css (--primary, --muted,
     --border, --radius) are prefixed with --ui- here: this file loads after
     tokens.css, so unprefixed duplicates would override the app palette
     (e.g. light-theme muted text turning near-white). */
  ```

- The two palettes (`tokens.css` hex vs. `tailwind.css` oklch) are currently
  **independent and will drift** as each is edited in isolation. Reconciling them is
  tracked in `plans/011-token-bridge-spike.md`.
- **Known dark-mode gap**: theme switching sets `[data-theme="dark"]` on the root (see
  `lib/theme.ts`), which the home-brewed system's CSS responds to. shadcn's dark-mode
  variant, however, keys off a `.dark` class (`@custom-variant dark (&:is(.dark *));`
  in `tailwind.css:8`) that is never applied anywhere in this app. As a result, shadcn
  screens do not currently honor dark mode. Also tracked in plan 011.

## Adding a shadcn component

Use the `shadcn` CLI against `components.json` (configured: style `radix-rhea`, base
color `mauve`, `cssVariables: true`) — it writes the new primitive into `components/ui/`.
