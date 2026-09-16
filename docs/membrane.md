# The membrane

A genome is Python source that defines one function, `live(me)`. It is written by a
language model and runs on your machine, once per cell per tick, so before it can
become a cell it passes through `bio/membrane.py`. The membrane has two gates: a
static inspection of the source, then a smoke test that runs it. Both return a
`Verdict` with a list of reasons. The first reason is what the mutagen is told when
a daughter is rejected, so the strings are part of the interface and the test suite
asserts them by name.

`bio/membrane.py` is a security boundary. A changed rule changes what every culture
that runs afterwards will accept; record it in `CHANGELOG.md`.

## The static gate: `inspect(source)`

Cheap, strict, and dumb on purpose. It walks the syntax tree once and collects every
rule the source breaks, deduplicated, in order. The length check comes first and
returns without parsing, because parsing megabytes of model output is itself a cost.

| what the genome did | reason |
|---|---|
| longer than `GENOME_MAX_CHARS` (2400) | `genome too long (N > 2400 chars)` |
| does not parse | `SyntaxError: <msg> (line N)` |
| `import x`, `from x import y` | `imports are not allowed (math and random are already in scope)` |
| a call, or any other non-constant expression, at module level | `module-level expression with side effects` |
| anything at module level but `def`, an assignment, an annotated assignment, or a bare constant such as a docstring (`try`, `if`, `for`, `while`, `with`, ...) | `module-level <Node> not allowed` |
| a module-level value that is not a constant: a call (`X = random.random()`, `DIRS = list(range(8))`), a list, dict, set or comprehension (`SEEN = []`), a lambda; the same in a `def`'s defaults and annotations (`def helper(me, seen=[])`, `def helper(me, x=random.random())`) | `module-level values must be constants (numbers, strings, tuples; no calls, lists or dicts)` |
| `@decorator` | `decorators not allowed` |
| no `def live` | `no live(me) function` |
| `def live(me, other)` | `live() must take exactly one argument` |
| `eval` `exec` `compile` `open` `input` `__import__` `globals` `locals` `vars` `getattr` `setattr` `delattr` `breakpoint` `memoryview` `type` `super` `object` `classmethod` `staticmethod` `property` `exit` `quit` `help` `dir` `id` `hash` `iter` `next` `print` | `forbidden name: <name>` |
| any other name beginning with `__` | `dunder name: <name>` |
| any attribute beginning with `__` (`me.__class__`, `[].__class__.__subclasses__()`, `me.rng.__dict__`) | `dunder access: .<attr>` |
| any attribute beginning with `_` (`random._os`) | `private attribute: .<attr>` |
| `.format`, `.format_map`, `.mro` | `forbidden attribute: .<attr>` |
| assigning to or deleting an attribute (`math.pi = 0`, `random.tally = 1`, `helper.n = 1`, `me.energy = 2`, `del math.pi`) | `attributes are read-only: .<attr>` |
| `try` with a `finally:` | `finally not allowed` |
| `with` | `with not allowed` |
| `except*` | `except* not allowed` |
| `except:` with no type | `bare except not allowed` |
| `except` naming anything but `Exception`, `ValueError`, `KeyError`, `IndexError`, `ZeroDivisionError`, `TypeError`, alone or as a tuple (`except BaseException:`, `except me.oops:`, `except err:`, `except Exception.mro()[1]:`) | `except may only name Exception, IndexError, KeyError, TypeError, ValueError, ZeroDivisionError` |
| binding one of those six names to anything: `ValueError = 5`, `def helper(me, KeyError)`, `except KeyError as ValueError`, `for KeyError in ...`, `(KeyError := 3)`, `def KeyError()`, `del ValueError`, a `case KeyError:` capture | `cannot rebind <name>` |
| `set()`, `frozenset`, a set display (`{'N', 'S'}`), a set comprehension | `sets not allowed (their order depends on the interpreter, not the seed; use a tuple, list or dict)` |
| `global`, `nonlocal` | `global/nonlocal not allowed` |
| `async def`, `await`, `yield`, `yield from` | `async/generators not allowed` |
| `class` | `classes not allowed` |

Why those three attributes: `str.format` and `str.format_map` read attributes named
inside their replacement fields, so `"{0.__class__}".format(me)` would reach a dunder
the syntax tree never shows. `.mro()` is the one attribute without a leading underscore
that leads from an exception class to `BaseException` and `object`; `BaseException` is
what a burst is (below), and a genome must be able neither to catch one nor to raise one.

