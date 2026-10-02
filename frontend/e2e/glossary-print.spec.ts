import { expect, test } from "@playwright/test";

test("result labels lead to plain definitions, and every term links to its formulas", async ({ page }) => {
  await page.goto("/app/optimise");
  await page.getByRole("button", { name: "Optimise" }).click();
  await page.getByRole("link", { name: "Sharpe ratio", exact: true }).first().click();
  await expect(page).toHaveURL(/\/glossary#sharpe-ratio$/);
  await expect(page.getByRole("heading", { name: "What the terms mean", level: 1 })).toBeVisible();
  const entry = page.locator("#sharpe-ratio");
  await expect(entry).toContainText("Return above the risk-free rate per unit of volatility");
  await entry.getByRole("link", { name: /Formulas:/ }).click();
  await expect(page).toHaveURL(/\/research\/returns-and-risk$/);
});

test("printing a result keeps the results and leaves out menus and settings", async ({ page }) => {
  await page.goto("/app/optimise");
  await page.getByRole("button", { name: "Optimise" }).click();
  await expect(page.getByText("Why each asset is (or is not) held")).toBeVisible();
  await page.emulateMedia({ media: "print" });
  await expect(page.getByText("Why each asset is (or is not) held")).toBeVisible();
  await expect(page.getByText("Best expected risk-adjusted return")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Workspace steps" }).first()).toBeHidden();
  await expect(page.getByRole("button", { name: "Optimise" })).toBeHidden();
  await expect(page.getByLabel("Max weight")).toBeHidden();
  await expect(page.getByRole("contentinfo")).toBeHidden(); // site footer
});
