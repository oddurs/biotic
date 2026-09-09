---
id: 10
title: 'Incubation gaps: record wall-clock absence, do not fake ticks'
type: feature
status: planned
milestone: dish
depends_on:
- 7
created: 2026-09-08
updated: 2026-09-08
priority: p2
effort: s
area: bio/culture.py
---

## Problem

`biotic live` after 12 hours away resumes at the tick it left. That is correct —
a dish in the freezer does not grow — but the curve and notes should say so,
and the naturalist should not describe a 12-hour gap as "since the last note".

## Proposal

- `Culture.load` compares `state.saved_at` to now; if the gap exceeds 10 minutes
  it logs `incubation resumed after 12h 04m` and writes a marker row to the curve.
- The observation packet for the naturalist includes the gap.
- `biotic status` shows `last active`.

## Acceptance criteria

- [ ] A resumed dish logs the gap once
- [ ] `biotic curve` shows the gap marker
