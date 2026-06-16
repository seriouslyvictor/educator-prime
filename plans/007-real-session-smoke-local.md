# Plan 007: Local real-session smoke for authenticated core flows (incl. true logout)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. This suite is **local-only and never runs in CI**. If anything in
> the "STOP conditions" section occurs, stop and report — do not improvise. When
> done, update the status row for this plan in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat b61ac5a..HEAD -- apps/web/src/App.tsx apps/web/src/components/Rail.tsx apps/api/src/classroom_downloader/routers/auth.py apps/api/src/classroom_downloader/main.py`
> If any changed since this plan was written, re-confirm the selectors and the
> static-serving behavior in "Current state" before proceeding; on a mismatch,
> treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW (local-only; read-only flows + logout against the developer's own
  test account)
- **Depends on**: plans/006-playwright-e2e-core-flows.md (reuses the Playwright
  install, the selector seams, and the spec conventions). Can stand alone if 006
  is not done — then this plan installs Playwright itself (Step 1).
- **Category**: tests
- **Planned at**: commit `b61ac5a`, 2026-06-13

## Why this matters

A core flow (logout) broke in a live demo. The mock-mode E2E (Plan 006) and the
existing backend test (`apps/api/tests/test_api.py:133`
`test_logout_deletes_google_token`) cover the frontend wiring and the backend
session-delete, but neither exercises the **real session lifecycle**: a genuine
`cd_session` cookie tied to a real Google OAuth session, and the production-shape
single-origin serving. The one assertion only a real session can make is the one
that matters for the demo bug: **after logout, a page reload stays logged out**.
In mock mode `auth_me` always returns `signed_in=True`, so that reload assertion
is meaningless; only a real, deletable session proves logout actually ended the
session.

This plan adds a **local, on-demand** Playwright smoke that runs against a
**production-like build** (FastAPI serving the built frontend on a single origin,
exactly as the Docker/Coolify deployment does) using the **real `google`
provider**. Authentication is done **once, manually, by a human** via Playwright's
`storageState` pattern — the Google consent screen is never automated, and **no
Google password is ever stored**. Run it before a demo or a deploy.

### Hard privacy constraint (this app's whole reason for existing)

This suite touches **real student data** (real Classroom rosters / Drive files
via `drive.readonly`). Therefore:
- Disable Playwright traces and video; screenshots only on failure
  (screenshots may contain real student names — they stay local and gitignored).
- The saved session file and all Playwright artifacts MUST be gitignored.
- Keep flows **read-only**. Do NOT trigger privacy audit, criteria inference, or
  drafting (those send data to the LLM and cost money). Do NOT run folder export
  (`showDirectoryPicker` isn't automatable anyway).

## Current state

- **Production serving model** (`apps/api/src/classroom_downloader/main.py:180-203`):
  when `settings.static_dir` points at a built frontend dir, FastAPI serves it
  with an SPA fallback to `index.html`. The root `Dockerfile` uses this to serve
  the Vite build from FastAPI on port 8000 (single origin) — README "Docker /
  Coolify deployment". The local prod-like target reproduces this on
  `http://localhost:8000`.
- **OAuth config** (`settings.py:37-39`): real mode needs `CD_GOOGLE_CLIENT_ID`,
  `CD_GOOGLE_CLIENT_SECRET`, and `CD_GOOGLE_REDIRECT_URI`. The documented dev
  redirect is `http://localhost:8000/api/auth/google/callback`
  (`apps/api/.env.example`) — already registered in the Google Cloud console for
  this project. **Use `localhost`, not `127.0.0.1`**, everywhere here so the
  cookie domain and the registered redirect URI match.
- **Callback sets the session cookie** (`routers/auth.py:256-266`):
  `cd_session`, `httponly=True`, `secure=is_prod` where
  `is_prod = frontend_origin.startswith("https://")`, `samesite="lax"`,
  `path="/"`. Over local http, `secure` is false, so the cookie works locally.
  (See "Known limitation" — the `secure=true` HTTPS path is only reproducible
  against live production, which is out of scope for this local plan.)
- **Logout** (`routers/auth.py:118-134`): in `google` mode, deletes the
  `UserSession` row, purges cached classroom state, and clears the cookie. After
  this, `auth_me` returns disconnected and a reload cannot restore the session.
- **Session lifetime**: `session_max_age_hours` default 24 (`settings.py:43`), so
  the captured session expires after ~24h; the underlying Google refresh token
  expires per the project's OAuth **Testing mode** (~7 days). Re-run the auth
  setup whenever the smoke fails at the boot step.