Why the `except` rules: a burst is an exception, and there are four ways a genome
could run on after one. A `finally:` block runs whatever is propagating, and a `return`
there discards it, instantly, so no timer can help; a `with` block's `__exit__` runs
the same way and may swallow what is propagating by returning true. A bare `except:`
catches everything. An `except` whose expression is not a plain name can evaluate to
something wider than the genome should be able to name: `Exception.mro()[1]` is
`BaseException`, and `except BaseException:` itself is a `NameError` inside a genome,
which an outer `except Exception:` would catch after the loop has burst. And an
`except` that names one of the six correctly still has to mean it: if `KeyError` has
been bound to anything else, locally, at module level, as a parameter, through `as`,
or merely later in the function so that the name is an unbound local, then matching a
burst against `except KeyError:` raises a `TypeError` or an `UnboundLocalError`, both
of them `Exception`s that an outer handler would catch, again after the burst, with
the one-shot timer already spent. So `except` may name only the exception classes in
the namespace, by name, alone or as a tuple; every one of those is a subclass of
`Exception`; and a genome may not bind any of those six names to anything. The list in
the reason string is built from `SAFE_BUILTINS`, so adding an exception class there
widens `except` and the rebinding rule in the same step; the suite pins that no class
in that namespace is a superclass of `Lysis` and that every name on the list is refused
as a binding target.

Names with a single leading underscore (`_`, `_tmp`, `def _helper`) stay legal. The
rule is about attributes, which are how a genome would reach out of its namespace.

Why attributes are read-only: `math` is the real module, and `random` is the dish's
generator, an ordinary object with a `__dict__`. `math.pi = 0` would change `math.pi`
for every genome in the process (it did, before the rule); `random.tally = 1` or
`helper.n = 1` would give a strain a scratchpad that no `dish.json` carries. Nothing a
genome can reach has an attribute it should write, so the gate refuses every attribute
store and delete. `me.memory[...] = x` is a subscript, not an attribute, and stays legal.

Why module level is constants: module-level code runs when a genome is compiled, and a
dish loaded from the freezer compiles its genomes again on their first tick, so whatever
happens at module level happens twice, at different points in the run. A module-level
`random.random()` would draw from the dish's generator at a different point than the
original run did and hand every cell a different constant; a module-level list, dict or
set, or a mutable default argument, which is created when the `def` runs, would be
state a strain carries between ticks that no save contains. So module level may hold
`def`s without decorators, and assignments, default arguments and annotations built
from numbers, strings, `True`/`False`/`None`, tuples, names and arithmetic on them: no
calls, no lists, dicts, sets, comprehensions or lambdas. An alias such as `R = random`
is fine; it is the same generator. With this and the read-only attributes, everything
a genome can change between ticks is in `me.memory` or the dish's generator, and both
are in `dish.json`.

Why no sets: a set of strings iterates in an order that depends on the interpreter's
hash seed, which is drawn afresh for every process unless `PYTHONHASHSEED` is set, so
`for d in {"N", "E", "S", "W"}` visits its members in one order in the culture that
saved a dish and in another in the one that resumes it. The dish's seed does not reach
that; a resume is a process boundary; and a genome that walked a set of strings was the
one admitted thing that could diverge from its twin there. Sets of numbers happen to be
stable and membership tests never depended on order, but the rule is static and cannot
tell those apart, so `set`, `frozenset`, set displays and set comprehensions are all
refused. A dict keeps insertion order whatever the hash seed and does the same jobs.

What a genome has: `math`, `random` (see below), and these builtins — `abs` `all` `any`
`bool` `dict` `divmod` `enumerate` `filter` `float` `int` `isinstance` `len` `list`
`map` `max` `min` `pow` `range` `reversed` `round` `sorted` `str` `sum` `tuple`
`zip` `True` `False` `None` `Exception` `ValueError` `KeyError` `IndexError`
`ZeroDivisionError` `TypeError`. Nothing else is defined; `BaseException` and `set`,
for two, are `NameError`s.

## The dynamic gate: `smoke_test(source)`

A genome that inspects clean is compiled into a namespace holding only the above, and
`live(me)` is called forty times against a stand-in cell with random energy, agar,
neighbours and scent. The stand-in is seeded, so a verdict is repeatable. Every call
must return something `parse_action` accepts.

Time is measured with the same wall-clock budget the dish uses, `CELL_TIME_BUDGET`
(4 ms), times four — for the module-level code as well as for each round:

