import { expect, test, type Page } from "@playwright/test";

// Nothing may be wider than a phone screen: sideways scrolling hides the navigation and
// makes every page awkward to use. Wide tables scroll inside their own frames instead.
test.use({ viewport: { width: 375, height: 800 } });

const PAGES = ["/", "/app", "/app/analytics", "/app/optimise", "/app/frontier", "/app/esg", "/app/esg-data", "/app/simulate", "/app/backtest", "/app/compare", "/portfolios", "/research", "/research/optimisation", "/login", "/account", "/terms", "/privacy", "/cookies", "/licences", "/tour", "/app/optimise?tour=3", "/usage", "/classroom", "/classroom/worksheet"];

const overflow = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

test("no page is wider than a phone screen", async ({ page }) => {
  const wide: string[] = [];
  for (const path of PAGES) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const extra = await overflow(page);
    if (extra > 0) wide.push(`${path} (+${extra}px)`);
  }
  expect(wide).toEqual([]);
});

test("results fit a phone screen", async ({ page }) => {
  await page.goto("/app/optimise");
  await page.getByRole("button", { name: "Optimise" }).click();
  await expect(page.getByText("Why each asset is (or is not) held")).toBeVisible();
  expect(await overflow(page)).toBe(0);

  await page.goto("/app/backtest");
  await page.getByRole("button", { name: "Run backtest" }).click();
  await expect(page.getByText(/drawdown/i).first()).toBeVisible({ timeout: 60_000 });
  expect(await overflow(page)).toBe(0);
});

test("the menu stays reachable on a phone", async ({ page }) => {
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Primary" });
  for (const name of ["Workspace", "Portfolios", "Research"]) await expect(nav.getByRole("link", { name })).toBeInViewport();
});
