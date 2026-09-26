// Captures real screenshots of the running app (synthetic demo data) for the landing page.
// Usage: start the API (port 8000) and the web app (port 3000), then
//   node scripts/capture-screenshots.mjs
// Set PLAYWRIGHT_CHROMIUM_PATH to use a system Chromium.
import { chromium } from "@playwright/test";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const OUT = new URL("../public/screenshots/", import.meta.url).pathname;
const SIZE = { width: 1440, height: 900 };
// The results column of the workspace pages (right of the settings panel), in CSS pixels.
const CLIP = { x: 600, y: 255, width: 816, height: 620 };

const SHOTS = [
  { name: "optimise", path: "/app/optimise", run: /^Optimise$/, wait: "Why each asset" },
  { name: "frontier", path: "/app/frontier", run: /Trace frontier/, wait: "Risk–return space" },
  { name: "simulate", path: "/app/simulate", run: /^Simulate$/, wait: "simulated paths" },
  { name: "backtest", path: "/app/backtest", run: /Run backtest/, wait: "Contribution to return" },
];

const browser = await chromium.launch(
  process.env.PLAYWRIGHT_CHROMIUM_PATH ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH } : {},
);
for (const theme of ["light", "dark"]) {
  const ctx = await browser.newContext({ viewport: SIZE, colorScheme: theme, deviceScaleFactor: 1.5 });
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
    await page.waitForTimeout(600);
    await page.screenshot({ path: `${OUT}${s.name}-${theme}.png`, clip: CLIP });
    console.log(`saved ${s.name}-${theme}.png`);
  }
  await ctx.close();
}
await browser.close();
