# Plan 006: Playwright E2E coverage for core user flows (incl. logout)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat b61ac5a..HEAD -- apps/web/src/App.tsx apps/web/src/components/Rail.tsx apps/web/src/components/ConnectView.tsx`
> If any changed since this plan was written, re-confirm the selectors in
> "Current state" against the live code before proceeding; on a mismatch, treat
> it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none. **Recommended before** plans/005-decompose-app-tsx.md —
  this suite is the automated regression net for that refactor (it replaces 005's
  manual smoke checklist).
- **Category**: tests
- **Planned at**: commit `b61ac5a`, 2026-06-13

## Why this matters

A core flow — **logout** — silently broke during a live demo. That class of
"silly" regression (a button that does nothing, a view that fails to transition,
a white screen on boot) is invisible to unit tests and to `pnpm build`, but a
browser-level E2E test catches it every run. The app has no E2E coverage today.

This plan adds **Playwright** with a small suite covering the core navigable
flows in **mock mode** (the backend's default — no real Google OAuth needed):
boot/bootstrap, logout, Rail navigation, and the grader queue. The logout test
specifically asserts the full user-visible outcome (UI returns to the connect
screen and the logout control disappears), so a future logout regression fails
CI instead of a demo.

Folder export is deliberately **out of scope**: it uses
`window.showDirectoryPicker`, which cannot be driven by headless Playwright (no
fake directory-picker API). Export stays covered by the Plan 002 unit tests.

## Current state

- **Run model**: the README documents two dev servers. Backend (FastAPI) on
  `:8000`, frontend (Vite) on `:5173`; Vite proxies `/api/*` → `127.0.0.1:8000`
  (`apps/web/vite.config.ts`). The backend defaults to
  `CD_GOOGLE_PROVIDER=mock` (`apps/api/src/classroom_downloader/settings.py:36`),
  which serves fake Classroom/Drive data and an always-signed-in profile — so the
  full product workflow runs with no credentials.
- **Health endpoint**: `GET /api/health` (`routers/health.py:6`) — use as the
  backend readiness URL for Playwright's `webServer`.
- **Boot behavior (mock)**: `auth_me` in mock returns `signed_in=True` with
  classroom + drive scopes (`routers/auth.py:45-59`), so on load `App.bootstrap`
  resolves `connected = true` and the app lands on the **workspace** view, not
  the connect screen.
- **Testability seams (use these as selectors — verified):**
  - The app shell sets `data-screen-label={view}` (`App.tsx:1149`). Its value is
    the current `AppView`: `connect`, `workspace`, `admin`, `progress`, `done`,
    `history`, `graderQueue`, `graderSetup`, `graderReview`, `graderWrap`. This
    is the primary assertion hook for "which screen am I on".
  - **Logout button** (`Rail.tsx:95-99`): rendered only when `auth?.signed_in`;
    `<button class="logout-btn" title="Sair da conta Google">`. Select via
    `page.getByTitle("Sair da conta Google")`.
  - **Rail nav buttons** (`Rail.tsx:49-72`), by visible text:
    `Corrigir com IA` → `graderQueue`, `Turmas` → `workspace`,
    `Histórico` → `history`. (`Corrigir com IA` and `Histórico` are `disabled`
    until connected; in mock the user is connected, so they're enabled.)
  - **Connect button** (`ConnectView.tsx:47-50`): text
    `Conectar conta Google escolar`.
  - The grader queue page also sets a nested `data-screen-label="01 Grader -
    Queue"` on its own container (`GraderQueue.tsx:71`) — do not rely on it;
    assert the shell's `data-screen-label="graderQueue"` instead (the nested one
    is a design label, not the view state).
- No Playwright config or `e2e/` directory exists yet (confirmed).

Conventions to match:
- Frontend tooling is pnpm (`pnpm@10.28.1`), ES modules, TypeScript strict.
- The app binds to `127.0.0.1` (not `localhost`) — Vite `--host 127.0.0.1`. Use
  `http://127.0.0.1:5173` as the Playwright `baseURL`.
- pt-BR UI text; assert against the real Portuguese strings shown above.

## Commands you will need

| Purpose            | Command (from `apps/web`)                         | Expected            |
|--------------------|---------------------------------------------------|---------------------|
| Add dep            | `pnpm add -D @playwright/test`                     | exit 0              |
| Install browser    | `pnpm exec playwright install chromium`            | downloads Chromium  |
| Run E2E            | `pnpm e2e`                                          | all specs pass      |
| Run headed (debug) | `pnpm exec playwright test --headed`               | browser visible     |
| Show report        | `pnpm exec playwright show-report`                 | opens HTML report   |
| Backend (manual)   | from `apps/api`: `uv run --extra dev python -m uvicorn classroom_downloader.main:app --app-dir src --port 8000` | serves on :8000 |

## Suggested executor toolkit

- If a `webapp-testing` or `verify` skill is available, use it to sanity-check
  selectors interactively before committing specs — but the specs themselves
  must be committed Playwright files, not ad-hoc skill runs.
- Reference: Playwright `webServer` docs
  (https://playwright.dev/docs/test-webserver) for the multi-server setup.

## Scope

**In scope** (create):
- `apps/web/playwright.config.ts`
- `apps/web/e2e/boot.spec.ts`
- `apps/web/e2e/logout.spec.ts`
- `apps/web/e2e/navigation.spec.ts`
- `apps/web/e2e/grader-queue.spec.ts`
- `apps/web/package.json` (add `e2e` script + dev dep)
- `.github/workflows/ci.yml` (add a `web-e2e` job)
- `apps/web/.gitignore` (or root) — ignore `playwright-report/`, `test-results/`

**Out of scope** (do NOT touch):
- Folder export flow (not automatable headlessly — see Why this matters).
- The real `google` provider path / actual OAuth (E2E runs in mock mode only).
- Any production source file. If a flow is untestable without adding a
  `data-testid`, prefer the existing text/`data-screen-label` seams; only add a
  `data-testid` if there is genuinely no stable selector, and if so, STOP and
  report which element needs it before editing source.
- The Vitest config from Plan 001 (Playwright is independent; keep its specs out
  of the Vitest `include` glob — `e2e/**` is already excluded by Vitest's
  `src/**/*.test.ts` pattern).

## Git workflow

- Branch: `advisor/006-playwright-e2e-core-flows`
- Commit style: conventional commits, e.g.
  `test(web): add Playwright e2e for core flows (boot, logout, nav, queue)`.
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Install Playwright and add the script

From `apps/web`:
```
pnpm add -D @playwright/test
pnpm exec playwright install chromium
```
Add to `package.json` scripts: `"e2e": "playwright test"`.

**Verify**: `pnpm exec playwright --version` prints a version → exit 0.

### Step 2: Configure Playwright with both servers

Create `apps/web/playwright.config.ts`. It must start the backend (mock mode,
isolated DB) and the Vite dev server, then run specs against the frontend.

```ts
import { defineConfig } from "@playwright/test";
import path from "node:path";

const API_DIR = path.resolve(__dirname, "../api");

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "html",
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "on-first-retry",
  },
  webServer: [
    {
      // Backend in mock mode with a disposable DB so runs are deterministic.
      command:
        "uv run --extra dev python -m uvicorn classroom_downloader.main:app --app-dir src --port 8000",
      cwd: API_DIR,
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        CD_GOOGLE_PROVIDER: "mock",
        CD_GRADING_ENGINE: "mock",
        CD_DATABASE_URL: "sqlite:///./e2e.db",
        CD_LOG_LEVEL: "WARNING",
      },
    },
    {
      command: "pnpm dev",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
```

If `uv` is not on PATH in the executor's shell, STOP and report (the backend
cannot start). If the backend health URL never becomes ready, confirm the path
is `/api/health` against `routers/health.py` before changing anything.

**Verify**: `pnpm exec playwright test --list` runs without a config error
(it may list zero tests until Step 3). A config/load error is a STOP condition.

### Step 3: Boot test — the app loads and reaches the workspace

`e2e/boot.spec.ts`:
```ts
import { expect, test } from "@playwright/test";

test("boots into the workspace in mock mode", async ({ page }) => {
  await page.goto("/");
  // Shell reflects the active view via data-screen-label.
  await expect(page.locator("[data-screen-label]").first())
    .toHaveAttribute("data-screen-label", "workspace", { timeout: 15_000 });
  // The signed-in Rail shows the logout control.
  await expect(page.getByTitle("Sair da conta Google")).toBeVisible();
});
```

**Verify**: `pnpm e2e` runs this spec green (Playwright starts both servers).

### Step 4: Logout test — the regression this plan exists for

`e2e/logout.spec.ts`:
```ts
import { expect, test } from "@playwright/test";

test("logout returns to the connect screen and hides the logout control", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("[data-screen-label]").first())
    .toHaveAttribute("data-screen-label", "workspace", { timeout: 15_000 });

  await page.getByTitle("Sair da conta Google").click();

  // The whole point: logout must visibly land the user on the connect screen...
  await expect(page.locator("[data-screen-label]").first())
    .toHaveAttribute("data-screen-label", "connect", { timeout: 10_000 });
  // ...and the logout control must be gone (auth.signed_in is now false).
  await expect(page.getByTitle("Sair da conta Google")).toHaveCount(0);
  // The connect CTA is present.
  await expect(page.getByText("Conectar conta Google escolar")).toBeVisible();
});
```

**Verify**: `pnpm exec playwright test e2e/logout.spec.ts` → passes. To prove the
test has teeth, temporarily break logout locally (e.g. comment out the
`onClick={onLogout}` wiring in `Rail.tsx`), confirm the test FAILS, then revert.
Do **not** commit the break.

### Step 5: Navigation test — Rail routing works

`e2e/navigation.spec.ts`: from the workspace, click each enabled Rail item and
assert the shell `data-screen-label` changes accordingly.
```ts
import { expect, test } from "@playwright/test";

const screen = (page) => page.locator("[data-screen-label]").first();

test("rail navigates between core views", async ({ page }) => {
  await page.goto("/");
  await expect(screen(page)).toHaveAttribute("data-screen-label", "workspace", { timeout: 15_000 });

  await page.getByRole("button", { name: "Corrigir com IA" }).click();
  await expect(screen(page)).toHaveAttribute("data-screen-label", "graderQueue");

  await page.getByRole("button", { name: "Histórico" }).click();
  await expect(screen(page)).toHaveAttribute("data-screen-label", "history");

  await page.getByRole("button", { name: "Turmas" }).click();
  await expect(screen(page)).toHaveAttribute("data-screen-label", "workspace");
});
```
If a button name match is ambiguous (the nav labels include counts/icons), use
`getByRole("button", { name: /Histórico/ })` with a regex, or scope to the Rail
`<aside>`. Adjust to whatever selector resolves uniquely — do not change source.

**Verify**: `pnpm exec playwright test e2e/navigation.spec.ts` → passes.

### Step 6: Grader queue test — the queue screen renders

`e2e/grader-queue.spec.ts`: navigate to the grader queue and assert it renders
without crashing. Mock mode serves data, but to stay robust to the exact mock
fixtures, assert on the screen state plus that *either* a queue row *or* the
empty-state is visible (not a blank/error screen).
```ts
import { expect, test } from "@playwright/test";

test("grader queue screen renders", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Corrigir com IA" }).click();
  await expect(page.locator("[data-screen-label]").first())
    .toHaveAttribute("data-screen-label", "graderQueue", { timeout: 15_000 });
  // The grader queue container is present (its own design label) — proves the
  // view mounted rather than throwing.
  await expect(page.locator('[data-screen-label="01 Grader - Queue"]')).toBeVisible();
});
```
Read `GraderQueue.tsx` first to confirm a stable element to assert on; if the
nested design label proves unreliable, assert on a heading/text the queue always
renders. STOP rather than adding a `data-testid` to source without reporting.

**Verify**: `pnpm exec playwright test e2e/grader-queue.spec.ts` → passes.

### Step 7: Ignore artifacts and wire CI

Add to `apps/web/.gitignore` (create if absent):
```
playwright-report/
test-results/
e2e.db
e2e.db-journal
```

Add a `web-e2e` job to `.github/workflows/ci.yml` (mirror the existing
`web-build` job's setup steps for pnpm + Node, and add uv for the backend, as in
the `api-tests` job):
```yaml
  web-e2e:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/web
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          python-version: "3.14"
          enable-cache: true
          cache-dependency-glob: apps/api/uv.lock
      - uses: pnpm/action-setup@v4
        with:
          package_json_file: apps/web/package.json
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: pnpm
          cache-dependency-path: apps/web/pnpm-lock.yaml
      - run: pnpm install --frozen-lockfile
      - name: Sync backend deps
        working-directory: apps/api
        run: uv sync --extra dev
      - name: Install Playwright browser
        run: pnpm exec playwright install --with-deps chromium
      - name: Run E2E
        run: pnpm e2e
```

**Verify**: valid YAML —
`python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
(from repo root) → exit 0. Confirm the new job's `uv sync` runs in `apps/api`
(the Playwright `webServer` launches the backend from there via `cwd`).

### Step 8: Full suite

**Verify**: from `apps/web`, `pnpm e2e` → all four specs pass. `pnpm build`
still exits 0 (Playwright additions must not affect the production build).

## Test plan

- Four specs: boot, logout, navigation, grader-queue — all mock mode, all
  asserting on `data-screen-label` and stable text/title selectors.
- The logout spec is the headline regression guard; Step 4 includes a
  deliberate break-then-revert to prove it fails when logout is broken.
- Pattern for future specs: these four files. Keep specs behavior-level and
  selector-stable so the Plan 005 refactor does not churn them.
- Verification: `pnpm e2e` → all pass locally; the `web-e2e` CI job is green.

## Done criteria

Machine-checkable. ALL must hold (from `apps/web` unless noted):

- [ ] `pnpm e2e` exits 0 with four passing specs
- [ ] `playwright.config.ts` exists and starts both the mock backend and Vite
- [ ] `e2e/logout.spec.ts` asserts the post-logout screen is `connect` AND the
      logout control is gone
- [ ] `e2e/boot.spec.ts`, `e2e/navigation.spec.ts`, `e2e/grader-queue.spec.ts`
      exist and pass
- [ ] `.github/workflows/ci.yml` has a `web-e2e` job; the file is valid YAML
- [ ] `pnpm build` still exits 0
- [ ] No production source modified (`git status` shows only new e2e/config/CI
      files and `package.json`/`.gitignore`)
- [ ] `plans/README.md` status row for 006 updated

## STOP conditions

Stop and report back (do not improvise) if:

- `uv` or the backend health URL (`/api/health`) does not come up under
  Playwright's `webServer` — the run model is broken; report rather than
  hard-coding waits.
- A core flow genuinely cannot be asserted with existing selectors and would
  require adding a `data-testid` to source — report which element, do not edit
  source unilaterally (source changes are out of scope here).
- The mock backend serves an empty grader queue AND no empty-state element is
  reliably assertable — report; the queue spec may need a different anchor.
- Boot does not land on `workspace` (e.g. mock `auth_me` behavior changed) — that
  is itself a finding; report it.

## Maintenance notes

- These specs are the **automated smoke net for Plan 005** (App.tsx
  decomposition). Run them throughout that refactor; they should stay green
  without edits because they assert behavior via stable seams, not structure.
- Keep specs in mock mode. Do not point E2E at the real `google` provider —
  that path needs live OAuth and is non-deterministic.
- If a future change renames a view in `AppView` or a Rail label, the
  corresponding `data-screen-label` / text assertion must be updated — treat that
  as an intentional contract change, surfaced by a failing spec.
- A reviewer should confirm the logout spec actually fails when logout is broken
  (the Step 4 break-then-revert demonstrates this) — a smoke test that can't fail
  is worse than none.
