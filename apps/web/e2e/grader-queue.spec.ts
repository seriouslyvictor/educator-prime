import { expect, test } from "@playwright/test";

test("grader queue screen renders", async ({ page }) => {
  await page.goto("/");
  // Wait for the app to finish bootstrapping in mock mode before interacting.
  await expect(page.locator("[data-screen-label]").first())
    .toHaveAttribute("data-screen-label", "workspace", { timeout: 15_000 });
  await page.getByRole("button", { name: /Corrigir com IA/ }).click();
  await expect(page.locator("[data-screen-label]").first())
    .toHaveAttribute("data-screen-label", "graderQueue", { timeout: 10_000 });
  // The grader queue container is present (its own design label) — proves the
  // view mounted rather than throwing.
  await expect(page.locator('[data-screen-label="01 Grader - Queue"]')).toBeVisible();
});
