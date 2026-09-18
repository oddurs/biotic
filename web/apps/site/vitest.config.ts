import { defineConfig } from "vitest/config";

// Unit tests for the site's own logic (the dish port). The browser suite is Playwright.
export default defineConfig({ test: { environment: "node", include: ["src/**/*.test.ts"] } });
