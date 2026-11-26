import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  timeout: 90000,
  workers: 1,
  reporter: [
    ["list"],
    ["junit", { outputFile: "../benchmark/frontend-results.xml" }],
  ],
  use: {
    baseURL: "http://localhost:5173",
    browserName: "chromium",
    channel: process.env.BROWSERFLOW_CHROMIUM_CHANNEL || undefined,
    screenshot: "only-on-failure",
  },
  webServer: {
    command:
      process.platform === "win32"
        ? "..\\.venv\\Scripts\\python.exe ..\\scripts\\dev.py"
        : "../.venv/bin/python ../scripts/dev.py",
    url: "http://localhost:5173/login",
    reuseExistingServer: !process.env.CI,
    timeout: 60000,
  },
});
