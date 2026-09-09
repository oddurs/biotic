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

## 2026-09-09

Review found the except whitelist was checked by identifier only: a genome could bind ValueError or KeyError to anything (a local or module-level assignment, a parameter, except ... as, or an assignment later in the function, which makes the name an unbound local), and except KeyError: then raised TypeError or UnboundLocalError while the Lysis was being matched, which an outer except Exception or except TypeError caught after the burst, with the one-shot timer already spent. Red: six spellings admitted by inspect and by admit at the 4 ms budget in 0.74-0.80 s each (forty bursts, every one swallowed); the variant that loops in the outer handler has no ceiling in the dish. Fix: inspect refuses any binding of a name in ALLOWED_EXCEPTIONS ('cannot rebind <name>'): Name in Store or Del context (assignment, augmented and annotated assignment, tuple unpacking, for, comprehension and walrus targets, del), parameters including lambda's, def names, except-as names, match captures, star and mapping rest, and 3.12 type parameters. Limited to the six exception names on purpose: rebinding sum or max has no bearing on Lysis, and models do write max = .... Tests: sixteen REJECTED rows, a per-name pin derived from ALLOWED_EXCEPTIONS so widening the list widens the rule, six laundering genomes refused by admit in under 0.5 s with the single new reason, and the looping one through admit_isolated so that a regression is a timeout and not a hung suite.

## 2026-09-09

with is refused ('with not allowed'): __exit__ runs while a Lysis propagates exactly as finally does, and until now the guarantee rested on nothing in scope having __enter__ rather than on the gate. Attributes are read-only ('attributes are read-only: .<attr>', Store and Del): math.pi = 0 was admitted and set math.pi to 0 for the whole process (verified), and random.tally = 1 or helper.n = 1 gave a strain a scratchpad that dish.json does not carry, so a resume would diverge. Neither the founder nor any fossil assigns an attribute; me.memory[...] = x is a subscript and unaffected.

## 2026-09-09

Module-level draws broke the exact twin: Dish.from_dict leaves _compiled empty, so every strain's module level runs again on its first tick after a load, and a genome with BOLD = random.random() registered directly diverged from its twin at tick 121 (verified; two fresh dishes agree, the reloaded one does not). Chose a static rule over the review's per-strain module generator: an alias R = random or a bound method F = random.random at module level would still have pointed at state no save carries, and module-level lists and dicts, mutable default arguments, draws in defaults or annotations, and decorators are the same hole under other spellings. Rule: top-level Assign/AnnAssign, and a def's defaults and annotations, must be built from Constant, Tuple, Name, Attribute, Subscript, Starred, unary/binary/boolean operators, comparisons, conditional expressions and f-strings ('module-level values must be constants (numbers, strings, tuples; no calls, lists or dicts)'); decorators are refused. Stricter than the review's option (b) in refusing lists and dicts: a module-level list a strain appends to is state between ticks that dish.json does not hold. With attributes read-only, everything a genome can change between ticks is me.memory or the dish generator, both in the save; the residual is memory fidelity (0043), now named under Known limits. No fossil has a module-level assignment. test_module_level_work_is_budgeted asserts the static refusal and calls smoke_test directly for the dynamic budget, since no admitted module level can be both slow and interruptible any more. The prompt's hard rules state the rule and why.

## 2026-09-09

Physics bands retightened after the review showed the old ones (0.35 K to K, min 0.6, max 1.4) did not move under most retunes. Measured on seed test, 24x12, ticks 1500-2500: mean 30.2 = 0.522 K, min 0.760 mean, max 1.157 mean, stationary 687 of 1000 ticks, replenish ratio 2.011. New pins: 0.46 K <= mean <= 0.58 K, min >= 0.7 mean, max <= 1.3 mean, ratio 1.8-2.2, modal phase stationary. What trips, one constant at a time: MOVE_COST 0.0125, 0.02, 0.03, 0.05 (mean 0.74, 0.60, 0.45, 0.42 K); BASAL_COST 0.007, 0.012, 0.015 (min and max; mean 0.60 K at 0.015), not 0.008; EAT_RATE 0.03 and 0.045 (min 0.52 and 0.60, max 1.5 and 1.4, modal death at 0.03), not 0.08 or 0.12; the founder's eat threshold lowered to 0.02 and its divide threshold raised to 1.2 (min), not its eat threshold raised to 0.08. Never: NECROMASS 0 or 0.7, CORPSE_NUTRIENT 0 or 0.3, DIFFUSION 0 or 0.15; the founder eats its tile bare before EAT_RATE limits it, and corpse and diffusion terms move less energy per tick than one cell's basal cost. The module docstring now says exactly this in place of 'will move them'. The proposal's plus or minus 30 percent of K is not attainable without retuning the physics or the founder, which this item must not do: K is the energy-conservation ceiling and the founder's basal share of intake is 52 percent, so the pin is plus or minus 12 percent around the measured 0.52 K.

## 2026-09-09

After the review fixes scripts/task check is green: 193 tests in 4.4 s (criterion: under 30 s); the slowest is still the 1 s isolated-timeout case and the new module-level twin test takes 0.18 s. All ten fossils, the founder and the benign genome are still admitted; no fossil uses with, a decorator, an attribute store, a module-level assignment or one of the six exception names as anything but an except target.
