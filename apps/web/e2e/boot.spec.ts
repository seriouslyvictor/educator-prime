import { expect, test } from "@playwright/test";

test("boots into the workspace in mock mode", async ({ page }) => {
  await page.goto("/");
  // Shell reflects the active view via data-screen-label.
  await expect(page.locator("[data-screen-label]").first())
    .toHaveAttribute("data-screen-label", "workspace", { timeout: 15_000 });
  // The signed-in Rail shows the logout control.
  await expect(page.getByTitle("Sair da conta Google")).toBeVisible();
});
