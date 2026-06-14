import { expect, test } from "@playwright/test";

const screen = (page: import("@playwright/test").Page) =>
  page.locator("[data-screen-label]").first();

test("rail navigates between core views", async ({ page }) => {
  await page.goto("/");
  await expect(screen(page)).toHaveAttribute("data-screen-label", "workspace", { timeout: 15_000 });

  await page.getByRole("button", { name: /Corrigir com IA/ }).click();
  await expect(screen(page)).toHaveAttribute("data-screen-label", "graderQueue");

  await page.getByRole("button", { name: /Histórico/ }).click();
  await expect(screen(page)).toHaveAttribute("data-screen-label", "history");

  await page.getByRole("button", { name: /Turmas/ }).click();
  await expect(screen(page)).toHaveAttribute("data-screen-label", "workspace");
});
