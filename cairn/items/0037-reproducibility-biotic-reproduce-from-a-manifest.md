---
id: 37
title: 'Reproducibility: `biotic reproduce` from a manifest'
type: feature
status: planned
milestone: instrument
depends_on:
- 6
created: 2026-09-08
updated: 2026-09-09
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

## 2026-09-09

From 0003/0045: mutations_ready samples a wall-clock pool and cannot reproduce under --replay-mutations; exclude it when asserting identical curves. phase is debounced in the process (last_phase is not persisted), so the earliest rows of a run and of every resume carry the raw reading: either resume the replay at the same ticks as the original or persist the debounce state alongside dish.json.

## 2026-09-09

From 0045's review: the identical-curve criterion has two more inputs besides mutations_ready. Drops arrive through vessel/inbox on the wall clock and change the agar, population and killed, and the mutation rate; replay them at their ticks from events.jsonl. And every live() runs under Budget(CELL_TIME_BUDGET), 0.004 s of wall clock, so a genome near the limit lyses on a slow machine and not on a fast one, and lysed, population and everything downstream follow. Either allow that tolerance or clock the budget in something deterministic before asserting identical curves. docs/curve.md states both.
