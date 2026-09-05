import { defineConfig, devices } from "@playwright/test";

/** Real FastAPI persistence with explicit test-only generation dependencies. */
export default defineConfig({
  testDir: "frontend/e2e",
  testMatch: "live-*.spec.ts",
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  timeout: 60_000,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4184",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        "uv run uvicorn --app-dir tests browser_app:create_browser_app --factory --host 127.0.0.1 --port 8016",
      url: "http://127.0.0.1:8016/api/health",
      env: { PYTHONPATH: process.cwd() },
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command:
        "pnpm exec vite --config frontend/vite.config.ts --host 127.0.0.1 --port 4184 --strictPort",
      env: { API_PROXY_TARGET: "http://127.0.0.1:8016" },
      url: "http://127.0.0.1:4184",
      reuseExistingServer: false,
    },
  ],
});
