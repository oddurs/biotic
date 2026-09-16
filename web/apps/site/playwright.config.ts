import { defineConfig } from "@playwright/test";

// End-to-end checks run against the built site, served the way it is deployed.
export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? "github" : "list",
  use: { baseURL: "http://localhost:6969", trace: "retain-on-failure" },
  webServer: {
    command: "pnpm exec astro build && node e2e/serve.mjs",
    url: "http://localhost:6969/",
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
