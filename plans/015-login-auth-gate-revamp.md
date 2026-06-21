# Plan 015 — Login / Auth-Gate Revamp (shadcn, scenario-complete)

First plan of the UI-revamp track.

## Context

Teachers get lost in the current UI. We are revamping the whole app behind a
wizard + stepper, rebuilt on shadcn primitives, sweeping the old home-brewed UI
out **as we go** (no leftovers). We start with the **login / auth gate** because
it is the front door and must be bulletproof: it has to handle every real-world
Google sign-in outcome with appropriate, friendly handling — including accounts
with no Classroom, account types Classroom rejects, denied/partial scope grants,
and org-policy blocks that are outside our control.

The app is **Google-OAuth-only** (no password auth exists in the backend) and
uses **incremental capability scopes**: `identity` → `classroom_read` →
`drive_read` (`google_scopes.py`, `routers/auth.py`). Auth/policy failures flow
`ApiError(code)` → `lib/errorCatalog.ts` → `Gate`/`InlineError`. shadcn is
already wired (`components.json`, `components/ui/*`, token bridge from plans
011–012). Logic and user flows are preserved — this is a UI rebuild plus the
**minimum** backend signals needed to render the missing scenarios.

Decisions locked with the maintainer:
1. **Google-only** login — drop the imported design's demo email/password form;
   keep its two-pane marketing layout. The only real action is "Continuar com o Google".
2. **Full auth gate** in scope — sign-in **and** the staged Classroom/Drive
   permission requests **and** the full error/edge matrix (replaces `ConnectView`).
3. **Dedicated explainer** for no-Classroom accounts (distinct from generic errors).
4. **Error-state e2e via Playwright route stubs** (frontend rendering), live-Google
   suite stays the happy-path source of truth, untouched.

Design reference: Claude Design project `Classroom Streamer`
(`92ebf79d-1322-432d-82fb-7c0aeff1e1ba`), file `app/login.jsx` (two-pane,
value-prop steps, brand mark) — adapted to Google-only.

## Goals / Non-goals

**Goals**
- Replace `ConnectView` with a shadcn auth gate covering the whole pre-workspace
  experience and every sign-in scenario below.
- Close the backend gap where a denied/blocked Google consent crashes the callback.
- Add deterministic tests (vitest reducer + pytest callback/mapping + Playwright
  route-stub specs) that exercise the full scenario matrix.
- Remove the old login UI completely (component + CSS + dead references).

**Non-goals (later plans)**
- The functional wizard/stepper for the grading flow (turma→…→postar). The login
  aside's "1·2·3" steps are **static marketing**, not the functional stepper.
- Reworking workspace/grader/history screens. Drive just-in-time consent is
  reskinned here only because it is part of the permission concern.

## Scenario matrix (the spec — "cover all login scenarios")

The gate is rendered by a **pure reducer** so each row below is a unit test.

| # | Scenario | Trigger / signal | Rendered state |
|---|----------|------------------|----------------|
| 1 | Booting | `loading` during `bootstrap()` | Full-screen skeleton (shadcn `Skeleton`/`Spinner`) |
| 2 | Signed out | `!signed_in` | Login two-pane, CTA "Continuar com o Google" |
| 3 | Identity granted, Classroom pending | `signed_in && !classroom_scopes` | Permission stage: explain + grant Classroom (`partialConsent`) |
| 4 | Partial consent (unchecked Classroom box) | `signed_in && !classroom_scopes` after a classroom attempt | Same stage + warning that the box must be checked |
| 5 | Connected, has courses | `connected && courses.length>0` | Leave gate → workspace |
| 6 | **Connected, no courses** | `connected && courses.length===0` (200 `[]`) | **No-Classroom explainer** ("nenhuma turma para corrigir") + switch account |
| 7 | **Classroom unavailable for account type** | 403 → new `classroom_not_available` | Explainer ("esta conta não tem acesso ao Classroom") + switch account |
| 8 | **Consent denied on Google** | callback `error=access_denied` → `?google=error&reason=google_auth_denied` | Gate `google_auth_denied` + reconnect |
| 9 | **Org policy blocked** | callback `error=admin_policy_enforced`/`org_internal` → new `google_policy_blocked` | Gate explaining the admin blocked the app + switch account |
| 10 | OAuth not configured | 503 `oauth_not_configured` | Admin gate (`adminHint`) |
| 11 | Google session expired (weekly in Testing) | 401 `google_session_expired` | Gate + reconnect (existing copy) |
| 12 | Google rate-limited / unavailable | `google_rate_limited` / `google_unavailable` | Banner over the gate |
| 13 | API offline / unreachable | `unreachable` / connectivity | Gate / `OfflinePill` (existing) |
| 14 | Version skew | `version_skew` | Banner (existing) |
| 15 | Switch account / sign out from any state | logout action | Back to scenario 2 |

