---
id: 8
title: Membrane and physics test suite
type: chore
status: planned
milestone: dish
created: 2026-09-08
updated: 2026-09-08
priority: p0
effort: m
area: tests/
---

## Problem

The membrane is the security boundary — genomes are untrusted code from a model
running on the user's machine — and its guarantees are asserted by nothing but
a smoke run. The physics has been tuned by eye. Both will be changed repeatedly
in the next milestones and need a floor.

## Proposal

`tests/` (pytest, run via `scripts/task check`):

- **membrane, negative:** for each escape class one genome that must be
  rejected: `import`, `__class__`/`__subclasses__`, `getattr`, `open`, `eval`,
  module-level call, class definition, generator, `while True`, a 3 MB source,
  a recursion bomb, `me.rng.__dict__`. Assert the reason string names the class.
- **membrane, positive:** the fallback founder and every strain in a fixture
  set of real evolved genomes (copy 10 from a run into `tests/fixtures/genomes/`)
  are admitted.
- **membrane, isolation:** `admit_isolated` on a genome that busy-loops returns
  "too slow" within the timeout and leaves no child process.
- **parse_action:** table test of every accepted form and a fuzz over random
  Python values asserting it returns a tuple or `None`, never raises.
- **physics:** a closed dish (`replenish=0`) with the fallback founder shows lag →
  log → death; a replenished one reaches a stationary population within ±30%
  of the analytic carrying capacity (replenish × tiles / basal). Deterministic
  under a fixed seed: two runs of 500 ticks produce identical census.
- **persistence:** `Dish.to_dict → from_dict` round-trips and the next 50 ticks
  are identical to an un-serialised twin (RNG state included).

## Acceptance criteria

- [ ] `pytest` passes in under 30 s
- [ ] Every escape class above has a test
- [ ] Determinism test exists and passes
