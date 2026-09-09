---
id: 30
title: 'Colony primitives: shared memory among adjacent kin'
type: feature
status: planned
milestone: transitions
created: 2026-09-08
updated: 2026-09-08
priority: p1
effort: m
area: bio/dish.py
---

## Problem

Multicellularity needs a way for adjacent kin to act as one: shared state,
and something that makes staying together pay.

## Proposal

- `me.colony`: a dict shared by the connected component of adjacent kin
  (recomputed each tick by flood fill over `kin`; cached by component id).
  Writes are visible to all members next tick. Capped at 32 keys.
- `me.colony_size`.
- A staged substrate whose stage 1 intermediate is only usable by the *same
  colony* (an "intracellular" intermediate) — so pipelines inside a colony are
  cheaper than pipelines across strangers. That is the selective advantage.
- Curve columns: `colonies`, `largest_colony`, `mean_colony`.

## Acceptance criteria

- [ ] Component computation stays under 5 ms for 2,000 cells
- [ ] A fixture genome using `me.colony` to coordinate direction moves as a block
- [ ] Curve reports colony statistics
