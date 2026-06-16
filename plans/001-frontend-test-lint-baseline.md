# Plan 001: Establish a frontend test runner and linter with CI enforcement

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat b61ac5a..HEAD -- apps/web/package.json apps/web/vite.config.ts apps/web/tsconfig.json .github/workflows/ci.yml`
> If any of those files changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: tests / dx
- **Planned at**: commit `b61ac5a`, 2026-06-13

## Why this matters

The `apps/web` frontend has **zero automated tests and no linter**. CI
(`.github/workflows/ci.yml`) runs only `pnpm build` for the web app, which
typechecks but verifies no behavior. Meanwhile the most complex code in the repo
lives here: a stale-while-revalidate cache layer (`src/lib/api.ts`), folder
export over the File System Access API (`src/lib/folder-export.ts`), and a
1380-line `App.tsx`. Any regression in these ships undetected.

This plan installs the verification baseline — **Vitest** (the Vite-native test
runner) and **ESLint** (flat config) — wires them into npm scripts and CI, and
adds a single smoke test so the harness is provably working. It writes *no
meaningful behavioral tests* — that is Plan 002, which depends on this one. Keep
this plan small: its job is the harness, not coverage.

## Current state

- `apps/web/package.json` — only `dev`, `build`, `preview` scripts; devDeps are
  `@types/react`, `@types/react-dom`, `typescript`. No test or lint tooling.
  Package manager is `pnpm@10.28.1`, `"type": "module"`.
- `apps/web/vite.config.ts` — Vite 6 config with `@vitejs/plugin-react`,
  `@tailwindcss/vite`, a `__APP_VERSION__` define, and `@` → `./src` alias.
  Vitest reads this file, so the alias and define carry over automatically.
- `apps/web/tsconfig.json` — `strict: true`, `moduleResolution: "Node"`,
  `jsx: "react-jsx"`, path alias `@/*` → `./src/*`.
- `.github/workflows/ci.yml` — has two jobs: `api-tests` (uv + pytest) and
  `web-build`. The `web-build` job ends with:
  ```yaml
      - name: Install dependencies
        run: pnpm install --frozen-lockfile

      - name: Type-check and build
        run: pnpm build
  ```
- There is no ESLint config anywhere (`apps/web/.eslintrc*`, `eslint.config.*`
  all absent).

Repo conventions to match:
- Portuguese (pt-BR) user-facing strings; English code/comments. Tests are
  internal, so write test names in English.
- The web app uses ES modules and modern TS. Use `.ts`/`.tsx` test files.
- Backend test files live next to a `tests/` dir; for the frontend, colocate
  test files next to the source as `*.test.ts` (Vitest default glob).

## Commands you will need

| Purpose          | Command (run from `apps/web`)        | Expected on success           |
|------------------|--------------------------------------|-------------------------------|
| Install          | `pnpm install`                       | exit 0                        |
| Add dev dep      | `pnpm add -D <pkg>`                   | exit 0, updates package.json  |
| Run tests        | `pnpm test`                          | exit 0, all tests pass        |
| Run tests (CI)   | `pnpm test -- --run`                 | exit 0, no watch              |
| Lint             | `pnpm lint`                          | exit 0, no errors             |
| Typecheck+build  | `pnpm build`                         | exit 0 (must still pass)      |

All web commands run from the `apps/web` directory.

## Suggested executor toolkit

- If a `vercel-react-best-practices` or `web-design-guidelines` skill is
  available, you do **not** need it for this plan — it is pure tooling setup.
- Reference: Vitest config docs (https://vitest.dev/config/) and the
  typescript-eslint flat-config quickstart
  (https://typescript-eslint.io/getting-started/) if a version detail drifts.

## Scope

**In scope** (the only files you should create or modify):
- `apps/web/package.json` (add scripts + devDeps)
- `apps/web/vitest.config.ts` (create) — or `vitest.setup.ts` if needed
- `apps/web/eslint.config.js` (create — flat config)
- `apps/web/src/lib/utils.test.ts` (create — the single smoke test)
- `.github/workflows/ci.yml` (add lint + test steps to the `web-build` job)
- `apps/web/pnpm-lock.yaml` (will change automatically from `pnpm add`)

**Out of scope** (do NOT touch):
- Any existing `src/**` source file except creating the one smoke test. Do not
  "fix" lint errors in existing files in this plan — see Step 5.
- The backend (`apps/api/**`) and its CI job.
- `apps/web/components.json` (shadcn config — unrelated).

## Git workflow

- Branch: `advisor/001-frontend-test-lint-baseline`
- Commit style: conventional commits (repo uses them — recent log shows
  `feat:`, `fix:`). Example from history: `fix: PiP selector collisions`.
  Suggested: `chore(web): add vitest + eslint baseline and wire into CI`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Add Vitest and run-time test deps

From `apps/web`, install Vitest and a DOM environment (folder-export and the
PiP code touch `window`, so a DOM env is required):

```
pnpm add -D vitest@^3 jsdom@^25 @vitest/coverage-v8@^3
```

**Verify**: `cat package.json` shows the three packages under `devDependencies`,
and `pnpm vitest --version` prints a 3.x version → exit 0.

### Step 2: Create `apps/web/vitest.config.ts`

Vitest merges with `vite.config.ts` automatically for the `@` alias and the
`__APP_VERSION__` define, but create an explicit config so the environment and
globs are pinned:

```ts
import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: "jsdom",
      globals: true,
      include: ["src/**/*.test.{ts,tsx}"],
      coverage: {
        provider: "v8",
        include: ["src/lib/**", "src/components/grader/**"],
      },
    },
  }),
);
```

If `mergeConfig` errors because `vite.config.ts` exports a function rather than a
config object, STOP and report (the current file exports a plain
`defineConfig({...})` object, so this should work).

**Verify**: file exists; `pnpm vitest --run` exits 0 with "No test files found"
or runs zero tests (no config error). A config *error* is a STOP condition.

### Step 3: Add the smoke test

`src/lib/utils.ts` exists in the repo (a shadcn-style `cn` helper). Read it
first to confirm its exports, then create `src/lib/utils.test.ts` exercising one
real export. Example shape (adjust to the actual export name you find):

```ts
import { describe, expect, it } from "vitest";
import { cn } from "./utils";

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("a", "b")).toContain("a");
    expect(cn("a", false && "b", "c")).not.toContain("false");
  });
});
```

If `src/lib/utils.ts` does not export `cn` (or anything testable), instead write
the smoke test against `src/lib/api.ts`'s `apiErrorFromUnknown` export, which is
pure:
```ts
import { describe, expect, it } from "vitest";
import { apiErrorFromUnknown, ApiError } from "./api";

