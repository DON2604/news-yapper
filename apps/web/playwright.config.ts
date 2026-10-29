import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3000";
// Use an installed browser (e.g. PLAYWRIGHT_CHANNEL=chrome or msedge) where `playwright install` can't download.
const channel = process.env.PLAYWRIGHT_CHANNEL || undefined;

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL, trace: "retain-on-failure" },
  projects: [
    { name: "e2e", testMatch: /.*\.e2e\.ts/, use: { ...devices["Desktop Chrome"], channel } },
    { name: "screens", testMatch: /screens\.spec\.ts/, use: { ...devices["Desktop Chrome"], channel } },
  ],
  webServer: {
    // Starts local Postgres, migrations, demo seed, API, worker and web (see scripts/dev.mjs).
    command: "node ../../scripts/dev.mjs",
    url: baseURL,
    reuseExistingServer: true,
    timeout: 240_000,
  },
});
