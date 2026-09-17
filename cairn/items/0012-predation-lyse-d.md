---
id: 12
title: 'Predation: `("lyse", d)`'
type: feature
status: done
milestone: biotic-env
assignee: Oddur Sigurdsson
created: 2026-09-08
updated: 2026-09-16
priority: p0
effort: m
area: bio/dish.py, bio/prompts.py
---

## Problem

Cells cannot act on each other. Without predation there is no reason to evolve
speed, armour, toxicity, flocking, or avoidance — half the phenotypes in a real
dish.

## Proposal

- Action `("lyse", d)`: if neighbour `d` is a cell of a *different* strain, the
  attacker pays `LYSE_COST` (0.05); with probability `p = sigmoid(k · (E_att −
  E_def))` the defender bursts and the attacker gains `LYSE_YIELD × E_def`
  (0.6); otherwise the attacker takes `LYSE_RECOIL` (0.03). Kin cannot be lysed
  (returns silently; that is `kin` earning its keep).
- Death cause `"predated"`, counted separately.
- `me` gains `me.threat`: 8 floats, energy of each neighbour (0 if empty or kin)
  — the perceptual basis for fleeing. Nothing else about neighbours is exposed.
- Prompt (`CELL_API`) documents the action, the odds, and `me.threat`.
- Off by default for existing dishes (`dish.features = {"lyse": False}` stored
  in `dish.json`); `biotic seed --with lyse,give,hgt` or `biotic drop feature
  lyse` enables mid-run and logs it as an intervention.

## Acceptance criteria

- [x] A genome that always lyses is admitted, and in a mixed dish produces `predated` deaths
- [x] Kin are never lysed
- [x] Enabling mid-run is logged and marked on the curve
- [x] Vitals show predation deaths; census unaffected in format

## 2026-09-16

_FakeMe (bio/membrane.py) must expose me.threat, or a genome reading it is refused by the smoke test — directly failing 'a lyser is admitted'. Added self.threat to _FakeMe.__init__ and refreshed it per smoke round; it is a plain float list so it passes the static gate.

## 2026-09-16

germinate ordering: features are validated before any destructive step (so a typo never autoclaves) and enable_feature() runs after cult=cls(...) but before _genesis(), so the founding prompt documents lyse when seeded --with lyse. enable_feature logs the tick-0 drop marker itself.

## 2026-09-16

predated appended at the very END of curve.COLUMNS (append-only invariant). This broke test_metrics widening tests that assumed a 19-col file gains exactly the 2 supply cols and full-width hand rows — updated them to expect predated too; not flagged in the plan.

## 2026-09-16

LYSE_K=2.0: energies are 0..MAX_ENERGY(2.0) so the sigmoid arg is bounded ±4, giving p in ~0.02..0.98 — always a chance either way and no exp overflow. Sigmoid uses pre-cost energies (what the genome perceived).

## 2026-09-16

plot.LABELS needs a predated entry: PLOTTABLE derives from COLUMNS so predated becomes plottable automatically, and test_plot pins set(LABELS)==set(PLOTTABLE); biotic curve --cols predated would KeyError without it.
