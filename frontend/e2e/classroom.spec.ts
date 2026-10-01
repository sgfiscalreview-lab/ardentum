import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

const answers = JSON.parse(readFileSync(new URL("../src/lib/classroom-answers.json", import.meta.url), "utf8")) as {
  max_sharpe_promised: number;
};

test("the classroom guide links to a printable worksheet and gives the answers", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("navigation", { name: "Footer" }).getByRole("link", { name: "Classroom" }).click();
  await expect(page.getByRole("heading", { name: "Teach with Ardentum", level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Lesson plan" })).toBeVisible();
  await expect(page.getByText(`promises a Sharpe ratio of ${answers.max_sharpe_promised.toFixed(2)}`)).toBeVisible();

  await page.getByRole("link", { name: "Open the student worksheet" }).click();
  await expect(page.getByRole("heading", { name: "Risk, diversification and the optimiser's promise", level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: /^Exercise \d\./ })).toHaveCount(3);
  await expect(page.getByRole("button", { name: "Print the worksheet" })).toBeVisible();
  // The address students need on paper.
  await expect(page.getByText("localhost:3000")).toBeVisible();
  // Printing leaves out the site header, footer and the button itself.
  await page.emulateMedia({ media: "print" });
  await expect(page.getByRole("button", { name: "Print the worksheet" })).toBeHidden();
  await expect(page.getByRole("navigation", { name: "Footer" })).toBeHidden();
});

test("the workspace defaults reproduce the classroom answer key", async ({ page }) => {
  // Exercise 2 starts from the default maximum-Sharpe optimisation.
  await page.goto("/app/optimise");
  await page.getByRole("button", { name: "Optimise", exact: true }).click();
  await expect(page.getByText(`Sharpe ratio ${answers.max_sharpe_promised.toFixed(2)}.`)).toBeVisible();
});
