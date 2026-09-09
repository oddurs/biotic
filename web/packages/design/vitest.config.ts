import stylex from "@stylexjs/unplugin";
import react from "@vitejs/plugin-react";
import { playwright } from "@vitest/browser-playwright";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const root = fileURLToPath(new URL("../..", import.meta.url));

export default defineConfig({
  plugins: [
    stylex.vite({ unstable_moduleResolution: { type: "commonJS", rootDir: root } }),
    react(),
  ],
  test: {
    // @stylexjs/unplugin leaves file handles open in its Vite dev server, which Vitest
    // otherwise waits ten seconds for after the last test.
    teardownTimeout: 1000,
    projects: [
      {
        extends: true,
        test: { name: "node", environment: "node", include: ["src/**/*.test.ts"] },
      },
      {
        extends: true,
        test: {
          name: "browser",
          include: ["src/**/*.test.tsx"],
          setupFiles: ["src/test/setup.ts"],
          browser: {
            enabled: true,
            headless: true,
            provider: playwright(),
            instances: [{ browser: "chromium" }],
          },
        },
      },
    ],
  },
});
