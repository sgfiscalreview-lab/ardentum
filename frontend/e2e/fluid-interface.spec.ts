import { expect, test, type Locator, type Page } from "@playwright/test";

// The interface rules in .claude/skills/apple-design: springs that can be grabbed, sheets
// that follow the finger, popovers anchored to their trigger, keyboard paths for all of it.

const bottom = async (el: Locator) => {
  const box = await el.boundingBox();
  return box ? Math.round(box.y + box.height) : Number.NaN;
};

async function dragGrabber(page: Page, sheet: Locator, distance: number, beforeRelease?: () => Promise<void>) {
  const handle = await sheet.getByRole("heading", { name: "Workspace steps" }).boundingBox();
  if (!handle) throw new Error("The sheet has no grabber.");
  const x = handle.x + 8;
  const y = handle.y + handle.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x, y + distance, { steps: 6 });
  if (beforeRelease) await beforeRelease();
  await page.mouse.up();
}

test.describe("on a phone", () => {
  test.use({ viewport: { width: 375, height: 800 } });

  test("the workspace steps open in a sheet that Escape closes and that moves between steps", async ({ page }) => {
    await page.goto("/app/analytics");
    await expect(page.getByText("Step 2 of 12")).toBeVisible();
    const opener = page.getByRole("button", { name: "All steps" });
    await opener.click();
    const sheet = page.getByRole("dialog", { name: "Workspace steps" });
    await expect(sheet).toBeVisible();
    await expect(sheet.getByRole("link", { name: /Analytics/ })).toBeFocused(); // starts on the current step
    await page.keyboard.press("Escape");
    await expect(sheet).toBeHidden();
    await expect(opener).toBeFocused(); // back where it was opened

    await opener.click();
    await sheet.getByRole("link", { name: /Frontier/ }).click();
    await expect(page).toHaveURL(/\/app\/frontier$/);
    await expect(sheet).toBeHidden();
    await expect(page.getByRole("heading", { name: "Efficient frontier", level: 1 })).toBeVisible();
    await expect(page.getByText("Step 4 of 12")).toBeVisible();
  });

  test("the sheet follows a drag, settles back when let go slowly and closes when flicked down", async ({ page }) => {
    await page.goto("/app");
    await page.getByRole("button", { name: "All steps" }).click();
    const sheet = page.getByRole("dialog", { name: "Workspace steps" });
    await expect.poll(() => bottom(sheet)).toBe(800); // resting against the bottom edge

    // A short drag: the sheet moves with the pointer, 1:1. A pause before letting go is no
    // flick, so it settles back.
    await dragGrabber(page, sheet, 60, async () => {
      expect(Math.abs((await bottom(sheet)) - 860)).toBeLessThanOrEqual(1);
      await page.waitForTimeout(250);
    });
    await expect(sheet).toBeVisible();
    await expect.poll(() => bottom(sheet)).toBe(800);

    await dragGrabber(page, sheet, 220); // a quick flick down, not past half its height
    await expect(sheet).toBeHidden();
  });
});

test("the copied-link note is anchored to its button and put away by Escape or a press elsewhere", async ({ browser }) => {
  const context = await browser.newContext();
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const page = await context.newPage();
  await page.goto("/app/analytics");
  const copy = page.getByRole("button", { name: "Copy link" });
  await copy.click();
  const note = page.getByText("Link copied.");
  await expect(note).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(note).toBeHidden();

  await copy.click();
  await expect(note).toBeVisible();
  await page.getByRole("heading", { name: "Historical analytics", level: 1 }).click();
  await expect(note).toBeHidden();
  await context.close();
});

test("the colour theme is a segmented control that arrow keys move through", async ({ page }) => {
  await page.goto("/");
  const group = page.getByRole("radiogroup", { name: "Colour theme" });
  await group.getByRole("radio", { name: "Dark" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(group.getByRole("radio", { name: "Dark" })).toHaveAttribute("aria-checked", "true");
  await page.keyboard.press("ArrowLeft");
  await expect(group.getByRole("radio", { name: "Light" })).toBeFocused();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.keyboard.press("Home");
  await expect(group.getByRole("radio", { name: "Auto" })).toHaveAttribute("aria-checked", "true");
});
