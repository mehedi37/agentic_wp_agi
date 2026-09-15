import { defineConfig, devices } from "@playwright/test";

/**
 * Points at an already-running backend (postgres/redis/backend, e.g. via
 * `make up && make seed`) -- see e2e/README.md. This config only drives the
 * frontend dev server itself; it does not attempt to orchestrate the
 * Python backend/worker from Node.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: "npm run dev",
        url: "http://localhost:3000",
        reuseExistingServer: true,
        timeout: 60_000,
      },
});
