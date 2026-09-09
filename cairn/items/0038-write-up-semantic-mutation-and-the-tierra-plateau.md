---
id: 38
title: 'Write-up: semantic mutation and the Tierra plateau'
type: docs
status: planned
milestone: instrument
depends_on:
- 15
- 16
- 28
- 37
created: 2026-09-08
updated: 2026-09-08
priority: p1
effort: xl
area: docs/
---

## Problem

The project's claim is a hypothesis. By this point the instrument can test it.
Whatever the answer, it should be written down with the data, because the
empty quadrant in CONCEPT.md is only interesting if someone reports what is
in it.

## Proposal

`docs/paper.md` (and a rendered PDF): question, apparatus, protocol (12 + 12
flasks per condition: llm / random / mixed, features on, 50k ticks), metrics
(shannon, arisen slope over time, parasitism, colonisation times, pipeline
emergence), results with figures from `biotic curve --png` and `flasks curve`,
the canalisation risk addressed head-on, limitations (one model, one physics,
small dishes), and what to try next. Manifests and freezer archives published
alongside so anyone can `biotic reproduce`.

## Acceptance criteria

- [ ] Protocol run to completion
- [ ] Paper with figures, manifests linked
- [ ] CONCEPT.md's "honest risk" section replaced with what was found
