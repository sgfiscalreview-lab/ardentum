import { expect, test, type Page } from "@playwright/test";

async function fresh(page: Page) {
  await page.goto("/");
  await page.evaluate(() => window.localStorage.clear());
}

test.beforeEach(async ({ page }) => {
  await fresh(page);
});

test("landing page leads to the workspace with synthetic data clearly labelled", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Portfolio analysis that shows its working." })).toBeVisible();
  await page.getByRole("link", { name: "Open the workspace" }).click();
  await expect(page.getByRole("heading", { name: "Universe" })).toBeVisible();
  await expect(page.getByText("Synthetic demo data").first()).toBeVisible();
  await expect(page.getByText(/Assets \(14 selected\)/)).toBeVisible();
});

test("optimise shows metrics, explanations and binding constraints", async ({ page }) => {
  await page.goto("/app/optimise");
  await page.getByRole("button", { name: "Optimise" }).click();
  await expect(page.getByText("Best expected risk-adjusted return")).toBeVisible();
  await expect(page.getByText("Why each asset is (or is not) held")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Binding constraints" })).toBeVisible();
  await expect(page.getByText(/Estimation window: 2016-01-04 to 2025-12-31/)).toBeVisible();
  // Weights sum to 100%: check through the table view of the weights chart.
  await page.getByRole("tab", { name: "Table" }).first().click();
  const cells = await page.locator("section:has-text('Share of portfolio value') td:nth-child(2)").allInnerTexts();
  const total = cells.reduce((a, c) => a + Number(c.replace("%", "")), 0);
  expect(Math.abs(total - 100)).toBeLessThan(0.05);
});

test("infeasible constraints are explained, not approximated", async ({ page }) => {
  await page.goto("/app/optimise");
  await page.getByLabel("Max weight").fill("5");
  await page.getByRole("button", { name: "Optimise" }).click();
  await expect(page.getByText("No portfolio satisfies these constraints")).toBeVisible();
  await expect(page.getByText(/cannot be fully invested/)).toBeVisible();
});

test("ESG constraints fail loudly on unscored assets and report their cost when resolved", async ({ page }) => {
  await page.goto("/app/esg");
  await page.locator("summary", { hasText: "ESG" }).first().click();
  await page.getByLabel("Minimum portfolio ESG score").fill("65");
  await page.getByRole("button", { name: "Measure ESG impact" }).click();
  const alert = page.getByRole("alert").filter({ hasText: "ESG score" });
  await expect(alert).toContainText("requires an ESG score");
  await expect(alert).toContainText("GOLD.SYN");
  await page.getByLabel(/Exclude assets without an ESG score/).check();
  await page.getByRole("button", { name: "Measure ESG impact" }).click();
  await expect(page.getByText("Effect of the ESG settings")).toBeVisible();
  await expect(page.getByText("ESG-efficient frontier")).toBeVisible();
});

test("choosing a base currency offers currency hedging", async ({ page }) => {
  await page.goto("/app");
  await expect(page.getByLabel("Currency risk")).toHaveCount(0);
  await page.getByLabel("Base currency").selectOption("EUR");
  await page.getByLabel("Currency risk").selectOption("hedged");
  await expect(page.getByText(/sold forward at a rate set by the two currencies' central-bank policy rates/)).toBeVisible();
  await expect(page.getByText("EUR, hedged")).toBeVisible();
  // Clearing the base currency also clears hedging.
  await page.getByLabel("Base currency").selectOption("");
  await expect(page.getByLabel("Currency risk")).toHaveCount(0);
  await expect(page.getByText("EUR, hedged")).toHaveCount(0);
});

test("efficient frontier by volatility and by CVaR (tail loss)", async ({ page }) => {
  await page.goto("/app/frontier");
  await page.getByRole("button", { name: "Trace frontier" }).click();
  await expect(page.getByText("Risk–return space")).toBeVisible();
  await page.getByRole("tab", { name: "CVaR (tail loss)" }).click();
  await page.getByLabel("CVaR confidence").selectOption("0.975");
  await page.getByRole("button", { name: "Trace frontier" }).click();
  await expect(page.getByText("Return against tail loss")).toBeVisible();
  await expect(page.getByText(/average loss in the worst 2.5% of days/).first()).toBeVisible();
  await expect(page.getByText("Mean-variance portfolios, measured by CVaR").first()).toBeVisible();
  // Each mode keeps its own result.
  await page.getByRole("tab", { name: "Volatility" }).click();
  await expect(page.getByText("Risk–return space")).toBeVisible();
});

test("Monte Carlo is reproducible with a seed", async ({ page }) => {
  await page.goto("/app/simulate");
  await page.getByLabel("Paths").fill("1000");
  await page.getByRole("button", { name: "Simulate" }).click();
  const tile = page.locator("p", { hasText: /^Median final value$/ }).locator("xpath=following-sibling::p[1]");
  await expect(tile).toBeVisible();
  const first = await tile.innerText();
  await page.reload();
  await expect(page.getByText(/seed 20260926/)).toBeVisible();
  // Recomputed from the persisted request after reload: identical output.
  await expect(tile).toHaveText(first);
});

test("walk-forward backtest separates estimation and evaluation periods", async ({ page }) => {
  await page.goto("/app/backtest");
  await page.getByRole("tab", { name: "Equal weight" }).click();
  await page.getByRole("button", { name: "Run backtest" }).click();
  await expect(page.getByText(/Estimation data from .* evaluation/)).toBeVisible();
  await expect(page.getByText("Contribution to return")).toBeVisible();
  await expect(page.getByText(/Sector attribution/)).toBeVisible();
});

test("sign in, save, list, export and delete a portfolio", async ({ page }) => {
  await page.goto("/login?next=/app/optimise");
  await page.getByLabel("Email").fill(`e2e-${Date.now()}@example.com`);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/app\/optimise/);
  await page.getByRole("button", { name: "Optimise" }).click();
  await expect(page.getByText("Best expected risk-adjusted return")).toBeVisible();
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.getByLabel("Portfolio name").fill("E2E core");
  await page.getByRole("button", { name: "Save portfolio" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();

  await page.goto("/portfolios");
  await expect(page.getByText("E2E core", { exact: true })).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "CSV" }).click();
  expect((await download).suggestedFilename()).toBe("E2E_core.csv");

  page.once("dialog", (d) => void d.accept());
  await page.getByRole("button", { name: "Delete E2E core" }).click();
  await expect(page.getByText("No saved portfolios yet")).toBeVisible();
});

test("compare two portfolios with an in-sample warning", async ({ page }) => {
  await page.goto("/app/optimise");
  await page.getByRole("button", { name: "Optimise" }).click();
  await page.getByRole("button", { name: "Use as working portfolio" }).click();
  await page.goto("/app/compare");
  await page.getByRole("button", { name: "Compare" }).click();
  await expect(page.getByText("In-sample comparison")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Side by side" })).toBeVisible();
});

test("research section renders methodology with mathematics", async ({ page }) => {
  await page.goto("/research");
  await page.getByRole("link", { name: /Optimisation/ }).click();
  await expect(page.getByRole("heading", { name: "Optimisation", level: 1 })).toBeVisible();
  await expect(page.locator(".katex").first()).toBeVisible();
});

test("legal pages are linked from every page and account data can be exported and deleted", async ({ page }) => {
  await page.goto("/app");
  await page.getByRole("link", { name: "Privacy Policy" }).click();
  await expect(page.getByRole("heading", { name: "Privacy Policy" })).toBeVisible();
  await page.getByRole("link", { name: "Terms of Service" }).first().click();
  await expect(page.getByRole("heading", { name: "Terms of Service" })).toBeVisible();

  await page.goto("/login?next=/account");
  await expect(page.getByText(/By signing in you agree to the/)).toBeVisible();
  await page.getByLabel("Email").fill(`acct-${Date.now()}@example.com`);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/account/);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download JSON" }).click();
  expect((await download).suggestedFilename()).toBe("ardentum-account-export.json");
  const del = page.getByRole("button", { name: "Delete my account" });
  await expect(del).toBeDisabled();
  await page.getByLabel('Type "delete" to confirm').fill("delete");
  await del.click();
  await expect(page.getByText("Account deleted")).toBeVisible();
});
