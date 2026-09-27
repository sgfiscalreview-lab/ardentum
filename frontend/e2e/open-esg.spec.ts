import { expect, test } from "@playwright/test";

// Upload real-company data with ISINs, build ESG scores from (mocked) WikiRate open data,
// confirm an unmatched company by hand, save the overlay and see it in analytics.
const START = Date.UTC(2023, 0, 2);
const prices =
  "date,AAA,BBB,CCC\n" +
  Array.from({ length: 150 }, (_, i) => {
    const d = new Date(START + i * 86_400_000).toISOString().slice(0, 10);
    return `${d},${(100 + i * 0.1 + (i % 7) * 0.3).toFixed(4)},${(50 + (i % 11) * 0.2 + i * 0.05).toFixed(4)},${(20 + (i % 5) * 0.1 + i * 0.02).toFixed(4)}`;
  }).join("\n");
const meta = "ticker,name,isin\nAAA,Apple,US0378331005\nBBB,Adidas,DE000A1EWWW0\nCCC,Puma,\n";

test("build, save and use open ESG scores from WikiRate", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => window.localStorage.clear());
  await page.goto("/login?next=/app");
  await page.getByLabel("Email").fill(`esg-${Date.now()}@example.com`);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/app$/);

  await page.locator("#ds-name").fill("Brands");
  await page.locator("#ds-prices").setInputFiles({ name: "p.csv", mimeType: "text/csv", buffer: Buffer.from(prices) });
  await page.locator("#ds-meta").setInputFiles({ name: "m.csv", mimeType: "text/csv", buffer: Buffer.from(meta) });
  await page.getByRole("button", { name: "Upload", exact: true }).click();
  await expect(page.getByText(/Uploaded “Brands” with 3 assets/)).toBeVisible();

  await page.getByRole("link", { name: /ESG data/ }).first().click();
  await expect(page.getByRole("heading", { name: "Open ESG data" })).toBeVisible();
  await page.getByLabel("Search metrics").fill("emissions");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText("Not numeric: cannot become a score.")).toBeVisible();
  await page.getByRole("button", { name: /Direct greenhouse gas/ }).click();
  await page.getByLabel("Direction").selectOption("lower");
  await page.getByRole("button", { name: /Preview scores for 3 assets/ }).click();

  await expect(page.getByText("matched by ISIN").first()).toBeVisible();
  await expect(page.getByText("Not numeric", { exact: true })).toBeVisible();
  await page.getByLabel("Find company for CCC").fill("Puma");
  await page.getByRole("button", { name: "Find", exact: true }).click();
  await page.getByRole("button", { name: /^Puma/ }).click();
  await expect(page.getByText("chosen by you")).toBeVisible();
  await expect(page.getByText(/2 of 3 assets scored/)).toBeVisible();
  await expect(page.getByText(/licensed CC BY 4\.0/)).toBeVisible();

  await page.getByRole("button", { name: "Save and use in workspace" }).click();
  await expect(page.getByText(/applied it to the workspace \(2 of 3 assets scored\)/)).toBeVisible();
  await expect(page.getByText("In use")).toBeVisible();

  await page.goto("/app/analytics");
  await page.getByRole("button", { name: /Compute analytics|Recompute/ }).click();
  // First table on the page: asset statistics, whose last column is the ESG score.
  const row = page.locator("table").first().locator("tr", { hasText: "CCC" });
  await expect(row.locator("td").last()).toHaveText("100");
  await expect(page.locator("table").first().locator("tr", { hasText: "BBB" }).locator("td").last()).toHaveText("n/a");
  await page.getByText("Data & provenance").click();
  await expect(page.getByText(/open-data overlay/)).toBeVisible();
});
