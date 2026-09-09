---
id: 31
title: 'Plasmids: heritable code that travels separately'
type: feature
status: planned
milestone: transitions
depends_on:
- 14
created: 2026-09-08
updated: 2026-09-08
priority: p2
effort: l
area: bio/dish.py, bio/mutagen.py
---

## Problem

HGT splices genes into the genome. Real plasmids are different: a separate
unit, copied at division, transferred by contact independent of division,
sometimes lost, sometimes selfish. They are how a trait can sweep a whole
community across strains in a few hundred ticks.

## Proposal

- A cell may carry one plasmid: a source string defining `plasmid(me)` that
  returns an action *or* `None`. If it returns an action, it overrides `live()`
  this tick. Cost `PLASMID_UPKEEP` 0.003/tick. Membrane applies.
- Copied to daughters with probability 0.95 (segregational loss). Transferred
  to an adjacent non-kin cell with probability 0.02/tick if the recipient has
  none (conjugation). The mutagen mutates plasmids as it does genomes, rarer.
- Plasmids have ids and a registry like strains; `biotic plasmids` shows
  prevalence by host strain. Rendered as a ring around the cell glyph? No — a
  brighter glyph (`◉`) suffices.
- How do plasmids arise? The mutagen, on a mutation roll, with p=0.05, is asked
  for a plasmid instead of a genome: "a small behaviour that could benefit any
  host". That is the only origin.

## Acceptance criteria

- [ ] A plasmid that says "give to kin when full" spreads across two strains that never splice
- [ ] Segregational loss and conjugation are measurable in `biotic plasmids`
- [ ] Membrane and time budget cover plasmid code
