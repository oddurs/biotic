import mdx from "@astrojs/mdx";
import expressiveCode from "astro-expressive-code";
import pagefind from "astro-pagefind";
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
  integrations: [
    react(),
    // Code blocks. Styles are inlined per page so StyleX keeps the single shared stylesheet.
    expressiveCode({
      themes: ["github-light", "github-dark"],
      themeCssSelector: (theme) => `[data-theme="${theme.type}"]`,
      useDarkModeMediaQuery: true,
      emitExternalStylesheet: false,
      styleOverrides: {
        borderRadius: "0.5rem",
        codeFontFamily: '"JetBrains Mono Variable", ui-monospace, "SF Mono", Menlo, monospace',
        codeFontSize: "0.875rem",
        frames: { shadowColor: "transparent" },
      },
    }),
    mdx(),
    sitemap(),
    pagefind(),
  ],
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
