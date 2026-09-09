---
id: 6
title: 'Replicate flasks: many dishes from one install'
type: feature
status: planned
milestone: dish
depends_on:
- 4
created: 2026-09-08
updated: 2026-09-08
priority: p1
effort: m
area: bio/config.py, bio/culture.py
---

## Problem

Every path is hardcoded to `vessel/` and `soma/`. One experiment per checkout.
The whole methodology of the field is replication — Lenski has twelve flasks,
and the citrate result means something *because* eleven flasks did not do it.

## Proposal

- `BIOTIC_VESSEL=<dir>` and `--vessel <dir>` on every command. `soma/` moves
  inside the vessel (`<vessel>/soma/`) so a flask is one directory. The root
  `soma/` becomes a symlink to the default vessel's, or is dropped from the
  README in favour of `<vessel>/soma`. Decide and record here.
- `biotic flasks new <name> --seed "…" [--n 12]` creates `flasks/<name>/{01..12}/`,
  each seeded identically (same seed → same agar; different `flask_id` mixed into
  the culture RNG so they diverge — like real replicates).
- `biotic flasks run <name> --ticks N [--tick 0] [--parallel 4]` runs them
  headless as subprocesses; `biotic flasks curve <name>` overlays their curves.
- `biotic live --vessel flasks/x/03` watches one.

## Acceptance criteria

- [ ] Two vessels run simultaneously in one checkout without touching each other's files
- [ ] `flasks new tide --n 3` produces three dishes with identical agar and different trajectories
- [ ] `flasks curve` overlays population for all replicates on one plot
- [ ] README updated for the vessel layout
