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
  // The rail must be absent — connect screen is a standalone full-bleed layout.
  await expect(page.locator("aside.rail")).toHaveCount(0);
  // The OAuth connect button is present (standalone login screen).
  await expect(
    page.getByRole("button", { name: /Continuar com o Google Sala de Aula/ }),
  ).toBeVisible();
});
