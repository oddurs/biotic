---
id: 42
title: Resource bombs the budget cannot interrupt
type: bug
status: backlog
milestone: dish
created: 2026-09-08
updated: 2026-09-08
priority: p1
area: bio/membrane.py
---

## Problem

The cell time budget is a SIGALRM raised between bytecodes. A single C-level
operation — `sum(range(10**12))`, `2 ** 10**9`, `[0] * 10**10`, sorting an
enormous list — runs to completion before `Lysis` can be raised. The smoke test
catches a genome that does this within its forty rounds (in the isolated child
the 20 s ceiling kills it), but a genome that does it only later — after tick
40, or under a state the stand-in cell never produces — stalls `biotic live`
until the operation finishes. There is no memory cap at all. `docs/membrane.md`
states the limit; nothing enforces it.

## Proposal

Options, not exclusive: `RLIMIT_CPU` and `RLIMIT_AS` in the isolated child, so
at least the smoke test cannot be taken down; a longer, randomised smoke test
that covers more of the state space; banning `ast.Pow` with a non-constant
exponent and sequence repetition by a large constant in `inspect`; or a way to
pre-empt a genome inside the dish (a subprocess per tick is too slow, a
watchdog that kills the process too blunt). Measure the per-tick cost of
whatever is chosen; the dish runs at about 3 ms per tick on 72×34 today.

## Acceptance criteria

- [ ] A genome that runs `sum(range(10**12))` only after tick 40 cannot stall the dish for more than a bounded time
- [ ] The smoke test's child cannot exhaust memory
- [ ] A test in `tests/test_membrane.py` demonstrates each
