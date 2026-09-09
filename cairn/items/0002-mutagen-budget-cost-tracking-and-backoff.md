---
id: 2
title: Mutagen budget, cost tracking and backoff
type: feature
status: planned
milestone: dish
created: 2026-09-08
updated: 2026-09-08
priority: p0
effort: m
area: bio/mind.py, bio/mutagen.py
---

## Problem

A week-long run is the point of the project, and today nothing bounds what it
costs. `Mind` counts tokens but not money, a failing endpoint is retried every
15 seconds forever, and a rate-limit (HTTP 429) is treated like any other error.
Nobody will leave this running overnight until the worst case is a number.

## Proposal

- `Mind` learns prices. On first use, fetch `/models` once and cache
  `{model: (prompt_usd_per_tok, completion_usd_per_tok)}` in `vessel/prices.json`.
  Expose `mind.spent_usd`. If the endpoint has no pricing (local), spent is 0.
- `BIOTIC_BUDGET_USD` (default 2.00 per dish, persisted into `dish.json` so a
  resumed run remembers). When exceeded the mutagen goes `state = "exhausted"`,
  logs one event, and the dish keeps running without variation. `biotic status`
  and the vitals panel show `$0.43 / $2.00`.
- Exponential backoff on `MindError`: 15s, 30s, 60s … capped at 10 minutes, reset
  on success. On 429 specifically, honour `Retry-After` if present.
- `biotic run --budget 0.50` and `biotic seed --budget` override per dish.

## Acceptance criteria

- [ ] `vessel/prices.json` written after the first call; `spent_usd` grows with each call
- [ ] A dish with `BIOTIC_BUDGET_USD=0.01` stops mutating after the first call, logs `mutagen exhausted`, and the culture keeps growing
- [ ] A dead endpoint produces at most ~10 error events in the first hour, not 240
- [ ] `biotic status` prints spent / budget
