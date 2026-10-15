// Captures real screenshots of the running app (synthetic demo data) for the landing page.
// Usage: start the API (port 8000) and the web app (port 3000), then
//   node scripts/capture-screenshots.mjs
// Set PLAYWRIGHT_CHROMIUM_PATH to use a system Chromium.
import { writeFileSync } from "node:fs";

import { chromium } from "@playwright/test";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const OUT = new URL("../public/screenshots/", import.meta.url).pathname;
// The results column (right of the settings panel) is 792 CSS pixels at this width.
const SIZE = { width: 1448, height: 1400 };
// Page background kept around the cards, so their own borders and shadows are whole.
const MARGIN = 8;
// The tallest picture, in CSS pixels; it ends at the bottom of the last card that fits.
const MAX_HEIGHT = 900;
const SIZES = new URL("../src/lib/screenshots.json", import.meta.url).pathname;

const SHOTS = [
  { name: "optimise", path: "/app/optimise", run: /^Optimise$/, wait: "Why each asset", max: 1100 }, // through the weights chart
  { name: "frontier", path: "/app/frontier", run: /Trace frontier/, wait: "Risk–return space" },
  { name: "simulate", path: "/app/simulate", run: /^Simulate$/, wait: "simulated paths" },
  { name: "backtest", path: "/app/backtest", run: /Run backtest/, wait: "Contribution to return" },
];

const browser = await chromium.launch(
  process.env.PLAYWRIGHT_CHROMIUM_PATH ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH } : {},
);
const sizes = {};
for (const theme of ["light", "dark"]) {
  const ctx = await browser.newContext({ viewport: SIZE, colorScheme: theme, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  await page.goto(BASE + "/");
  await page.evaluate((t) => {
    localStorage.clear();
    localStorage.setItem("ardentum.theme", t);
  }, theme);
  for (const s of SHOTS) {
    await page.goto(BASE + s.path);
    await page.getByRole("button", { name: s.run }).first().click();
    await page.getByText(s.wait).first().waitFor({ timeout: 120_000 });
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(800); // let springs settle
    // The results column is the element that shows "Computing" while a run is in progress.
    // The picture shows whole cards only: it stops at the bottom of the last one that fits.
    const clip = await page.locator("main [aria-busy]").first().evaluate((col, { margin, max }) => {
      const box = col.getBoundingClientRect();
      const panels = [...col.querySelectorAll("*")].filter((el) => {
        const cs = getComputedStyle(el);
        return parseFloat(cs.borderTopWidth) > 0 && parseFloat(cs.borderTopLeftRadius) >= 8;
      });
      const outer = panels.filter((el) => !panels.some((p) => p !== el && p.contains(el)));
      const bottoms = outer.map((el) => el.getBoundingClientRect().bottom).filter((b) => b - box.top <= max);
      const bottom = Math.max(...bottoms);
      return { x: box.left - margin, y: box.top - margin, width: box.width + 2 * margin, height: Math.ceil(bottom - box.top) + 2 * margin };
    }, { margin: MARGIN, max: s.max ?? MAX_HEIGHT });
    await page.screenshot({ path: `${OUT}${s.name}-${theme}.png`, clip });
    if (theme === "light") sizes[s.name] = { width: clip.width, height: clip.height };
    console.log(`saved ${s.name}-${theme}.png`);
  }
  await ctx.close();
}
await browser.close();
writeFileSync(SIZES, JSON.stringify(sizes, null, 2) + "\n");
console.log(`sizes in ${SIZES}`);