"Non-Google account" is not directly reachable (Google hosts the login), so it
collapses into 8/9 (Google rejects or org blocks) — handled, not a separate UI.

## Frontend changes

New folder `apps/web/src/components/auth/` (shadcn, `@/` imports, lucide icons):

- **`authState.ts`** — pure reducer `resolveAuthStage({ auth, loading, courses, error })`
  → discriminated union (`booting | signin | grant-classroom | no-courses |
  classroom-unavailable | policy-blocked | gate | ready`). This is the heart of
  the matrix and the unit-test target. Reuse existing booleans from
  `useConnection` (`signedIn`, `classroomReady`, `connected`, `partialConsent`).
- **`AuthGate.tsx`** — renders the stage; replaces the `view === "connect"` block
  in `App.tsx`. Hosts banners (rate-limit/skew) and the `OfflinePill`.
- **`LoginScreen.tsx`** — two-pane shadcn layout (brand mark, value-prop steps as
  static list, single Google CTA `Button`). Adapted from design `app/login.jsx`,
  Google-only, pt-BR.
- **`PermissionStage.tsx`** — Classroom (and Drive JIT) consent card using shadcn
  `Card`/`Button`/`Separator`; scope list with plain-language copy (port the good
  copy already in `ConnectView`/`useConnection` reasons).
- **`AuthExplainer.tsx`** — shared empty/explainer (shadcn `Empty`) for scenarios
  6, 7, 9, with a "Trocar de conta" (logout) action.
- **`AccountChip.tsx`** — signed-in account display (avatar + email) reused by the
  stage and explainers.

`App.tsx`:
- Render `<AuthGate .../>` instead of `<ConnectView .../>`; pass `courses`,
  `loading`, `auth`, `error`, and the connect/ logout callbacks already available.
- **Hide the `Rail`** while `view === "connect"` so the login is full-bleed
  (matches the design). Currently `Rail` always renders (`App.tsx:258`).
- Reskin `DrivePermissionPanel` (inline `App.tsx:501`) into the new
  `PermissionStage`/a shadcn `Dialog` — remove the `notice`/`btn` old classes.

shadcn primitives to add via CLI (`pnpm dlx shadcn@latest add ...` against
`components.json`): **`alert`**, **`avatar`**, **`dialog`** (others already exist:
button, card, field, separator, empty, skeleton, spinner, badge, label).

