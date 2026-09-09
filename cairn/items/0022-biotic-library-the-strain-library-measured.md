---
id: 22
title: '`biotic library` — the strain library, measured'
type: feature
status: planned
milestone: substrates
depends_on:
- 19
created: 2026-09-08
updated: 2026-09-08
priority: p0
effort: m
area: bio/__main__.py, bio/culture.py
---

## Problem

Once strains digest substrates, `soma/` contains working programs — but
nobody can tell which ones work on what without reading them. The library
needs measuring, not describing.

## Proposal

- `biotic library [--substrate X] [--extinct] [--min 0.5]`: for each strain,
  run its genome in a *trial dish* saturated with each substrate (same harness
  as the founder trial) for 300 ticks and report mean score per substrate,
  alongside the in-vivo diet stats. Cache results in `vessel/library.json`
  keyed by genome hash.
- Output: a table sorted by best score; `--json` for tooling.
- `biotic library export <substrate> <dir>` writes the top-N genomes for a
  substrate as standalone modules with a tiny `solve(sample)` shim that builds
  a `Me`-like object and calls `live()` — so a grown pathway can be imported
  by something that is not a dish. This is the moment the output is software.
- Fossil headers gain the measured diet line.

## Acceptance criteria

- [ ] `biotic library` ranks strains per substrate with measured scores
- [ ] `export` produces an importable module whose `solve()` reproduces the trial score within noise
- [ ] Results cached; re-running is instant for unchanged genomes
