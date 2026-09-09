---
id: 44
title: A per-cell generator derived from the dish rng
type: chore
status: backlog
milestone: dish
created: 2026-09-08
updated: 2026-09-08
priority: p3
area: bio/dish.py
---

## Problem

`random` and `me.rng` inside a genome are the dish's own generator. That is what
makes a culture reproducible, but one genome that calls `random.seed(...)`, or
simply draws an unusual number of values, perturbs the randomness every other
cell sees and the dish's own shuffles. The run stays deterministic; it is just
no longer independent of one strain's appetite for random numbers.

## Proposal

Give each cell a `random.Random` seeded from the dish rng at birth, stored on the
cell so it survives a save, and hand that to the genome as both `me.rng` and
`random`. Cost: one generator per cell, about 2.5 KB of state each, so a larger
`dish.json`. Only worth doing if a replay (0037) ever shows a divergence that
traces back to one strain's draws.

## Acceptance criteria

- [ ] Reseeding `random` inside one strain does not change another strain's draws
- [ ] The exact-twin test still passes with per-cell generators serialised