**Old-UI sweep (no leftovers):**
- Delete `components/ConnectView.tsx` and `components/ConnectView.module.css`.
- Remove now-dead `notice`/`scope-*`/`connect-*` rules from `styles/base.css`
  **only if** unused elsewhere (grep first — some `notice` usage remains in
  `GradingHealthBanner`; keep what's still referenced, delete the login-only rules).
- Keep the `connect` view id (minimal churn) but it now renders `AuthGate`.

## Backend changes (minimum)

`apps/api/src/classroom_downloader/routers/auth.py` — `auth_callback`:
- Make `code`/`state` **optional**; accept `error` and `error_description` query
  params. On `error`, or on a missing/failed exchange, **redirect** to
  `{frontend_origin}/?google=error&reason=<code>` instead of raising 422/500.
- Map Google error values → app codes: `access_denied`→`google_auth_denied`;
  `admin_policy_enforced`/`org_internal`/`disallowed_useragent`→`google_policy_blocked`;
  fallback→`google_auth_denied`. Wrap `flow.fetch_token` in try/except to catch
  exchange failures the same way.
- Frontend bootstrap reads `?google=error&reason=` (it already reads
  `?google=connected`) and seeds the gate error.

`apps/api/src/classroom_downloader/api/google_errors.py` (+ `courses.py`):
- Map a Classroom-disabled / account-type 403 to a new **`classroom_not_available`**
  code (verify exact Google reason strings during execution; distinguish from the
  hard-auth 403 already handled in `auth_errors.py`).

`lib/errorCatalog.ts` — add entries: **`classroom_not_available`** (info, switch
account), **`google_policy_blocked`** (warning, switch account). The
`no-courses` state (scenario 6) is **not** an error — it is a reducer branch off a
successful empty `courses` response, so no catalog entry.

`types.ts` — extend `ApiError` codes/union as needed; no `AuthState` shape change
required (empty courses already representable).

## Tests

**Frontend unit (vitest)** — `components/auth/authState.test.ts`: assert every
row of the matrix maps to the right stage. Pure, deterministic, fast — this is the
primary "test the shit out of it" guarantee.

**Backend (pytest)** — extend `tests/test_oauth_callback.py`: `error=access_denied`
and `error=admin_policy_enforced` redirect to the right `?google=error&reason=`;
malformed/expired state still 400. Add a `courses` test asserting the
`classroom_not_available` 403 mapping.

**E2E (Playwright)** — keep `e2e/live-classroom.spec.ts` (happy path) untouched.
Add `e2e/auth-states.spec.ts` that uses `page.route` to stub `/api/auth/me` and
`/api/courses` per scenario (2, 3, 6, 7, 8/9 via `?google=error`, 11, 13) and
asserts the correct gate/explainer renders (stable `data-screen-label` /
`data-auth-stage` seams + visible copy). Header-comment it clearly as
**frontend-rendering** tests, not a live-Google integration (honors the live-e2e
philosophy: live for the real path, stubs only for UI states Google can't produce
on demand).

Add a `data-auth-stage={stage}` attribute on the gate root for test seams (mirrors
the existing `data-screen-label` pattern in `App.tsx:257`).

## Verification (end-to-end)

1. `cd apps/web && pnpm build && pnpm test` — reducer matrix green.
2. `cd apps/api && uv run pytest tests/test_oauth_callback.py -q` — callback error
   redirects + mapping green.
3. `cd apps/web && pnpm e2e` — live happy path + `auth-states` stub specs green
   (fails loud if baked creds missing, per existing harness).
4. Manual: run the app (dev servers), in mock provider confirm the happy
   gate→workspace; with the real test account confirm sign-in; force scenarios 6–9
   via the route-stub specs' fixtures.
5. Confirm the old login is gone: `git grep -n "ConnectView\|scope-item\|connect-card"`
   returns nothing live; `pnpm lint` clean.

## Critical files

- Rebuild target: `apps/web/src/components/ConnectView.tsx` (+ `.module.css`) → **deleted**.
- New: `apps/web/src/components/auth/{authState.ts,authState.test.ts,AuthGate.tsx,LoginScreen.tsx,PermissionStage.tsx,AuthExplainer.tsx,AccountChip.tsx}`.
- Edit: `apps/web/src/App.tsx` (render `AuthGate`, hide `Rail` on connect, reskin Drive panel), `apps/web/src/lib/errorCatalog.ts`, `apps/web/src/types.ts`.
- Backend: `apps/api/src/classroom_downloader/routers/auth.py`, `apps/api/src/classroom_downloader/api/google_errors.py`, `apps/api/src/classroom_downloader/routers/courses.py`.
- Tests: `apps/web/src/components/auth/authState.test.ts`, `apps/web/e2e/auth-states.spec.ts`, `apps/api/tests/test_oauth_callback.py`.
- Reuse: `useConnection` booleans/callbacks (`hooks/useConnection.ts`), `resolveError`/catalog (`lib/errorCatalog.ts`), `Gate`/`OfflinePill` (`components/errors/`), `cn` (`lib/utils`).

## Risks / notes

- The Classroom-403 reason strings for `classroom_not_available` must be verified
  against real Google responses during execution; until confirmed, fall back to the
  existing generic Google-error path (no regression).
- `styles/base.css` is global (CSS-modules unhashed, see `FRONTEND.md`) — grep
  before deleting any shared rule (`notice` is still used by `GradingHealthBanner`).
- Per `FRONTEND.md`, build the new screen fully on shadcn; do not mix old `btn`/
  `notice` classes into it.


## Execution status

- Branch: `codex/015-login-auth-gate-revamp`
- Status: implemented; ready for PR review.
- Frontend auth gate: replaced `ConnectView` with shadcn-based `AuthGate`, reducer-backed stages, Google-only login, permission stages, no-Classroom/account-policy explainers, and `data-auth-stage` test seam.
- Backend auth callback: handles Google callback `error` values and token-exchange failures by redirecting to `?google=error&reason=...`; expired/malformed OAuth state remains 400.
- Classroom unavailable mapping: added conservative 403 mapping for account types without Classroom.
- Old login sweep: deleted `ConnectView.tsx` and `ConnectView.module.css`; `git grep -n "ConnectView|connect-card|scope-item" apps/web/src` returns no matches.
- Verification:
  - `pnpm test -- --run` passed: 5 files, 33 tests.
  - `pnpm build` passed.
  - `uv run pytest tests/test_oauth_callback.py tests/test_google_errors.py -q` passed: 5 tests.
  - `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` passed: 224 passed, 4 skipped.
  - `pnpm lint` exited 0 with 14 existing warnings.
  - `auth-states.spec.ts` passed against Vite on temporary port 5185 with route stubs.
  - Full `pnpm e2e` was blocked because an existing backend from `D:\Classroom Downloader` was already serving `http://127.0.0.1:8000/api/health`; the Playwright config intentionally refuses to reuse that server.
