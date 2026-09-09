---
id: 32
title: Heritable mutator traits
type: feature
status: planned
milestone: transitions
depends_on:
- 15
created: 2026-09-08
updated: 2026-09-08
priority: p2
effort: m
area: bio/strains.py, bio/mutagen.py
---

## Problem

Mutation rate, temperature, and which model does the mutating are global
knobs. In biology they are traits, and their evolution is one of the clearest
results from long-term experiments.

## Proposal

- `Strain` gains `mutator: {rate_mult: float, temperature: float, model: str}`
  inherited from the parent with a small chance of its own perturbation on
  each new strain (rate_mult ×/÷ 1.5, temperature ±0.15, model from
  `BIOTIC_MODELS` list).
- `_on_divide` uses the strain's `rate_mult`; the mutagen uses the strain's
  temperature and model. Budget accounting per model.
- Census shows `μ×1.5` when a strain's rate differs from baseline. Curve:
  population-weighted mean `rate_mult`.

## Acceptance criteria

- [ ] Traits inherit and drift; visible in `biotic strains`
- [ ] A run shows a measurable change in mean rate over 20k ticks (either direction; record it)
