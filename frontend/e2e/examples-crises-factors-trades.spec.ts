import { expect, test, type Page } from "@playwright/test";

// The API's Ken French data comes from the local stand-in: generated returns for 400 business
// days from 2 January 2020, which cover the COVID-19 crash but no earlier crisis.

async function fresh(page: Page) {
  await page.goto("/");
  await page.evaluate(() => window.localStorage.clear());
  await page.goto("/app");
}

test("crisis example: replays the crash the data covers and says why the others are missing", async ({ page }) => {
  await fresh(page);
  await page.getByRole("button", { name: /US industries through past crashes/ }).click();
  await expect(page).toHaveURL(/\/app\/crises$/);
  const covid = page.getByRole("row", { name: /COVID-19 crash/ });
  await expect(covid).toContainText(/-?\d+\.\d%/);
  await expect(page.getByRole("row", { name: /1929 crash/ })).toContainText("Not available: The data begins after this period started");
  await expect(page.getByRole("row", { name: /2022 inflation/ })).toContainText("Not available: The data ends");
  await expect(page.getByText("Value of 1 invested at the close on 19 Feb 2020")).toBeVisible();
  await expect(page.getByText("What each holding contributed")).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Market" })).toBeVisible();
});

test("factor example: loadings, the split of the average return and each holding", async ({ page }) => {
  await fresh(page);
  await page.getByRole("button", { name: /What drives US industries/ }).click();
  await expect(page).toHaveURL(/\/app\/factors$/);
  await expect(page.getByText("Market loading")).toBeVisible();
  await expect(page.getByText(/For each 1% the US market moved above the risk-free rate/)).toBeVisible();
  await expect(page.getByText("Where the average return came from")).toBeVisible();
  await expect(page.getByRole("row", { name: /NODUR/ })).toBeVisible();
});

test("optimise and 60/40 examples open finished results", async ({ page }) => {
  await fresh(page);
  await page.getByRole("button", { name: /Lowest-risk mix of US industries/ }).click();
  await expect(page).toHaveURL(/\/app\/optimise$/);
  await expect(page.getByText(/Lowest-risk portfolio available/)).toBeVisible();

  await page.goto("/app");
  await page.getByRole("button", { name: /Balanced 60\/40/ }).click();
  await expect(page).toHaveURL(/\/app\/compare$/);
  await expect(page.getByRole("columnheader", { name: /Working: Balanced 60\/40/ }).first()).toBeVisible();
  await expect(page.getByText("Historical CAGR")).toBeVisible();
});

test("real industry data lists its industries to pick from", async ({ page }) => {
  await fresh(page);
  await page.getByRole("button", { name: /US industries: 12 portfolios/ }).click();
  await expect(page.getByLabel("Select NODUR")).toBeVisible();
  await page.getByLabel("Select NODUR").check();
  await page.getByLabel("Select UTILS").check();
  await expect(page.getByText("Assets (2 selected)")).toBeVisible();
});

test("crisis replay on demo data: named crises need real data, your own dates work", async ({ page }) => {
  await fresh(page);
  await page.goto("/app/crises");
  await page.getByLabel("Your own dates").check();
  await page.getByLabel("Bought at the close on").fill("2018-01-26");
  await page.getByLabel("Held until").fill("2018-04-02");
  await page.getByRole("button", { name: "Replay" }).click();
  await expect(page.getByRole("row", { name: /Dot-com crash/ })).toContainText("synthetic");
  await expect(page.getByRole("row", { name: /Your period/ })).toContainText(/-?\d+\.\d%/);
});

test("trade list: from what you hold to the 60/40 target, with costs", async ({ page }) => {
  await fresh(page);
  await page.getByRole("button", { name: /Balanced 60\/40/ }).click();
  await expect(page).toHaveURL(/\/app\/compare$/);
  await page.goto("/app/trades");
  await page.getByLabel(/^GOVB\.SYN/).fill("5000");
  await page.getByLabel(/^NWS\.SYN/).fill("5000");
  await page.getByLabel("New money").selectOption("add");
  await page.getByLabel("Amount to add").fill("2000");
  await page.getByRole("button", { name: "Make trade list" }).click();
  const govb = page.getByRole("row", { name: /GOVB\.SYN/ });
  await expect(govb).toContainText("Sell");
  await expect(page.getByRole("row", { name: /CORP\.SYN/ })).toContainText("Buy");
  await expect(page.getByText("These assets are not directly tradable")).toBeVisible();
  // 12,000 less 10 basis points of everything traded.
  await expect(page.getByText("Value after")).toBeVisible();
  await expect(page.getByRole("row", { name: /^Total/ })).toContainText(/11,9\d\d\.\d\d/);
});
