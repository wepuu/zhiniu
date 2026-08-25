import { defineConfig } from "@playwright/test";

const externalBaseUrl = process.env.E2E_BASE_URL;
const baseURL = externalBaseUrl ?? "http://127.0.0.1:3100";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 2,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    launchOptions: { args: ["--no-proxy-server"] },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: { browserName: "chromium", viewport: { width: 1440, height: 900 } },
    },
    {
      name: "mobile-chromium",
      use: {
        browserName: "chromium",
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
});
