---
id: 25
title: Staged substrates and the `secrete` action
type: feature
status: planned
milestone: secretions
created: 2026-09-08
updated: 2026-09-08
priority: p0
effort: l
area: bio/substrates.py, bio/dish.py
---

## Problem

A substrate is one question with one answer; nothing can be done to it
partially and left for someone else.

## Proposal

- `Substrate` gains optional `stages: list[Stage]`, each with its own
  `sample → intermediate` semantics and `score`. A staged substrate is digested
  by producing the final answer *or* by producing a valid intermediate.
- Action `("secrete", value)`: score `value` as an intermediate for the tile's
  substrate; if ≥ 0.6, place it on the tile as `intermediates[y][x] = (stage,
  value, secretor_strain, tick)` and pay the secretor a small immediate yield
  (0.3 × stage yield). Intermediates decay after 200 ticks.
- `me.intermediate` → `(stage, value)` if one is present. `("digest", answer)`
  on a tile with an intermediate is scored *from that stage onward* and pays
  the digester the remaining yield. The secretor is *not* paid again — that is
  what makes it a public good, and cheaters possible.
- Two staged built-ins: **order** becomes 2-stage (partition around a pivot →
  sort); a new **compose** substrate — evaluate a small arithmetic expression
  tree given as nested lists, staged by depth.
- `Strain` records `secretes` / `consumes` counts per (substrate, stage).

## Acceptance criteria

- [ ] A fixture pair of genomes — one that only secretes stage 1, one that only digests from stage 1 — together clear a staged substrate that neither clears alone
- [ ] Intermediates decay; provenance is stored
- [ ] Energy accounting: total yield of a staged digestion by two cells ≤ yield of one perfect digestion