- **Selectors** (verified, same as Plan 006):
  - Shell `data-screen-label={view}` (`App.tsx:1149`).
  - Logout button: `getByTitle("Sair da conta Google")` (`Rail.tsx:96`), shown
    only when signed in.
  - Rail nav by text: `Corrigir com IA`, `Turmas`, `Histórico` (`Rail.tsx:49-72`).
  - Connect CTA: `Conectar conta Google escolar` (`ConnectView.tsx:49`).
- If Plan 006 landed, `@playwright/test` and `apps/web/e2e/` already exist; reuse
  them. If not, Step 1 installs Playwright.

## Commands you will need

| Purpose                 | Command (from `apps/web` unless noted)                          | Expected           |
|-------------------------|----------------------------------------------------------------|--------------------|
| Add dep (if no 006)     | `pnpm add -D @playwright/test`                                  | exit 0             |
| Install browser         | `pnpm exec playwright install chromium` (and `chrome` channel) | downloads browser  |
| Build frontend          | `pnpm build`                                                    | exit 0, `dist/`    |
| Auth setup (manual)     | `pnpm e2e:real:auth`                                            | human logs in; session file saved |
| Run real smoke          | `pnpm e2e:real`                                                 | specs pass         |
| Backend (prod-like)     | see Step 2 — run from `apps/api`                                | serves on :8000    |

## Scope

**In scope** (create):
- `apps/web/playwright.real.config.ts`
- `apps/web/e2e-real/auth.setup.ts` (manual login → save storageState)
- `apps/web/e2e-real/core-flows.spec.ts` (boot, navigation, queue, logout-last)
- `apps/web/package.json` (add `e2e:real` and `e2e:real:auth` scripts)
- `apps/web/.gitignore` — ignore `.auth/`, `playwright-report*/`, `test-results*/`
- `docs/real-session-smoke.md` (short runbook: prerequisites + how to run)

**Out of scope** (do NOT touch):
- CI (`.github/workflows/ci.yml`) — this suite never runs in CI.
- Production source code (assert via existing seams only; if a flow needs a new
  `data-testid`, STOP and report).
- Any write/cost flow: privacy audit, inference, drafting, export.
- The mock E2E from Plan 006 (`apps/web/e2e/`, `playwright.config.ts`).
- The real `.env` / any credential values — never commit or echo them.

## Git workflow

- Branch: `advisor/007-real-session-smoke-local`
- Commit style: conventional commits, e.g.
  `test(web): add local real-session smoke for auth core flows`.
- Do NOT push or open a PR unless instructed. **Confirm `git status` shows no
  `.auth/` file and no Playwright artifacts staged before any commit.**

## Prerequisites (document these; do not perform credential setup yourself)

The developer must already have, in `apps/api/.env`:
- `CD_GOOGLE_PROVIDER=google`
- `CD_GOOGLE_CLIENT_ID` / `CD_GOOGLE_CLIENT_SECRET` (real)
- `CD_GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback`
- `CD_FRONTEND_ORIGIN=http://localhost:8000`
- If Plan 003 landed: `CD_SESSION_SECRET_KEY` set.
- A real test teacher account they control (with at least one Classroom course).

If `apps/api/.env` is not configured for `google` mode, the executor should write
the plan's files and the runbook, verify the **config loads** (Step 5 dry parts),
and STOP before the manual-auth step, reporting that real-mode env is required to
finish — do not invent credentials.

## Steps

### Step 1: Ensure Playwright is installed

If Plan 006 already added `@playwright/test`, skip the add. Otherwise from
`apps/web`: `pnpm add -D @playwright/test`. Then install browsers including the
real Chrome channel (Google is friendlier to a real-Chrome profile during the
manual login):
```
pnpm exec playwright install chromium
pnpm exec playwright install chrome
```

**Verify**: `pnpm exec playwright --version` → prints a version.

### Step 2: Document the prod-like backend launch

The smoke targets a single-origin prod-like build. The developer runs, from
`apps/api` (PowerShell), after `pnpm build` in `apps/web`:
```
$env:CD_GOOGLE_PROVIDER="google"
$env:CD_STATIC_DIR="../web/dist"
$env:CD_FRONTEND_ORIGIN="http://localhost:8000"
uv run python -m uvicorn classroom_downloader.main:app --app-dir src --port 8000
```
(Real client id/secret/redirect come from `apps/api/.env`.) Put this in
`docs/real-session-smoke.md`. The app is then at `http://localhost:8000`,
single-origin — the same shape as production, so the real cookie path is
exercised (no Vite dev proxy in front).

Do **not** start servers from `playwright.real.config.ts` automatically — real
mode needs the developer's env and a human login, so the runbook has them start
the backend manually. The config's `webServer` is omitted for the real suite.

**Verify**: with the backend running, `curl http://localhost:8000/api/health`
returns 200 and `curl http://localhost:8000/` returns the built `index.html`.

### Step 3: Real Playwright config

