---
id: 4
title: '`biotic curve` — plot a run'
type: feature
status: planned
milestone: dish
depends_on:
- 3
created: 2026-09-08
updated: 2026-09-16
priority: p1
effort: m
area: bio/__main__.py
---

## Problem

The growth curve is the primary output of an experiment and there is no way to
look at it except opening a CSV. A microbiologist reads the plate *and* the
curve.

## Proposal

`biotic curve [--png out.png] [--cols population,shannon,nutrient] [--since TICK]`

- Default: an ASCII plot in the terminal using `rich` — population as the main
  trace, strain count as a second axis, phase transitions marked as vertical
  ticks with labels (lag / log / stationary / death), interventions marked with
  the drop glyph.
- `--png` renders the same with matplotlib *if installed* (optional dependency
  group `[plot]` in pyproject; do not make it a hard requirement — the organism
  stays a one-dependency thing).
- Reads `vessel/curve.csv` and `vessel/events.jsonl` (for phase and drop markers).

## Acceptance criteria

- [ ] `biotic curve` on the current dish prints a plot with phase markers
- [ ] `biotic curve --png` produces a file when matplotlib is present and says how to install it when not
- [ ] Works on a curve with 50 rows and with 50,000 rows (downsamples)

## 2026-09-09

From 0003/0045: read the curve through bio.curve.read(path); rows from a nine-column file carry None in the new columns. Markers (drops, phase changes, extinctions, incubation gaps) come from events.jsonl joined on tick, not from curve columns. docs/curve.md names dominance as the Berger-Parker index and defines mean_gen as lineage depth; use those words in axis labels.

## 2026-09-16

From 0005: after a dish revive, join events on (branch, tick), not on tick; the curve's branch column is 0 until the first revive and one more after each, and an event's branch is the number of revived dish events (the ones with from and was) before it in events.jsonl. The earlier advice to split the file where tick decreases is withdrawn: a forward revive leaves tick monotone. A plot is per branch, or of the last branch by default; rows from a file older than the column read None there and are branch 0.
