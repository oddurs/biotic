import mdx from "@astrojs/mdx";
import react from "@astrojs/react";
import sitemap from "@astrojs/sitemap";
import stylex from "@stylexjs/unplugin";
import { defineConfig } from "astro/config";
import { fileURLToPath } from "node:url";
import { site } from "./site.config";

// StyleX resolves cross-package tokens relative to the workspace root.
const workspaceRoot = fileURLToPath(new URL("../..", import.meta.url));

export default defineConfig({
  site: site.url,
  base: site.base,
  trailingSlash: "always",
  integrations: [react(), mdx(), sitemap()],
  build: {
    // StyleX appends its CSS to the shared stylesheet; it must exist as a file on every page.
    inlineStylesheets: "never",
  },
  vite: {
    plugins: [
      stylex.vite({ unstable_moduleResolution: { type: "commonJS", rootDir: workspaceRoot } }),
    ],
  },
});
