import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "frontend/e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: "html",
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        "pnpm exec vite --config frontend/vite.config.ts --host 127.0.0.1 --port 4174",
      env: { API_PROXY_TARGET: "http://127.0.0.1:8015" },
      url: "http://127.0.0.1:4174",
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "uv run uvicorn app.main:app --host 127.0.0.1 --port 8015",
      url: "http://127.0.0.1:8015/api/health",
      reuseExistingServer: !process.env.CI,
    },
    {
      command:
        "pnpm exec vite --config frontend/vite.config.ts --host 127.0.0.1 --mode preview --port 4173",
      url: "http://127.0.0.1:4173",
      reuseExistingServer: !process.env.CI,
    },
  ],
});