describe("apiErrorFromUnknown", () => {
  it("passes ApiError through unchanged", () => {
    const original = new ApiError(404, "x", "msg");
    expect(apiErrorFromUnknown(original, "fallback")).toBe(original);
  });
  it("wraps a plain Error", () => {
    const wrapped = apiErrorFromUnknown(new Error("boom"), "fallback");
    expect(wrapped).toBeInstanceOf(ApiError);
    expect(wrapped.message).toBe("boom");
  });
});
```

**Verify**: `pnpm vitest --run` → exit 0, reports the new test(s) passing.

### Step 4: Add ESLint flat config and deps

Install ESLint with the TypeScript and React-hooks plugins:

```
pnpm add -D eslint@^9 typescript-eslint@^8 eslint-plugin-react-hooks@^5 eslint-plugin-react-refresh@^0.4 globals@^15
```

Create `apps/web/eslint.config.js`:

```js
import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";

export default tseslint.config(
  { ignores: ["dist", "node_modules", "**/*.config.{js,ts}"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: { ...globals.browser, __APP_VERSION__: "readonly" },
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
    },
  },
);
```

If `pnpm add` pulls a `typescript-eslint` major that requires a different config
entry shape, follow the version's quickstart rather than forcing the above.

**Verify**: `pnpm exec eslint src --max-warnings=9999` runs to completion (exit
0 or non-zero from findings, but **not** a config-load crash). A crash is a STOP
condition.

### Step 5: Add npm scripts; do NOT fail the build on pre-existing lint debt

The existing source has never been linted, so it will have warnings/errors.
This plan must not turn those into a red CI. Add scripts to `package.json`:

```json
"scripts": {
  "dev": "vite --host 127.0.0.1",
  "build": "tsc -b && vite build",
  "preview": "vite preview --host 127.0.0.1",
  "test": "vitest",
  "test:run": "vitest --run",
  "lint": "eslint src"
}
```

Then run `pnpm lint` once and **record the error count** in your report. Do not
fix those errors here (out of scope). In Step 6 the CI lint step runs in a
non-blocking mode so the baseline lands without a cleanup project.

**Verify**: `pnpm test:run` → exit 0. `pnpm build` → exit 0 (unchanged).

### Step 6: Wire test + lint into CI

Edit the `web-build` job in `.github/workflows/ci.yml`. After the existing
"Type-check and build" step, append:

```yaml
      - name: Test
        run: pnpm test:run

      - name: Lint (non-blocking until baseline is clean)
        run: pnpm lint || true
