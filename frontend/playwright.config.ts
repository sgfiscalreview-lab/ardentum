import { defineConfig, devices } from "@playwright/test";

const CHROMIUM = process.env.PLAYWRIGHT_CHROMIUM_PATH;
const reuse = !process.env.CI;

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
    viewport: { width: 1440, height: 1000 },
    launchOptions: CHROMIUM ? { executablePath: CHROMIUM } : {},
  },
  webServer: [
    {
      // Stand-in for the WikiRate API (open ESG data), serving recorded-format fixtures.
      command: "cd ../backend && uv run python -m tests.fixtures.wikirate_mock_server 8765",
      port: 8765,
      reuseExistingServer: reuse,
      timeout: 60_000,
    },
    {
      // Backend in dev-auth mode with a throwaway SQLite database.
      command:
        "cd ../backend && rm -f /tmp/ardentum-e2e.sqlite3 && ARDENTUM_DATABASE_URL=sqlite:////tmp/ardentum-e2e.sqlite3 ARDENTUM_ENV=test ARDENTUM_WIKIRATE_BASE_URL=http://127.0.0.1:8765 uv run uvicorn ardentum.api.main:create_app --factory --port 8000",
      url: "http://localhost:8000/api/v1/health",
      reuseExistingServer: reuse,
      timeout: 120_000,
    },
    {
      command: "npm run build && npm run start",
      url: "http://localhost:3000",
      reuseExistingServer: reuse,
      timeout: 300_000,
    },
  ],
});