| what happened | reason |
|---|---|
| module-level code ran past its budget | `too slow: module level exceeded time budget` |
| a round ran past its budget | `too slow: exceeded time budget` |
| an exception escaped `live` | `threw on tick N: <Type>: <msg>` |
| a return value `parse_action` rejects | `returned an unknown action: <repr>` |
| the source did not compile | `failed to compile: <Type>: <msg>` |

## Lysis: why a genome cannot catch the budget

`Budget` arms a one-shot `SIGALRM` timer; when it fires, the handler raises `Lysis`.
Nothing inside a genome can catch it or run after it:

- `Lysis` derives from `BaseException`, not `Exception`. `Exception` is the widest
  class a genome can name, and `except Exception:` does not see it.
- The static gate refuses every construct that would run code after it: `finally:`,
  `with`, bare `except:`, `except*`, any `except` that does not name one of the six
  built-in exception classes directly, and any binding of those six names. Every route
  from a name a genome has to `BaseException` is closed too (`.mro()`, every
  `__dunder__`, `type`, `object`), so a genome cannot raise one either, and the dish's
  own handler, which catches `Lysis` and `Exception`, sees everything a genome can throw.

The timer is one shot on purpose. Nothing can run after the first `Lysis`, so a second
alarm would add nothing, and a repeating one could fire while the first is still
unwinding through the dish's handler, where it would escape the tick.

Because the alarm is a signal, `Budget` only works on the main thread, which is where
the dish runs. In the dish a `Lysis` is a death like any other: the cell bursts,
`lysed` counts up, the cell's necromass returns to its tile, and the tick goes on.

## Isolation: `admit_isolated(source)`

The mutagen thread cannot use the alarm, and a genome that fails in a way the alarm
cannot interrupt (below) would take the whole process with it. So the mutagen admits
through `admit_isolated`, which runs `python -m bio.membrane` as a child, feeds it the
source on stdin, and reads one JSON line back. The child has a ceiling of 20 s. If it
is still running then it is killed and reaped, and the verdict is
`too slow: smoke test timed out`. A child that dies without a verdict gives
`membrane crashed: <tail of stderr>`.

## `random` is the dish's generator

Inside a genome, `random` and `me.rng` are the same object: the dish's own seeded
`random.Random`. Everything a genome is likely to want is there — `random()`,
`choice`, `randint`, `uniform`, `shuffle`, `gauss`, `randrange`, `sample` — and the
`random` module itself, with its private state and `SystemRandom`, is out of reach.
This is what makes a culture reproducible: with a fixed seed, two dishes run the same
genomes to the same state, tick for tick, in any process. A draw at module level is
refused by the static gate (above), because module level runs again when a dish is
loaded and the draw would then land at a different point in the sequence; sets are
refused because their order comes from the interpreter and not from the seed.

The flip side is that a genome can call `random.seed(...)`, and that reseeds the dish.
The result is still deterministic — the same genome does the same thing on every
replay — but one strain can perturb the randomness every other cell sees. If that
ever matters, the remedy is a per-cell generator derived from the dish's. It is not
done today.

## The fixture set

`tests/fixtures/genomes/` holds ten fossils copied verbatim from `soma/` of the first
"tide" run (seed "tide", model `qwen/qwen3-coder`, 2026-09-08): the founder,
`tide_drifter`, and nine of its descendants. They are the membrane's positive control.
Every one must be admitted, and the suite names the one that stops being when a rule
changes. Do not edit them; ruff is told to leave them alone, and their trailing
whitespace is part of the record.

## What the suite guarantees

