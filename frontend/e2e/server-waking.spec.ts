import { expect, test } from "@playwright/test";

test("says the server is starting while the first requests wait, then gets out of the way", async ({ page }) => {
  // Stand in for a sleeping API: every call is held for a few seconds before it is answered.
  await page.route("**/api/v1/**", async (route) => {
    await new Promise((r) => setTimeout(r, 4500));
    await route.continue();
  });
  await page.goto("/app");
  const notice = page.getByRole("status").filter({ hasText: "Starting the calculation server" });
  await expect(notice).toBeVisible({ timeout: 10_000 });
  await expect(notice).toContainText("continues on its own");
  // Once the API answers, the notice goes and the page carries on.
  await expect(notice).toBeHidden({ timeout: 20_000 });
  await expect(page.getByRole("heading", { name: "Universe", level: 1 })).toBeVisible();
  await page.unroute("**/api/v1/**");
});

test("a page whose API answers quickly shows no notice", async ({ page }) => {
  await page.goto("/app");
  await expect(page.getByRole("heading", { name: "Universe", level: 1 })).toBeVisible();
  await page.waitForTimeout(3500);
  await expect(page.getByText("Starting the calculation server")).toHaveCount(0);
});
