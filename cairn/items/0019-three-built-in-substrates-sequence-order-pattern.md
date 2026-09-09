---
id: 19
title: 'Three built-in substrates: sequence, order, pattern'
type: feature
status: planned
milestone: substrates
depends_on:
- 18
created: 2026-09-08
updated: 2026-09-08
priority: p0
effort: m
area: bio/substrates.py
---

## Problem

The abstraction needs concrete chemistry, chosen so that (a) a 30-line
`live()` can plausibly evolve a partial solution, (b) partial credit is
meaningful, (c) the tasks are different enough to produce specialists.

## Proposal

- **sequence** — predict the next value. Sample: 6 floats from a family
  (arithmetic, geometric, sine with noise, random walk); answer: one float.
  Score: `max(0, 1 − |err| / scale)`. This is the "tide" substrate.
- **order** — sort. Sample: 4–7 small ints; answer: the list ascending.
  Score: fraction of adjacent pairs in order (partial credit for partial sorts).
- **pattern** — classify a short string against a hidden rule per patch
  (contains `"ab"`, length even, starts with vowel, …). Sample: a string of
  3–8 lowercase letters; answer: `True`/`False`. Score: 1 or 0 — but the rule
  is *per patch*, so a strain must use `me.memory` to learn it from feedback,
  and `me.last_score` is exposed for exactly this reason.
- Add `me.last_score` (score of the previous digest, or `None`) to `Me`.
- Each substrate has a one-line description for the prompt and a hue.

## Acceptance criteria

- [ ] Each substrate has a unit test: perfect answer → 1.0, empty → 0.0, garbage never raises
- [ ] A genome per substrate exists in `tests/fixtures/` that scores > 0.8 (proves each is solvable inside the membrane)
- [ ] `me.last_score` round-trips through persistence
