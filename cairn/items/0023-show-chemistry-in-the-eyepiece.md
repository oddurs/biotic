---
id: 23
title: Show chemistry in the eyepiece
type: feature
status: planned
milestone: substrates
depends_on:
- 18
created: 2026-09-08
updated: 2026-09-08
priority: p1
effort: s
area: bio/tui.py
---

## Problem

Substrate patches, per-substrate uptake, and colonisation events need to be
visible or the milestone is invisible.

## Proposal

- Agar rendering: substrate tiles use the substrate's glyph (`~` sequence,
  `≡` order, `¤` pattern) tinted by its hue, intensity by richness.
- Vitals: one row per substrate — share of agar, cells currently digesting it,
  mean score last 100 ticks, colonised-by.
- Census: a diet column, e.g. `seq 0.9 · ord 0.1`.
- A legend line under the agar panel.

## Acceptance criteria

- [ ] Patches are distinguishable at a glance from glucose and from each other
- [ ] Per-substrate rows appear only for substrates present
- [ ] Colonisation shows as a highlighted log line
