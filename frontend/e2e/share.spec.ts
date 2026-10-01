import { expect, test } from "@playwright/test";

test("a copied link opens the same calculation in another browser, with a way back", async ({ browser }) => {
  // Sender: minimum volatility with a 25% cap, optimised.
  const sender = await browser.newContext();
  await sender.grantPermissions(["clipboard-read", "clipboard-write"]);
  const a = await sender.newPage();
  await a.goto("/app/optimise");
  await a.getByLabel("Objective", { exact: true }).selectOption("min_volatility");
  await a.getByLabel("Max weight").fill("25");
  await a.getByRole("button", { name: "Optimise" }).click();
  const headline = a.getByText(/Lowest-risk portfolio available/);
  await expect(headline).toBeVisible();
  const result = await headline.innerText(); // names the volatility achieved
  await a.getByRole("button", { name: "Copy link" }).click();
  await expect(a.getByText("Link copied.")).toBeVisible();
  const link = await a.evaluate(() => navigator.clipboard.readText());
  expect(link).toMatch(/\/app\/optimise#share=[A-Za-z0-9_-]+$/);

  // Recipient: their own settings first, then the link.
  const recipient = await browser.newContext();
  const b = await recipient.newPage();
  await b.goto("/app/optimise");
  await b.getByLabel("Max weight").fill("40");
  await b.getByLabel("Max weight").press("Tab");
  await b.goto(link);
  await expect(b.getByText("You opened a shared link")).toBeVisible();
  await expect(b).toHaveURL(/\/app\/optimise$/); // the fragment is removed once read
  await expect(b.getByText(/Lowest-risk portfolio available/)).toHaveText(result); // recomputed without a click
  await expect(b.getByLabel("Max weight")).toHaveValue("25");

  await b.getByRole("button", { name: "Go back to my settings" }).click();
  await expect(b.getByText("You opened a shared link")).toHaveCount(0);
  await expect(b.getByLabel("Max weight")).toHaveValue("40");

  // A damaged link leaves the settings alone and says so.
  await b.goto(link.slice(0, link.length - 12));
  await expect(b.getByText("This shared link could not be read")).toBeVisible();
  await expect(b.getByLabel("Max weight")).toHaveValue("40");

  // Opened as the first page in a new browser (the usual case: a link from a message).
  const newcomer = await browser.newContext();
  const c = await newcomer.newPage();
  await c.goto(link);
  await expect(c.getByText("You opened a shared link")).toBeVisible();
  await expect(c.getByText(/Lowest-risk portfolio available/)).toHaveText(result);
  await c.getByRole("button", { name: "Keep these settings" }).click();
  await c.reload();
  await expect(c.getByLabel("Max weight")).toHaveValue("25"); // kept in this browser
  await expect(c.getByText("You opened a shared link")).toHaveCount(0);
  await sender.close();
  await recipient.close();
  await newcomer.close();
});
