import { chromium } from "@playwright/test";

const OUT = process.env.SHOTS ?? "/tmp/shots";
const BASE = process.env.BASE ?? "http://localhost:3000";
const theme = process.env.THEME ?? "light";
const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: theme });
const page = await ctx.newPage();
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));

async function shot(name) { await page.screenshot({ path: `${OUT}/${theme}-${name}.png`, fullPage: true }); }
async function run(path, button, waitText, name) {
  await page.goto(BASE + path);
  await page.getByRole("button", { name: button }).first().click();
  await page.getByText(waitText).first().waitFor({ timeout: 60000 });
  await page.waitForTimeout(500);
  await shot(name);
}

await page.goto(BASE + "/");
await shot("home");
await page.goto(BASE + "/app");
await page.getByText("Assets (").waitFor();
await shot("universe");
await run("/app/analytics", /Compute analytics|Recompute/, "Asset statistics", "analytics");
await run("/app/optimise", "Optimise", "Why each asset", "optimise");
await page.getByRole("button", { name: /working portfolio/ }).first().click();
await run("/app/frontier", "Trace frontier", "Risk–return space", "frontier");
await page.goto(BASE + "/app/esg");
await page.locator("summary", { hasText: "ESG" }).first().click();
await page.getByLabel("Minimum portfolio ESG score").fill("65");
await page.getByLabel(/Exclude assets without an ESG score/).check();
await page.getByRole("button", { name: "Measure ESG impact" }).click();
await page.getByText("Effect of the ESG settings").waitFor({ timeout: 60000 });
await page.waitForTimeout(500);
await shot("esg");
await run("/app/simulate", "Simulate", "simulated paths", "simulate");
await run("/app/backtest", "Run backtest", "Contribution to return", "backtest");
await run("/app/compare", "Compare", "Side by side", "compare");
await page.goto(BASE + "/research/optimisation");
await page.waitForTimeout(500);
await shot("research");
console.log("console errors:", errors.length ? errors : "none");
await browser.close();