`tests/test_membrane.py` holds one genome per escape class, each asserting the reason
string above by name, so a rule that quietly stops firing is caught by name and not by
a count. The dynamic gate is exercised at the real 4 ms budget: a busy loop, a loop
inside `except Exception:`, a recursion bomb, module-level work, the `finally` and
laundering genomes, and six spellings of a rebound `except` name (a local, a module-level
constant, a parameter, an `as` name, an unbound local, and one whose outer handler loops
forever, admitted through the child interpreter so that a regression is a timeout and
not a hung suite), all refused before anything runs. `admit_isolated` is exercised with
a Python-level loop, which the child's own budget answers, and a C-level one, which the
ceiling ends, leaving no process behind. The built-in founder and the ten fossils are
the positive control, and one genome using every benign construct at once — generator
expressions, `try/except` on the whitelisted names alone, as a tuple and with `as`,
`del` of a local, `match` with a wildcard, a walrus, f-strings, underscore-prefixed
locals, module-level constants with arithmetic, a tuple and an alias of `random`, a
helper with constant defaults and annotations, a docstring, `random.random()` and
`random.choice()` — must be admitted. The tests that prove the static gate alone refuses
a construct replace the smoke test with one that fails loudly, so "nothing ran" is a
structural fact and not a timing. `tests/test_persistence.py` resumes a genome with the
fullest module level the gate admits and asserts an exact twin for fifty ticks, once in
the same interpreter and once in a child interpreter under a different `PYTHONHASHSEED`;
pins what the freezer keeps of `me.memory` at every boundary; and runs a genome whose
counter passes the 4300-digit limit until its save goes through. `tests/test_culture.py`
runs a culture whose `dish.json` cannot be written, checks that the culture's generator
comes back from a save, and thaws a dish holding a strain with a bare `except` to see it
lysed, named and marked extinct when the culture runs.

## Thawing a dish

`dish.json` is the freezer. It holds the agar, the pheromone, every cell with its energy,
age and memory, every genome, the dish's generator and, since this release, the culture's
own generator, which rolls the mutations, so a resumed culture rolls them at the divisions
the running one would have. The culture writes it every 150 ticks and once more on the
way out, atomically. A save that fails, whatever the reason, is logged once as a
`freezer` event (`≣` in the incubator log), tried again at every later save, and
announced again when writing works; the dish keeps stepping meanwhile, and the last
`dish.json` that was written stands.

Of `me.memory` the freezer keeps at most 64 keys. Floats, strings, bools, `None` and
ints in `[-2**63, 2**63)` are kept as they are and come back exactly; anything else, a
list, a dict, a tuple, an int wider than that, comes back as the first 80 characters of
its `str()`. The bound on ints is what keeps a save writable: `json.dumps` refuses an int
past 4300 digits, and a genome that multiplies a counter every tick gets there in an
afternoon. Before the bound such a genome made the save raise and the loop die with it.

Every strain in a thawed dish is held against the static gate again when the culture
starts to run. A dish saved under older rules may hold strains admitted with a bare
`except`, a `finally`, a set, or a module-level draw, exactly the constructs a release
closes, and those do not get to run: their cells lyse when `biotic live` or `biotic run`
starts, their genome leaves the dish, one `nonviable` event names the strain and the
reason (`relic no longer passes the membrane — bare except not allowed; 3 cells lysed`),
and the registry marks the strain extinct on the next tick. The screening happens in
`Culture.run()`, not `Culture.load()`, so `biotic status`, `strains`, `genome` and `log`
show the dish as it is on disk and do not rewrite it. Only the static gate is re-run;
the smoke test is not, since a strain that has been living in the dish has passed a
harder one.

## Known limits

- **Only interruptible code is bounded.** The alarm is delivered between bytecodes. A
  single C-level operation — `sum(range(10**12))`, `2 ** 10**9`, `[0] * 10**10`,
  sorting an enormous list — runs to completion before `Lysis` can be raised. The
  smoke test catches such a genome if it does this within its forty rounds; in the
  isolated child the 20 s ceiling ends it. A genome that only does it later, in the
  dish, stalls the culture until the operation finishes. There is no memory cap
  either.
- **`%`-formatting and `repr` are a read-only channel.** `"%r" % me`, `str(random)` and
  `str(live)` reveal a class name and an address. Nothing can be called through it, but
  the address differs from process to process, so a genome that branches on such a
  string is the one admitted thing that can diverge from its twin across a resume. No
  model writes that by accident, which is why it is a limit and not a rule.
- **The stand-in cell is not the dish.** Forty rounds against random situations find
  genomes that throw on ordinary inputs. They do not find one that throws on a state
  only a real dish produces; that is what lysis in the dish is for.
- **The twin holds for primitive memory.** `dish.json` keeps ints in `[-2**63, 2**63)`,
  floats, strings, bools and `None` in `me.memory`, at most 64 keys, and stringifies the
  rest (above); a genome that keeps a list there, or an int wider than that, gets a
  string back after a resume. Module level and attributes are closed, so this is the one
  place a genome's state can differ from its save.
- **A thawed strain is inspected, not smoke-tested.** The screening at the start of a run
  applies the static rules only. A genome that a newer smoke test would refuse but the
  older one admitted keeps living until the dish itself lyses it.
