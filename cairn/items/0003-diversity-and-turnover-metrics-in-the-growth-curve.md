---
id: 3
title: Diversity and turnover metrics in the growth curve
type: feature
status: planned
milestone: dish
created: 2026-09-08
updated: 2026-09-08
priority: p0
effort: s
area: bio/dish.py, bio/culture.py
---

## Problem

`curve.csv` records population and strain count. Neither can answer the
project's central question — is novelty ongoing or does the dish converge? —
because ten strains at 1 cell each and one strain at 90% look identical in
`strains`. The research claim in CONCEPT.md needs diversity, dominance and
turnover, sampled at the same cadence as everything else.

## Proposal

Add columns to `vessel/curve.csv` every 10 ticks:

- `shannon` — Shannon diversity over the strain census, in nats
- `dominance` — share of the most common strain
- `mean_gen` — mean generation of living cells (how deep the lineage runs)
- `arisen` — cumulative strains ever created (novelty rate = its slope)
- `extinct` — cumulative extinctions
- `pheromone` — mean pheromone over the agar (are they signalling at all)
- `mutations_ready`, `mutations_taken` — supply vs. uptake of variants

Keep the header backward compatible: new columns appended, existing order kept.
`Dish` gets a `metrics()` method that returns the dict; `Culture._curve` writes it.
Show `shannon` and `dominance` in the vitals panel.

## Acceptance criteria

- [ ] `curve.csv` has the new columns and an old file is still readable by `biotic curve`
- [ ] A monoculture reports `shannon=0.0, dominance=1.0`
- [ ] Vitals panel shows diversity next to the strain count
