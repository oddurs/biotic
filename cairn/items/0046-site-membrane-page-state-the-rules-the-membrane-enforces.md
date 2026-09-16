---
id: 46
title: 'Site membrane page: state the rules the membrane enforces'
type: docs
status: backlog
milestone: dish
created: 2026-09-16
updated: 2026-09-16
priority: p3
area: web/
effort: s
part_of:
- 39
---

## Problem

`web/apps/site/src/content/docs/instrument/membrane.mdx` summarises the static
gate as it was in 0.1.0: imports, classes, `global`/`nonlocal`, async and
generators, dunders, the banned builtins, "`def` and simple assignments at module
level", a size cap. Since 0008 the membrane also refuses attributes beginning
with `_`, `.format`/`.format_map`/`.mro`, attribute stores, `finally`, `with`,
`except*`, bare `except:`, `except` on anything but the six built-in exceptions
and any rebinding of those names, and non-constant values at module level; and
`random` inside a genome is the dish's own generator. `docs/membrane.md` states
all of it with the reason strings. The site page is not wrong, but a reader who
writes a founder from it will be surprised by `finally not allowed`.

## Proposal

Bring the page's "static gate" and "dynamic gate" sections in line with
`docs/membrane.md` (rules, `Lysis` as a `BaseException`, `random` being the dish
generator, the known limits), or link the page to it. The web toolchain runs under
`scripts/task check` for any change under `web/`, which is why 0008 did not touch
it: that gate needs `pnpm install` and a Chromium for the design package's browser
tests.

## Acceptance criteria

- [ ] The page names every rule `docs/membrane.md` names, or links to it for the list
- [ ] `TASK_SCOPE=all scripts/task check` is green
