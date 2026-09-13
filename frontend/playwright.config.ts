import { defineConfig } from "@playwright/test";

const apiPort = process.env.RELAY_BROWSER_API_PORT || "8010";
const appPort = process.env.RELAY_BROWSER_FRONTEND_PORT || "3010";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  use: { baseURL: `http://localhost:${appPort}`, trace: "retain-on-failure" },
  webServer: [
    {
      command:
        process.platform === "win32"
          ? "..\\backend\\.venv\\Scripts\\python.exe ..\\backend\\tests\\browser_server.py"
          : "../backend/.venv/bin/python ../backend/tests/browser_server.py",
      url: `http://127.0.0.1:${apiPort}/health`,
      timeout: 60_000,
      // Falls back to PYTHONPATH when the backend venv has no editable
      // install of `app` (e.g. a Python version below pyproject's pin).
      env: {
        PYTHONPATH: "../backend",
        RELAY_BROWSER_API_PORT: apiPort,
        RELAY_BROWSER_FRONTEND_PORT: appPort,
      },
    },
    {
      command: `npm run dev -- --port ${appPort}`,
      url: `http://localhost:${appPort}/login`,
      timeout: 120_000,
      env: { API_INTERNAL_URL: `http://127.0.0.1:${apiPort}` },
    },
  ],
});
