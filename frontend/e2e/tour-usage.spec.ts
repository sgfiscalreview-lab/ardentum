import { expect, test } from "@playwright/test";

test("the guided tour walks through the workspace without signing in", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Take the guided tour" }).click();
  await expect(page.getByRole("heading", { name: "Ardentum in eight steps", level: 1 })).toBeVisible();
  await page.getByRole("link", { name: "Start the tour" }).click();

  const bar = page.getByRole("complementary", { name: "Guided tour" });
  await expect(page).toHaveURL(/\/app\?tour=1$/);
  await expect(bar).toContainText("Guided tour, step 1 of 8: Choose the data");
  await expect(bar.getByRole("link", { name: "Previous step" })).toHaveCount(0);

  await bar.getByRole("link", { name: "Next step: Look at the history" }).click();
  await expect(page).toHaveURL(/\/app\/analytics\?tour=2$/);
  await expect(bar).toContainText("step 2 of 8");
  await expect(page.getByRole("heading", { name: "Historical analytics", level: 1 })).toBeVisible();

  // The last step points to the methodology; closing removes the bar.
  await page.goto("/app/compare?tour=8");
  await expect(bar.getByRole("link", { name: "Finish: read the methodology" })).toBeVisible();
  await bar.getByRole("link", { name: "Close the tour" }).click();
  await expect(page).toHaveURL(/\/app\/compare$/);
  await expect(bar).toHaveCount(0);

  // A step number that does not belong to the page shows nothing.
  await page.goto("/app/compare?tour=2");
  await expect(page.getByRole("heading", { name: "Compare portfolios", level: 1 })).toBeVisible();
  await expect(bar).toHaveCount(0);
});

test("the usage page shows anonymous counts, including a calculation just run", async ({ page }) => {
  await page.goto("/usage");
  await expect(page.getByRole("heading", { name: "How much Ardentum is used", level: 1 })).toBeVisible();
  const optimisations = page.getByRole("row").filter({ hasText: "Optimisations" });
  await expect(optimisations).toBeVisible();
  const before = Number((await optimisations.getByRole("cell").nth(2).innerText()).replace(/,/g, ""));

  await page.goto("/app/optimise");
  await page.getByRole("button", { name: "Optimise", exact: true }).click();
  await expect(page.getByText("Best expected risk-adjusted return")).toBeVisible();

  await page.goto("/usage");
  await expect
    .poll(async () => Number((await page.getByRole("row").filter({ hasText: "Optimisations" }).getByRole("cell").nth(2).innerText()).replace(/,/g, "")))
    .toBeGreaterThan(before); // other tests may run calculations at the same time
  await page.getByRole("navigation", { name: "Footer" }).getByRole("link", { name: "Usage" }).click();
  await expect(page).toHaveURL(/\/usage$/);
});
