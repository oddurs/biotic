---
id: 13
title: 'Sharing: `("give", d, x)`'
type: feature
status: done
milestone: biotic-env
assignee: Oddur Sigurdsson
depends_on:
- 12
created: 2026-09-08
updated: 2026-09-16
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

- [x] Energy is conserved minus the documented loss
- [x] A "give to kin below 0.3" genome keeps a starving cluster alive longer than a control (test with fixed seeds)
- [x] `given`/`received` appear in curve columns

## 2026-09-16

Adding a NEW perception me.neighbor_energy (energy of every occupied neighbour, KIN INCLUDED, 0.0 for empty/glass) rather than renaming me.threat as the item's proposal suggested. Me.__init__ zeroes threat on kin, so threat cannot serve criterion 2's give-to-kin; renaming would also break shipped lyse and the byte-pinned genesis/mutagen prompts.

## 2026-09-16

given/received tracked as dish-wide cumulative floats (Dish.given, Dish.received) and surfaced as two curve columns after 'predated', not per-strain. curve.csv is a fixed scalar schema; this matches births/predated. 'given' is gross energy leaving givers, 'received' is net arriving at recipients, so given-received is the heat lost.

## 2026-09-16

parse_action: give is the only 3-element action, so the tuple/list guard widens to 1<=len<=3 with its own try-branch before the shared one; a required amount (a bare ('give', d) is None), coerced+clamped to 0..MAX_ENERGY; any other 3-element form returns None so ('move',1,2) stays rejected. Added 'share' alias.

## 2026-09-16

_FakeMe._neighbor_energy multiplies each around value by MAX_ENERGY and the crowd bool (no rng draw), unlike _threat which rolls per tile. Zero draws keeps membrane admission byte-for-byte, so shipped genomes still admit identically.

## 2026-09-16

crit2 test pinned K=15 empirically: control's poor cells (0.12 on basal 0.01) starve by tick 13; the poorest giver cell holds ~0.33 at K=15, far above reserve. Both dishes share one seed and gifts touch no rng, so shuffle order stays in lockstep; assert control starved>=1, giver starved==0, giver live>control. A feature-off guard test proves survival is the gift, not the layout.
