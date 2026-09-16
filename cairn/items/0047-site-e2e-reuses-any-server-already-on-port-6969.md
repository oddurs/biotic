---
id: 47
title: Site e2e reuses any server already on port 6969
type: bug
status: backlog
milestone: instrument
created: 2026-09-16
updated: 2026-09-16
priority: p2
effort: s
area: web/apps/site
---

## Problem

`web/apps/site/playwright.config.ts` sets `reuseExistingServer: !process.env.CI`. Outside CI, `scripts/task check` therefore runs the site's end-to-end tests against whatever already listens on 6969 — on 2026-09-16 a stray `astro dev` from another checkout — and every page timed out at `page.goto`, with the feeds and sitemap returning non-200 because a dev server has no build. The gate fails, or worse passes, for reasons that have nothing to do with the branch.

## Proposal

Never reuse: `reuseExistingServer: false`, or a free port per run (`e2e/serve.mjs` already honours `PORT`; `baseURL` and `webServer.url` would follow it). A local `pnpm dev` on 6969 must not be able to affect the check.

Worked around while finishing 0002 by running Playwright with a throwaway config on `PORT=6970` (14 passed).
