---
id: 5
title: 'The freezer: `biotic freeze` and `biotic revive`'
type: feature
status: planned
milestone: dish
created: 2026-09-08
updated: 2026-09-08
priority: p0
effort: m
area: bio/culture.py, bio/__main__.py
---

## Problem

Lenski's experiment is possible because every 500 generations a sample goes in
the freezer, and any question about contingency — would this have happened
again? — is answered by thawing an ancestor and replaying. We serialise the
dish every 150 ticks but overwrite it, so the past is gone. Without a freezer
there is no replay, and without replay there is no experiment.

## Proposal

- `vessel/freezer/<tick>.json.gz` — a full dish snapshot (cells, agar, pheromone,
  RNG state, genomes) plus the strains registry at that moment. Automatic every
  `BIOTIC_FREEZE_EVERY` ticks (default 2000); manual with `biotic freeze [--label]`.
- `biotic freeze --strain <id>` — a *strain* sample: the genome plus one cell's
  memory, as `vessel/freezer/strain-<id>.json`.
- `biotic revive <tick>` — replace the current dish with the snapshot (after
  confirming; the current dish is itself frozen first as `pre-revive`). The
  events log gets a `revived from tick N` entry and the curve gets a marker.
- `biotic revive --strain <id> [--into fresh|current] [--n 5]` — inoculate a
  strain sample into a fresh dish (same seed, so same agar) or drop it into the
  running one as an invader.
- `biotic freezer` lists what is frozen with tick, label, population, strains.
- Snapshots are gzipped; a 72×34 dish is ~100KB compressed.

## Acceptance criteria

- [ ] Automatic snapshots appear at the configured cadence; the freezer listing shows them
- [ ] `revive <tick>` restores a dish whose next 100 ticks match a run that never left that state (same RNG state → identical trajectory)
- [ ] `revive --strain` into a fresh dish grows (or does not) and the log says which
- [ ] Reviving records the event and a curve marker
