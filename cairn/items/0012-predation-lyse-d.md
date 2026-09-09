---
id: 12
title: 'Predation: `("lyse", d)`'
type: feature
status: planned
milestone: biotic-env
created: 2026-09-08
updated: 2026-09-08
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

- [ ] A genome that always lyses is admitted, and in a mixed dish produces `predated` deaths
- [ ] Kin are never lysed
- [ ] Enabling mid-run is logged and marked on the curve
- [ ] Vitals show predation deaths; census unaffected in format
