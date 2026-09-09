---
id: 16
title: 'Experiment: does parasitism arise?'
type: docs
status: planned
milestone: biotic-env
depends_on:
- 5
- 6
- 12
- 13
- 14
- 15
created: 2026-09-08
updated: 2026-09-08
priority: p1
effort: l
area: experiments
---

## Problem

The first thing Tierra produced that nobody designed was a parasite. If the
biotic environment is real, something analogous should appear here: a strain
that never eats agar and lives by lysing, or by receiving from kin-mimics, or
one that splices donors' foraging code and drops its own. Whether it does is
the first real result this project can report, and it should be run as an
experiment, not noticed by accident.

## Proposal

A written protocol, executed, with results recorded *in this item*:

1. Six flasks, seed `"tide"`, features `lyse,give,hgt`, mutagen `mixed`,
   replenish default, 30,000 ticks each at `--tick 0`, budget $3 each.
2. Six control flasks: same, features off.
3. Freeze every 2,000 ticks.
4. Measure per flask: `shannon` over time, `arisen` slope in the last 10k
   ticks vs. the first 10k (is novelty decelerating?), share of `predated`
   deaths, and — by reading genomes — whether any living strain at the end has
   *no* `"eat"` path (an obligate predator or beggar).
5. Naturalist notes on for the treatment flasks; read them.
6. Write the result as a table in this item and a paragraph in CONCEPT.md's
   "honest risk" section, whichever way it comes out.

## Acceptance criteria

- [ ] Protocol run to completion (12 flasks × 30k ticks)
- [ ] Table of metrics per flask in this item
- [ ] A yes/no on obligate parasites, with the genome quoted if yes
- [ ] CONCEPT.md updated with the finding
