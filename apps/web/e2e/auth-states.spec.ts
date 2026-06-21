import { expect, type Page, test } from "@playwright/test";

// Frontend-rendering tests only. Live Google coverage stays in live-classroom.spec.ts.
async function stubAuth(page: Page, auth: Record<string, unknown>, courses: Array<Record<string, unknown>> = []) {
  await page.route("**/api/auth/me", (route) => route.fulfill({ json: auth }));
  await page.route("**/api/courses", (route) => route.fulfill({ json: courses }));
  await page.route("**/api/grading/jobs**", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/grading/health**", (route) => route.fulfill({ json: {
    engine: "mock", ready: true, status: "mock", model: null, provider: null,
    missing_keys: [], detail: "ok", probed: false, probe_ok: null,
  } }));
}

const signedOut = {
  signed_in: false, identity_scopes: false, classroom_scopes: false, drive_scopes: false,
  email: null, name: null, picture: null, provider: "google",
};

const signedIn = {
  signed_in: true, identity_scopes: true, classroom_scopes: true, drive_scopes: true,
  email: "teacher@example.com", name: "Teacher", picture: null, provider: "google",
};

test("renders signed-out Google-only login", async ({ page }) => {
  await stubAuth(page, signedOut);
  await page.goto("/");
  await expect(page.locator("[data-auth-stage]")).toHaveAttribute("data-auth-stage", "signin");
  await expect(page.getByRole("button", { name: "Continuar com o Google" })).toBeVisible();
});

test("renders Classroom permission stage", async ({ page }) => {
  await stubAuth(page, { ...signedIn, classroom_scopes: false, drive_scopes: false });
  await page.goto("/");
  await expect(page.locator("[data-auth-stage]")).toHaveAttribute("data-auth-stage", "grant-classroom");
  await expect(page.getByText("Permitir leitura do Classroom")).toBeVisible();
});

test("renders no-courses explainer", async ({ page }) => {
  await stubAuth(page, signedIn, []);
  await page.goto("/");
  await expect(page.locator("[data-auth-stage]")).toHaveAttribute("data-auth-stage", "no-courses");
  await expect(page.getByText("Nenhuma turma para corrigir")).toBeVisible();
});

test("renders callback denial and policy states", async ({ page }) => {
  await stubAuth(page, signedOut);
  await page.goto("/?google=error&reason=google_auth_denied");
  await expect(page.locator("[data-auth-stage]")).toHaveAttribute("data-auth-stage", "gate");
  await expect(page.getByText(/Google recusou/)).toBeVisible();

  await page.goto("/?google=error&reason=google_policy_blocked");
  await expect(page.locator("[data-auth-stage]")).toHaveAttribute("data-auth-stage", "policy-blocked");
  await expect(page.getByText(/bloqueou este app/)).toBeVisible();
});

test("renders expired session and offline gates", async ({ page }) => {
  await page.route("**/api/auth/me", (route) => route.fulfill({
    status: 401,
    json: { detail: { code: "google_session_expired", message: "Expired" } },
  }));
  await page.goto("/");
  await expect(page.locator("[data-auth-stage]")).toHaveAttribute("data-auth-stage", "gate");

  await page.unroute("**/api/auth/me");
  await page.route("**/api/auth/me", (route) => route.abort());
  await page.goto("/");
  await expect(page.locator("[data-auth-stage]")).toHaveAttribute("data-auth-stage", "gate");
});
