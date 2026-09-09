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
