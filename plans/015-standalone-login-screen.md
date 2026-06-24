# Plan 015 — Standalone login screen (separate from the dashboard shell)

> Source: Notion "Classroom Downloader - IA grading draft" → TODO
> "Criar tela de login separada do dashboard (verificar tela de login nova no
> MCP do Claude Design - Educator Prime)".
> Theme: **A — Auth & onboarding**. Priority P1. Effort S–M. Depends on: none.
> Base: branch off `main` @ `6d6b264`.

## Why
Today the unauthenticated state is rendered **inside the app shell**: `App.tsx`
always mounts `<Rail … />` and then `<main>` containing `ConnectView` when
`view === "connect"` (`apps/web/src/App.tsx:242-272`). So a logged-out user sees
the navigation rail (with disabled nav, theme toggle, logout) wrapped around a
welcome card. The maintainer wants a **dedicated full-bleed login screen** with
no dashboard chrome, matching the new design in the "Educator Prime" design
reference — while keeping the **exact same auth behavior** as today.

## Hard constraint — behavior is unchanged
The OAuth flow must not change. The login screen's only action is still
`connectClassroom()` from `useConnection` (`apps/web/src/hooks/useConnection.ts`,
wired in `App.tsx:156-176`). Same scopes, same redirect, same `deliveryMode`
notice, same error surface (`InlineError` / gate errors), same
"connected → workspace" transition (`App.tsx:178-182`). This is a **presentation
refactor**, not an auth change. Do not touch `routers/auth.py`, the OAuth scopes,
or `useConnection`'s logic.

## Design reference (operator action required)
The new layout lives in the **"Claude Design – Educator Prime"** MCP design, per
the Notion note. That MCP is **not available in the agent environment** — before
building, the human/operator must export the target login layout (screenshot or
spec) into `apps/web/docs/` or paste it into the executing session. If it is
unavailable, fall back to restyling the **existing** `ConnectView` card full-bleed
(centered, no rail) and STOP for design review before merging — do not invent a
new visual language.

## A branch already exists
`codex/015-login-auth-gate-revamp` ("Implement login auth gate revamp") is a prior
attempt. Per the Plan 013 lesson in `plans/README.md`, earlier codex attempts were
built on **stale bases**. Treat that branch as reference only: diff it against
`main`, salvage anything correct, but **start fresh from `main` HEAD**. It also
contains `ci: pause web-e2e during the UI revamp` — do **not** carry that over;
the e2e suite must stay green (see Acceptance).

## Files
- `apps/web/src/App.tsx` — the shell decision (Rail vs no Rail).
- `apps/web/src/components/ConnectView.tsx` — the login card (reuse/restyle).
- `apps/web/src/components/ConnectView.module.css` — full-bleed styles.
- `apps/web/src/components/Rail.tsx` — confirm it is simply *not mounted* when
  logged out (no internal "hide when disconnected" hack needed).
- `apps/web/e2e/` — the boot/login specs assert on `data-screen-label` and the
  connect button; keep those selectors working.

## Steps
1. In `App.tsx`, split rendering into two top-level branches:
   - **Logged-out / connect** (`view === "connect"` and not `connected`): render a
     standalone `<LoginScreen>` (the restyled `ConnectView`) with **no `Rail`** and
     no dashboard `<main>` wrapper. Keep `data-screen-label="connect"` on the root
     so e2e and the gate logic still find it.
   - **Logged-in**: render the existing shell (`Rail` + `main` + all views) exactly
     as today.
   Keep the gate-error path (`gateError`, `handleGateAction`, `partialConsent`) and
   `versionSkew`/`OfflinePill` working in both branches — a gate error while
   logged out must still show on the login screen.
2. Make `ConnectView` (or a thin `LoginScreen` wrapper) full-bleed: centered,
   own background, no rail gutter. Preserve every existing element — logo, scopes
   list, delivery-mode `Notice`, `InlineError`, the connect button with its
   loading state, and the privacy footnote.
3. Verify the connect → `connected` → `workspace` transition is untouched and the
   Rail appears only after sign-in.
4. Confirm theme toggle still works post-login (it lived in the Rail); the login
   screen may show a minimal theme toggle if the design calls for one, but that is
   optional and must not regress the post-login toggle.

## Acceptance / STOP
- `pnpm --filter web build`, `pnpm --filter web test`, `pnpm --filter web lint`
  all green.
- `pnpm --filter web e2e` green **without** disabling/pausing any spec. If a boot
  or logout spec asserts the rail is present on the connect screen, update the spec
  to the new contract (rail absent when logged out) — but never delete coverage.
- Manual smoke (human): logged-out shows the standalone screen with no rail;
  clicking connect runs the identical OAuth flow; after sign-in the full dashboard
  (rail + workspace) appears; logout returns to the standalone screen.
- **STOP for design review** if the Educator Prime reference could not be obtained
  and you fell back to a restyle.
