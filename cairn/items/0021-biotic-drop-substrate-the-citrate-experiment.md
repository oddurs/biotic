---
id: 21
title: '`biotic drop substrate` — the citrate experiment'
type: feature
status: planned
milestone: substrates
depends_on:
- 5
- 6
- 19
created: 2026-09-08
updated: 2026-09-08
priority: p1
effort: m
area: bio/culture.py, bio/__main__.py
---

## Problem

The most famous result in experimental evolution is a substrate that sat
unused for 31,000 generations until a lineage learned to eat it. We can run
that in an evening — if a substrate can be introduced into a running dish.

## Proposal

- `biotic drop substrate <name> [--at x,y] [--r 8] [--params …]` lays a patch
  of a substrate, logged as a drop with a curve marker. `biotic drop substrate
  --everywhere <name> --share 0.2` converts a share of glucose tiles.
- Track *time to colonisation*: the first tick at which any strain digests the
  new substrate with score ≥ 0.5 for 50 consecutive ticks. Logged as
  `colonised sequence at tick N by <strain> (gen G)` — the headline event of
  the milestone — and the naturalist packet flags it.
- `biotic library` (next item) shows the colonising lineage.

## Acceptance criteria

- [ ] Dropping a substrate mid-run renders immediately and is marked on the curve
- [ ] Colonisation is detected and logged with strain and lineage
- [ ] Protocol recorded in this item: 6 flasks, drop `order` at tick 10k, freeze every 2k; report time-to-colonisation per flask and whether reviving the tick-8k freeze reproduces it
