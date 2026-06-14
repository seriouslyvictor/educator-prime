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
