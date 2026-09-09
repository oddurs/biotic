---
id: 34
title: The naturalist recognises transitions
type: feature
status: planned
milestone: transitions
depends_on:
- 7
- 30
created: 2026-09-08
updated: 2026-09-08
priority: p2
effort: m
area: bio/culture.py
---

## Problem

The naturalist describes what it is shown. Colonies, plasmid sweeps, and
mutator emergence are only visible if the observation packet computes them.

## Proposal

- Detectors in `Culture`, each producing a structured `observation` event when
  it fires: sweep (dominance +0.4 in 500 ticks), cascade (≥3 extinctions in
  100 ticks), colonisation (from substrates), colony formation (largest colony
  ≥ 12 for 300 ticks), plasmid sweep (prevalence +0.3 in 500 ticks), mutator
  rise (mean rate_mult > 2).
- Observations go in the packet; the naturalist is asked to address them
  explicitly. `biotic notes --observations` lists the structured ones.

## Acceptance criteria

- [ ] Each detector has a unit test on synthetic histories
- [ ] A note following a detected sweep names the strain
