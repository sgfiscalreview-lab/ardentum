import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const PAGES = ["/", "/app", "/app/optimise", "/app/frontier", "/app/esg-data", "/research/optimisation", "/login", "/terms", "/privacy", "/cookies", "/licences", "/account", "/app/compare", "/tour", "/app/analytics?tour=2", "/usage", "/classroom", "/classroom/worksheet", "/glossary"];

for (const theme of ["light", "dark"] as const) {
  for (const path of PAGES) {
    test(`${path} has no serious accessibility violations (${theme})`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: theme });
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
      const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(", ")}`)).toEqual([]);
    });
  }
}

test("optimise results have no serious accessibility violations", async ({ page }) => {
  await page.goto("/app/optimise");
  await page.getByRole("button", { name: "Optimise" }).click();
  await expect(page.getByText("Why each asset is (or is not) held")).toBeVisible();
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(", ")}`)).toEqual([]);
});
