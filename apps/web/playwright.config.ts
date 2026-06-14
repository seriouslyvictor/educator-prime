import { defineConfig } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const API_DIR = path.resolve(__dirname, "../api");

export default defineConfig({
  testDir: "./e2e",
  // Run tests serially to avoid SQLite write contention on the shared e2e.db
  // and race conditions on the shared Vite dev server.
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "html",
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "on-first-retry",
  },
  webServer: [
    {
      // Backend in mock mode with a disposable DB so runs are deterministic.
      // Always start a fresh mock backend — never reuse a real-provider dev
      // server that may be running on :8000, which would fail auth assertions.
      command:
        "uv run --extra dev python -m uvicorn classroom_downloader.main:app --app-dir src --port 8000",
      cwd: API_DIR,
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        CD_GOOGLE_PROVIDER: "mock",
        CD_GRADING_ENGINE: "mock",
        CD_DATABASE_URL: "sqlite:///./e2e.db",
        CD_LOG_LEVEL: "WARNING",
      },
    },
    {
      command: "pnpm dev",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
