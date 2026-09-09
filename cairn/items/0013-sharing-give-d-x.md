---
id: 13
title: 'Sharing: `("give", d, x)`'
type: feature
status: planned
milestone: biotic-env
depends_on:
- 12
created: 2026-09-08
updated: 2026-09-08
priority: p1
effort: s
area: bio/dish.py
---

## Problem

Cooperation, cheating and kin selection — the richest dynamics in
microbiology — need a way to transfer energy voluntarily. Division is the
only transfer that exists, and it is not voluntary in the relevant sense.

## Proposal

- Action `("give", d, x)`: move `min(x, E − 0.05)` energy to neighbour `d` if
  occupied (any strain — giving to non-kin is what makes cheating possible).
  Transfer efficiency `GIVE_EFFICIENCY` 0.9; the loss is heat.
- Track per-strain `given` / `received` totals per curve interval in
  `metrics()` so altruism and cheating are measurable, not anecdotal.
- `me.kin` already exists; `me.threat` (from lyse) doubles as "how hungry is
  that neighbour" when read as neighbour energy. Rename to `me.neighbor_energy`
  and keep `threat` as an alias in the prompt only if lyse is enabled.
- Feature flag as in lyse.

## Acceptance criteria

- [ ] Energy is conserved minus the documented loss
- [ ] A "give to kin below 0.3" genome keeps a starving cluster alive longer than a control (test with fixed seeds)
- [ ] `given`/`received` appear in curve columns
