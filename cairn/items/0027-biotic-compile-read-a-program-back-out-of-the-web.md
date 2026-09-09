---
id: 27
title: '`biotic compile` — read a program back out of the web'
type: feature
status: planned
milestone: secretions
depends_on:
- 22
- 26
created: 2026-09-08
updated: 2026-09-08
priority: p0
effort: m
area: bio/__main__.py
---

## Problem

The pipeline exists in the dish as a pattern of who eats what. It is not yet
a program anybody can run outside the dish.

## Proposal

- `biotic compile <substrate> [--out module.py]`: from the trophic web pick,
  per stage, the strain with the highest measured score (library trial) that
  actually participates in the web; emit one module containing each stage's
  `live()` renamed `stage_1`, `stage_2`, …, the `Me` shim, and a `solve(sample)`
  that threads a sample through the stages exactly as the dish would (feeding
  each stage's output as the next stage's `me.intermediate`).
- Header comment: the seed, the tick, the strains and their lineages, and the
  measured end-to-end score. This header is the provenance the whole project
  has been building toward: *this program was grown from "tide" over 41,000
  ticks by these lineages*.
- `biotic compile --all` writes one module per substrate into `vessel/compiled/`
  and a `README.md` index.

## Acceptance criteria

- [ ] Compiled module's `solve()` matches the dish's end-to-end score within noise on 200 fresh samples
- [ ] Header carries provenance
- [ ] Compiling a substrate no chain has solved says so instead of emitting a broken module
