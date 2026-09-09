---
id: 39
title: Documentation site and install path
type: docs
status: planned
milestone: instrument
depends_on:
- 37
created: 2026-09-08
updated: 2026-09-08
priority: p2
effort: m
area: docs/
---

## Problem

README.md and CONCEPT.md are enough for the author. An instrument needs a
manual: the cell API for people writing founders by hand, the physics with
every constant explained, the substrate catalogue, the CLI reference, and the
experiment protocols.

## Proposal

- `docs/` as plain Markdown, rendered with whatever the sibling repo setup
  chose (mkdocs or similar); pages: getting started, the dish, the cell API,
  chemistry, interventions, the freezer, flasks, the naturalist, CLI reference
  (generated from argparse), physics constants (generated from `Physics`).
- `pipx install biotic` / `uv tool install biotic` works from a tagged release.

## Acceptance criteria

- [ ] Every CLI command documented, generated not hand-written
- [ ] A fresh machine goes from install to a growing dish following only the docs
