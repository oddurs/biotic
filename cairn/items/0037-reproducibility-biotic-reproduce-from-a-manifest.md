---
id: 37
title: 'Reproducibility: `biotic reproduce` from a manifest'
type: feature
status: planned
milestone: instrument
depends_on:
- 6
created: 2026-09-08
updated: 2026-09-08
priority: p0
effort: l
area: bio/config.py, bio/dish.py, bio/culture.py
---

## Problem

Determinism exists per dish (seeded RNG) but the mutagen is not
deterministic, and nothing records the full configuration of a run.

## Proposal

- `vessel/manifest.json` written at seed: seed text, chemistry recipe, every
  physics constant, features, mutagen config and model, biotic version,
  dish size. Updated on interventions (appended as a timeline).
- `biotic reproduce <manifest> [--vessel …]` seeds an identical dish. With
  `--replay-mutations` it also replays the exact sequence of admitted genomes
  from the original `strains.json` at the same ticks instead of calling the
  mind — so a run can be reproduced *exactly*, offline, at zero cost. That is
  the artefact a paper ships.
- Physics constants stop being module globals and become a `Physics`
  dataclass on the dish, loaded from the manifest, so an old run keeps its old
  physics after constants are retuned.

## Acceptance criteria

- [ ] `reproduce --replay-mutations` of a 20k-tick run yields identical curve.csv
- [ ] Changing a constant in config does not change a reproduced run
