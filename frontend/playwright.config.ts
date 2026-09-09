import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  use: { baseURL: "http://localhost:3010", trace: "retain-on-failure" },
  webServer: [
    {
      command:
        process.platform === "win32"
          ? "..\\backend\\.venv\\Scripts\\python.exe ..\\backend\\tests\\browser_server.py"
          : "../backend/.venv/bin/python ../backend/tests/browser_server.py",
      url: "http://127.0.0.1:8010/health",
      timeout: 60_000,
    },
    {
      command: "npm run dev -- --port 3010",
      url: "http://localhost:3010/login",
      timeout: 120_000,
      env: { API_INTERNAL_URL: "http://127.0.0.1:8010" },
    },
  ],
});
