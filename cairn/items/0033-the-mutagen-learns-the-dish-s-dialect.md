---
id: 33
title: The mutagen learns the dish's dialect
type: feature
status: planned
milestone: transitions
created: 2026-09-08
updated: 2026-09-08
priority: p2
effort: m
area: bio/mutagen.py, bio/prompts.py
---

## Problem

Every mutation prompt is written from scratch. The mutagen never learns what
has worked *in this dish*, so it re-proposes the same sensible moves.

## Proposal

- Cheap version first: the mutagen's context includes a *fossil digest* —
  the five strains with the highest peak that are now extinct (what failed,
  with their notes) and the five with the longest current tenure (what
  persists). Refreshed every 500 ticks. Kept under 1,500 tokens.
- Then: retrieval — pick the 3 fossils most similar to the parent (by
  difflib ratio) and show what happened to them.
- Deferred and recorded here, not built: fine-tuning a local model on
  survivors (ELM's third component). Requires the local backend; out of scope
  until someone has one.

## Acceptance criteria

- [ ] Fossil digest present in mutation prompts; token cost measured and recorded here
- [ ] A/B over 6+6 flasks: novelty rate and shannon with and without; result recorded