Create `apps/web/playwright.real.config.ts`:
```ts
import { defineConfig } from "@playwright/test";

const SESSION = ".auth/real-session.json";

export default defineConfig({
  testDir: "./e2e-real",
  // No webServer: the developer starts the prod-like backend manually (real env + login).
  use: {
    baseURL: "http://localhost:8000",
    channel: "chrome",
    trace: "off",        // privacy: no trace of real student data
    video: "off",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "setup", testMatch: /auth\.setup\.ts/ },
    {
      name: "real",
      testMatch: /core-flows\.spec\.ts/,
      dependencies: ["setup"],
      use: { storageState: SESSION },
    },
  ],
});
```
Add scripts to `package.json`:
```json
"e2e:real:auth": "playwright test --config playwright.real.config.ts --project setup --headed",
"e2e:real": "playwright test --config playwright.real.config.ts --project real"
```
(`e2e:real` runs `setup` first via the project dependency, then `real`; the
`--headed` auth-only script lets the developer log in interactively.)

**Verify**: `pnpm exec playwright test --config playwright.real.config.ts --list`
→ lists the setup + spec without a config error.

### Step 4: Manual auth setup that saves storageState

Create `apps/web/e2e-real/auth.setup.ts`. It opens the app headed, clicks
connect, then **waits for the human to complete Google login**, and on return
saves `storageState` (which captures the httponly `cd_session` cookie):
```ts
import { test as setup, expect } from "@playwright/test";

const SESSION = ".auth/real-session.json";

setup("manual google login → save session", async ({ page }) => {
  setup.setTimeout(180_000); // 3 min for a human to log in
  await page.goto("/");

  // If a previous session is still valid we may already be on workspace.
  const onWorkspace = await page
    .locator('[data-screen-label="workspace"]')
    .isVisible()
    .catch(() => false);

  if (!onWorkspace) {
    await page.getByText("Conectar conta Google escolar").click();
    // Human completes Google consent in the opened window. Wait until the app
    // redirects back and reaches the workspace.
    await expect(page.locator("[data-screen-label]").first())
      .toHaveAttribute("data-screen-label", "workspace", { timeout: 170_000 });
  }

  await expect(page.getByTitle("Sair da conta Google")).toBeVisible();
  await page.context().storageState({ path: SESSION });
});
```

**Manual run**: `pnpm e2e:real:auth` (headed). Complete the login by hand.

