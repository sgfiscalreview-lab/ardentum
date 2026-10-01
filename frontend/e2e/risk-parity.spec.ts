import { expect, test } from "@playwright/test";

test("risk parity names the limit it breaks, then gives every holding the same share of risk", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => window.localStorage.clear());
  await page.goto("/app/optimise");
  await page.getByLabel("Objective", { exact: true }).selectOption("risk_parity");
  await expect(page.getByText("Every holding contributes the same share of risk. Uses no expected returns.")).toBeVisible();

  // The default 30% cap is too tight for the low-risk bond fund: said plainly, not approximated.
  await page.getByRole("button", { name: "Optimise" }).click();
  await expect(page.getByText(/GOVB\.SYN gets \d+\.\d%, above its maximum of 30\.0%/)).toBeVisible();

  await page.getByLabel("Max weight").fill("100");
  await page.getByRole("button", { name: "Optimise" }).click();
  await expect(page.getByText(/Every holding contributes the same share of risk \(7\.1% each\)/)).toBeVisible();
  await expect(page.getByText(/contributes 7\.1% of portfolio risk, the same share as every other holding/).first()).toBeVisible();
});
