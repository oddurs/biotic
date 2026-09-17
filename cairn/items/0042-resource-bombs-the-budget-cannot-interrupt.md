---
id: 42
title: Resource bombs the budget cannot interrupt
type: bug
status: done
milestone: dish
assignee: Oddur Sigurdsson
created: 2026-09-08
updated: 2026-09-16
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

- [x] A genome that runs `sum(range(10**12))` only after tick 40 cannot stall the dish for more than a bounded time
- [x] The smoke test's child cannot exhaust memory
- [x] A test in `tests/test_membrane.py` demonstrates each

## 2026-09-16

From 0043: the me.memory check the dish runs after every live() (membrane.memory_fault) is O(MEMORY_MAX_CHARS) per cell, not O(memory): its walk stops as soon as a lower bound on the JSON length passes the cap, and json.dumps only runs on a memory the walk has already bounded. A 10**9-leaf list DAG is refused in ~7 us. It cannot itself be made to stall; no need to re-measure it here.

## 2026-09-16

Reverted the interrupted attempt (bio/incubator.py, SIGPROF CELL_HARD_CEILING process-kill + journal + supervise() fork of live/run, config.py/dish.py/tui.py plumbing). That is the 'watchdog that kills the process too blunt' approach the item rules out, it modified guarded config.py, added per-tick cost, and never added the static bans. Implemented the reviewed plan instead: static AST bans in inspect + RLIMIT_AS/CPU in the isolated child.

## 2026-09-16

Pow rule bans on the exponent only, never the base: 2**me.age (non-constant) and 2**10**9 (oversized constant) are refused, but x**0.5, energy**2 and 2**1000 pass. Fixed a flaw in the original plan that folded float exponents to None and would have banned x**0.5 — which _screen/revive re-run inspect on thaw, so it would silently lyse a live sqrt-idiom strain on reload.

## 2026-09-16

Mult repeat rule guards on _is_const_expr(count) before folding, so a non-constant multiplier ([0]*len(me.around), [0]*me.age) is a documented residual that passes, while a constant one that folds huge or refuses ([0]*10**10, [0]*(10**10*10**10)) is banned. _fold_number is a manual recursive descent (no eval/compile/literal_eval), bounded so it cannot detonate.

## 2026-09-16

rlimits are set inside the child (_limit_resources at top of __main__), not via subprocess preexec_fn: preexec_fn runs in a fork of the multithreaded mutagen and can deadlock on fork+threads. RLIMIT_AS/DATA=2GiB is best-effort (macOS refuses to lower below an infinite hard limit; CI is ubuntu so it is real there); RLIMIT_CPU=15s works on both, under admit_isolated's 20s wall timeout.

## 2026-09-16

Review fix: Pow branch banned only when _fold_number(exp) was an int > POW_MAX_EXP, but an oversized const exponent (2**10**19) folds to None past _FOLD_CAP and escaped; now bans on 'v is None or int>cap', mirroring the range/repeat branches. To keep None meaning 'oversized/unrepresentable' and not 'benign but unfoldable', _fold_number now carries / // % and float ** too, so x**(1/2) folds to 0.5 and stays admitted (the thaw re-inspect must not lyse a sqrt idiom).

## 2026-09-16

Review fix: chained repeat ([0]*1000*1000*1000) escaped because the outer Mult saw a BinOp on both sides; _mult_factors now flattens the Mult chain and the rule bans on the product of all constant factors against MAX_LITERAL_COUNT. Range now folds all bounds and bans on the actual len(range(*args)), so a negative-step form (range(0,-10**12,-1)) is caught like range(10**12); a bound past _FOLD_CAP is oversized. Added reject rows + tick-guard params (pow/repeat/range) and positive controls (division exponent, chained runtime multiplier, high-numbered short range window).

## 2026-09-16

Rebase onto main (0043's me.memory bound) collided with this branch's Pow rule: the int case of MEMORY_FAULTS built its oversized memory with 10 ** 5000, which the new static gate now refuses as a resource bomb (exp > POW_MAX_EXP=1024). Rewrote that genome to 10 ** 1000 * 10 ** 1000 * 10 ** 1000 (each exponent under the cap, product 10**3000) so the memory_fault path is still exercised through a form the gate admits. Merged docs/README/prompts to carry both the me.memory bound and the resource-bomb rules.