```

Rationale for `|| true`: existing files were never linted; making lint
blocking now would red-line CI on legacy debt. The step still surfaces findings
in the log. A follow-up (deferred, see Maintenance notes) removes `|| true`
once the existing warnings are cleared.

**Verify**: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"`
from the repo root → exit 0 (valid YAML). If `python`/PyYAML is unavailable, run
`pnpm dlx js-yaml .github/workflows/ci.yml` instead, or visually confirm
indentation matches the surrounding steps (6-space indent under `steps:`).

## Test plan

- One smoke test file (`src/lib/utils.test.ts`) proving the runner executes and
  asserts. No behavioral coverage of app logic in this plan.
- Structural pattern for future tests: the smoke test itself, plus Plan 002.
- Verification: `pnpm test:run` → all pass, including the new smoke test.

## Done criteria

Machine-checkable. ALL must hold (run from `apps/web` unless noted):

- [ ] `pnpm install` exits 0
- [ ] `pnpm test:run` exits 0 and reports ≥1 passing test
- [ ] `pnpm lint` runs without a config-load crash (non-zero from findings is OK)
- [ ] `pnpm build` still exits 0
- [ ] `package.json` has `test`, `test:run`, and `lint` scripts
- [ ] `vitest.config.ts` and `eslint.config.js` exist in `apps/web/`
- [ ] `.github/workflows/ci.yml` `web-build` job has a `Test` step running
      `pnpm test:run` and a lint step; the file is valid YAML
- [ ] No `src/**` file modified except the new `*.test.ts` (`git status`)
- [ ] `plans/README.md` status row for 001 updated

## STOP conditions

Stop and report back (do not improvise) if:

- `vitest.config.ts`'s `mergeConfig` against `vite.config.ts` throws (the Vite
  config shape drifted).
- ESLint or Vitest fails to *load its config* (as opposed to reporting findings
  or test failures).
- `pnpm build` starts failing after your changes — your tooling additions must
  not affect the production build.
- The pinned major versions above are unavailable on the registry and the
  current major needs a materially different config; report the versions you see
  rather than guessing a config.

## Maintenance notes

- **Follow-up explicitly deferred**: clear the existing ESLint warnings, then
  remove `|| true` from the CI lint step so lint becomes blocking. That cleanup
  is intentionally out of this plan to keep the baseline landing small.
- When Plan 002 lands real tests, coverage `include` globs in
  `vitest.config.ts` may need widening.
- A reviewer should confirm the CI `Test` step actually fails the job when a
  test fails (the lint step is intentionally non-blocking; the test step is not).