**Fallback if Google blocks the Playwright browser** ("this browser may not be
secure"): log in using your normal Chrome at `http://localhost:8000`, then export
the `cd_session` cookie and hand-write `.auth/real-session.json` in Playwright's
storageState shape:
```json
{ "cookies": [{ "name": "cd_session", "value": "<paste>", "domain": "localhost",
  "path": "/", "httpOnly": true, "secure": false, "sameSite": "Lax",
  "expires": -1 }], "origins": [] }
```
Document both paths in the runbook. STOP and report if neither yields a saved
session.

**Verify**: `.auth/real-session.json` exists and contains a `cd_session` cookie
entry. Confirm it is gitignored (`git status` does NOT list it).

### Step 5: Core-flow specs (logout LAST — it ends the session)

Create `apps/web/e2e-real/core-flows.spec.ts`. Order matters: read-only flows
first; logout last because it deletes the session and invalidates the saved
state. Use `test.describe.serial` so they run in order and stop on first failure.

```ts
import { test, expect } from "@playwright/test";

const screen = (page) => page.locator("[data-screen-label]").first();

test.describe.serial("real authenticated core flows", () => {
  test("boots into workspace with a real session", async ({ page }) => {
    await page.goto("/");
    await expect(screen(page)).toHaveAttribute("data-screen-label", "workspace", { timeout: 20_000 });
    await expect(page.getByTitle("Sair da conta Google")).toBeVisible();
  });

  test("navigates the rail with real data", async ({ page }) => {
    await page.goto("/");
    await expect(screen(page)).toHaveAttribute("data-screen-label", "workspace", { timeout: 20_000 });
    await page.getByRole("button", { name: /Corrigir com IA/ }).click();
    await expect(screen(page)).toHaveAttribute("data-screen-label", "graderQueue");
    await page.getByRole("button", { name: /Turmas/ }).click();
    await expect(screen(page)).toHaveAttribute("data-screen-label", "workspace");
  });

  // THE point of this suite: real logout must truly end the session.
  test("logout ends the session and survives a reload", async ({ page }) => {
    await page.goto("/");
    await expect(screen(page)).toHaveAttribute("data-screen-label", "workspace", { timeout: 20_000 });

    await page.getByTitle("Sair da conta Google").click();
    await expect(screen(page)).toHaveAttribute("data-screen-label", "connect", { timeout: 15_000 });
    await expect(page.getByTitle("Sair da conta Google")).toHaveCount(0);

    // Real-session-only assertion: reload must NOT restore the session.
    await page.reload();
    await expect(screen(page)).toHaveAttribute("data-screen-label", "connect", { timeout: 15_000 });
    await expect(page.getByText("Conectar conta Google escolar")).toBeVisible();
  });
});
```

Keep the suite read-only — do **not** add audit/draft/export steps. If you want a
grader-queue render check, assert `data-screen-label="graderQueue"` only (done in
the navigation test); do not open a job (that can trigger an audit).

**Verify** (requires the prod-like backend running and a fresh session from Step
4): `pnpm e2e:real` → all three tests pass. After this run the session is logged
out; re-run `pnpm e2e:real:auth` before the next smoke.

### Step 6: Runbook + ignores

Write `docs/real-session-smoke.md` covering: prerequisites (env, test account),
the two-terminal flow (build web → run prod-like backend → `pnpm e2e:real:auth`
→ `pnpm e2e:real`), the ~24h session / ~7-day consent re-auth note, the privacy
constraints, and that logout invalidates the saved session (re-auth each run).

Add to `apps/web/.gitignore`:
```
.auth/
playwright-report*/
test-results*/
```

**Verify**: `git status` shows the new source/config/doc files but NOT
`.auth/real-session.json` or any Playwright artifact. `pnpm build` still exits 0.

## Test plan

- `e2e-real/core-flows.spec.ts`: boot (real session), rail navigation (real
  data), and the headline logout-ends-session-and-survives-reload test, run
  serially with logout last.
- `e2e-real/auth.setup.ts`: one-time manual login that saves `storageState`.
- This is a **manual/on-demand** suite; there is no CI assertion. Its "passing
  state" is: a developer can run `pnpm e2e:real:auth` then `pnpm e2e:real` and
  see all three green against a real session.
- To prove the logout test has teeth, the developer can (locally, not committed)
  break the logout wiring and confirm the reload assertion fails.

## Done criteria

ALL must hold:

- [ ] `apps/web/playwright.real.config.ts` exists with a `setup` project and a
      `real` project that consumes `storageState`, no `webServer`, traces off
- [ ] `apps/web/e2e-real/auth.setup.ts` saves `storageState` after a manual login
- [ ] `apps/web/e2e-real/core-flows.spec.ts` exists with boot, navigation, and a
      logout test that asserts the post-reload screen is still `connect`
- [ ] `package.json` has `e2e:real` and `e2e:real:auth` scripts
- [ ] `.auth/` and Playwright artifacts are gitignored and NOT staged
- [ ] `docs/real-session-smoke.md` runbook exists
- [ ] No CI file changed; no production source changed; `pnpm build` exits 0
- [ ] (If real env is available) `pnpm e2e:real:auth` then `pnpm e2e:real` pass
      against a real session; otherwise the executor reports that real-mode env
      is required to execute the live run, with everything else in place
- [ ] `plans/README.md` status row for 007 updated

## STOP conditions

Stop and report back (do not improvise) if:

- `apps/api/.env` is not configured for `google` mode — write the files + runbook,
  verify config loads, and stop before the live run (do not fabricate credentials).
- Google blocks both the Playwright-driven login AND the manual cookie-import
  fallback — report; without a captured session the suite cannot run.
- A flow would require triggering an audit/draft/export or adding a `data-testid`
  to production source — both are out of scope; report instead.
- The prod-like backend won't serve the built frontend (`CD_STATIC_DIR` not
  picked up) — confirm `main.py` static serving against the "Current state" note
  before changing anything.
- You find yourself about to commit `.auth/real-session.json` or an artifact
  containing student data — STOP; fix `.gitignore` first.

## Maintenance notes

- **Re-auth cadence**: the saved session expires in ~24h (app session) and the
  Google consent in ~7 days (Testing mode). When `pnpm e2e:real` fails at the
  boot step, re-run `pnpm e2e:real:auth`. Logout (the last test) also
  invalidates the session each run by design — re-auth before each smoke.
- **Known limitation**: locally over http, the cookie's `secure` flag is false,
  so the `secure=true` HTTPS cookie behavior in production is NOT reproduced
  here. If a future logout/cookie bug is suspected to be HTTPS-specific, the only
  faithful repro is pointing this suite at live production (the "against live
  production" option, deliberately out of this local plan) or serving locally
  over HTTPS — note this when triaging.
- Keep this suite read-only and out of CI. If someone proposes wiring it into CI
  with stored credentials, push back: Google blocks automated consent and CI
  secrets would expose real student data — that is the reason this plan is
  local-only.
- A reviewer should confirm: no artifact or session file is committed; traces are
  off; the logout test includes the post-reload assertion (the real-session
  differentiator).
