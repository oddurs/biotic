---
id: 8
title: Membrane and physics test suite
type: chore
status: done
milestone: dish
assignee: Oddur Sigurdsson
created: 2026-09-08
updated: 2026-09-09
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

- [x] `pytest` passes in under 30 s
- [x] Every escape class above has a test
- [x] Determinism test exists and passes

## 2026-09-08

Red first: on main before the fixes these tests failed — random._os admitted (A); bare except, except Exception swallowing Lysis, Lysis being an Exception (B); the Exception.mro()[1] route to BaseException; .format/.format_map (C); a 3 MB source parsed before the length check (E); parse_action raising on nan/inf/10**400 (F); the resumed dish diverging at tick 1 because to_dict rounded energy to 4 places (G); compile_genome taking one argument; and no backstop. Two hung outright: a finally block that loops after the first Lysis (one-shot timer) and module-level work (compile ran outside any budget).

## 2026-09-08

Why a test-suite item touches bio/membrane.py, bio/dish.py and bio/prompts.py: a floor that encodes random._os.system(...) as admitted is worse than no floor, and fix G (unrounded energy in dish.json) is required by the persistence criterion itself. Every fix is minimal and listed in CHANGELOG under Unreleased.

## 2026-09-08

Lysis is now a BaseException; .mro is banned as the one non-dunder route from an exception class to BaseException; the timer repeats so a finally cannot outlive it. Because the .mro ban is a route analysis and a future SAFE_BUILTINS addition could reopen it, smoke_test also measures each round (and the module level) with a clock and rejects anything that returns after its budget without bursting: 'too slow: outlived the time budget without bursting'. That backstop is tested with the alarm replaced by a no-op, so it is known to hold independently of the signal.

## 2026-09-08

random inside a genome is now the dish rng (compile_genome(source, rng) is required positional). me.rng already was dish.rng, so this only points the bare name at the same object; the loss is random.Random/random.SystemRandom, which no fossil uses. All 17 fossils in soma/ of the tide run are still admitted. A genome can still random.seed() the shared generator — deterministic but influential; a per-cell derived rng is left as a follow-up.

## 2026-09-08

conftest autouse budget is 0.25 s per live() call (the plan said 0.05). A legitimate genome takes microseconds, so the larger value costs nothing and removes the one flake vector: a stalled CI runner lysing a founder cell mid-test, which would shift the physics trajectory and break determinism together. Tests about the budget set 0.004 explicitly.

## 2026-09-08

Physics bands: the item asked for ±30% of K = replenish × tiles / BASAL_COST (58 on 24×12 at 0.0025). Measured: the founder holds 0.53 K; over ticks 1500–2500 intake splits 51% basal, 46% MOVE_COST, the rest leaves with corpses, so K is the energy-conservation ceiling and not an estimate of the population. Tests assert 0.35K <= mean <= K, min >= 0.6 mean, max <= 1.4 mean, the modal phase reading is stationary (687 of 1000 ticks), and the 0.005 dish holds 1.5–2.5× as many (2.0 measured). These are deliberate floors: retuning a constant or the founder trips them, which is the point.

## 2026-09-08

Per-tick cost is unchanged: 3.22 ms/tick before and after on a 72×34 dish over 300 ticks (pop 926). The hot-path deltas are except (Lysis, Exception), a try around one int(), and setitimer with an interval — the same syscall.

## 2026-09-08

The too-long test patches ast.parse with a recorder and undoes the patch before asserting, not a raiser: pytest itself calls ast.parse when it renders a failure, and a raising patch turns a plain failure into an INTERNALERROR.

## 2026-09-08

Follow-ups not done here: C-level work (sum(range(10**12)), big-int **, [0]*10**10) is not interruptible by SIGALRM and stalls the dish if a genome does it only after the smoke test; _jsonable stringifies non-primitive memory values on save; a per-cell derived rng. Documented under Known limits in docs/membrane.md.

## 2026-09-08

scripts/task check is green: 114 tests in 4.4 s (criterion: under 30 s); the slowest single test is the 1 s isolated-timeout case. Follow-ups opened: 0042 (resource bombs the budget cannot interrupt, p1), 0043 (genome memory fidelity across a save, p2), 0044 (per-cell generator derived from the dish rng, p3).

## 2026-09-09

Rebased onto main after 0003 landed (tests/conftest.py, test_metrics.py, bio/curve.py) and reconciled with the revised plan. The guarantee that nothing in a genome runs after a Lysis is now static, in inspect: finally ('finally not allowed'), except* ('except* not allowed'), bare except, and any except clause that does not name one of the six SAFE_BUILTINS exception classes by name, alone or as a tuple ('except may only name ...', built from SAFE_BUILTINS so the list cannot drift). This supersedes the repeating timer and the clock backstop ('outlived the time budget without bursting') described in the earlier note: both are gone. The timer is one shot again because a second alarm could land while the first Lysis is still unwinding through Dish.step's handler and escape the tick; test_budget_is_one_shot pins it. .mro stays banned: it is the only non-dunder route to BaseException and object, and a genome must not be able to raise a BaseException either, since the dish catches only Lysis and Exception.

## 2026-09-09

Red evidence for the reconciliation, on the code as rebased: inspect admitted all six new cases (a return in finally, except BaseException, except me.oops, except err, except (ValueError, BaseException), except* ValueError); parse_action(('emit', nan)) returned ('emit', 1.0), now None; Budget's timer had an interval; and the finally-return and except-laundering genomes were stopped only by the clock backstop, not by the gate. All red before, green after, and all 17 fossils in soma/ of the tide run are still admitted; none uses except, finally, random., ._ or .format. Watch the nonviable rate in the first run after merge: a model that habitually writes bare except or finally sees more rejections, and the prompt now states the rule so they feed back.

## 2026-09-09

tests/conftest.py is main's autouse vessel fixture extended, not replaced: lenient_budget (0.25 s), fixture_genomes, make_dish and dish_state are added; dormant_mind and a separate no_network fixture are gone because the autouse fixture already leaves Mind() dormant and turns urlopen into an AssertionError, which test_network_guard_is_armed relies on. test_culture no longer pins the curve header (18 columns now; test_metrics owns it). The mask/tiles test left test_physics: geometry is 0009/0006. Suite after the rebase: 146 tests in about 5 s; the slowest is still the 1 s isolated-timeout case.
