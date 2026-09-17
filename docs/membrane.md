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
| `**` with a non-constant exponent (`2 ** me.age`) or a constant one over 1024, whether it folds to a plain number (`2 ** 10**9`) or is too large to carry (`2 ** 10**19`, `2 ** (2 ** 100)`); a base of any size, and a float or small integer exponent (`x ** 0.5`, `energy ** 2`, `energy ** (1 / 2)`), are fine | `** with a non-constant or oversized exponent (a resource bomb the budget cannot interrupt)` |
| a list, tuple, string or bytes literal repeated so that the product of its constant factors is over 1,000,000, in one multiply (`[0] * 10**10`, `'-' * 10**10`) or a chain of them (`[0] * 1000 * 1000 * 1000`, `([0] * 10**6) * 10**6`); a small product (`[0] * 8`) or a factor only the dish knows (`[0] * len(me.around)`) is fine | `sequence repeated by a large constant (a resource bomb the budget cannot interrupt)` |
| `range()` whose bounds are all constant and whose length is above 1,000,000 (`range(10**12)`, `range(0, 10**12)`, `range(0, -10**12, -1)`), or a bound too large to carry (`range(10**19)`); a short one (`range(8)`, `range(10**7, 10**7 + 5)`) or a runtime count (`range(n)`) is fine | `range() over a huge constant (a resource bomb the budget cannot interrupt)` |

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

Why the resource-bomb rules: the time budget below is a signal delivered between
bytecodes, so a single C-level operation — `2 ** 10**9`, `[0] * 10**10`,
`sum(range(10**12))` — runs to completion before it can be interrupted, and one of them
can hold the whole dish. The static gate refuses their literal and constant forms here,
where it sees the code whatever tick would run it, so a bomb behind `if me.tick > 40:` is
refused at admission rather than stalling a running dish. It reads only what the source
fixes — an exponent, the factors of a repeat, or a `range`'s bounds when they are literals or
constant arithmetic on literals — folded by a small hand-written evaluator that runs no genome
code. The evaluator carries the everyday numeric operators (`+ - * / // % **`) and treats a
value that folds past `10**18` as too large to carry, so a fold to nothing means "oversized",
not "benign but not a plain literal": `2 ** 10**9` and the larger `2 ** 10**19` are both refused,
a chain like `[0] * 1000 * 1000 * 1000` is refused on the product of its factors, and a `range`
is refused on its actual length, so a negative-step form (`range(0, -10**12, -1)`) is caught the
same as `range(10**12)`. A value the dish computes at runtime is left to the isolated child's
caps and the wall-clock timeout (below): `2 ** me.age` is refused as non-constant, but
`[0] * len(me.around)` and `range(n)` pass. A float or small integer exponent is not a bomb, so
`x ** 0.5`, `energy ** 2` and `energy ** (1 / 2)` stay legal — which matters because a thawed
dish is inspected again (below) and a benign power must survive the reload.

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
| the memory held something a save cannot carry, or too much, after a round | `<reason> (tick N)` — the reasons are in the next section |
| the source did not compile | `failed to compile: <Type>: <msg>` |

## What a cell may keep: `me.memory`

`me.memory` is the one thing a genome can change that lives on between ticks; it is what
a daughter inherits and what `dish.json` and every sample carry. So after every `live()`
the dish holds the memory to one rule, `membrane.memory_fault`, and a cell whose memory
breaks it bursts, before its action applies. The smoke test applies the same rule after
each of its forty rounds (the stand-in cell keeps one memory across them, so counters and
trails grow as they would in the dish) and refuses the genome with the reason and the
round. After a tick a cell's memory must satisfy all of:

1. **Values** are `None`, bools, ints, floats, strings, and lists, tuples and dicts of
   those, at any nesting; **keys** are strings, numbers, bools or `None`. That is what
   JSON can carry, and a save is JSON.
2. **Nesting** is at most `MEMORY_MAX_DEPTH` (16) deep, the memory dict itself being
   depth 1. A daughter's memory is a `copy.deepcopy` of her mother's and the save runs a
   recursive codec over it; the bound keeps both far from the interpreter's recursion
   limit, where `deepcopy` gives up and mother and daughter end up sharing the structure.
3. **No list or dict appears twice** — in two places, or inside itself. A save separates
   what was one object: before it a write to `rows[0]` showed in all eight rows of
   `[[0] * 8] * 8`, after it in one. A tuple is immutable and may appear anywhere, any
   number of times.
4. **Written as plain JSON it is at most `MEMORY_MAX_CHARS` (2048) characters**: about a hundred
   floats, or four hundred small ints, or a two-thousand-character string. The figure is
   `len(json.dumps(memory))` — the memory as JSON writes it, a tuple counted as its list and a
   numeric key as its string. It is not the tagged on-disk form (below): the file's type tags
   are not counted, so a tuple- or numeric-key-heavy memory can serialise to somewhat more than
   this on disk.

Over the bound is lysis, not trimming: trimming would have to pick a key to drop, a silent
change to what the genome sees, where a burst shows in the death ledger and the smoke test
tells the mutagen why. The rule runs in the tick and not at the save because only then can
the save be exact: whatever a save dropped, the running dish would still have, and its twin
would not.

| what the memory held after a tick | reason |
|---|---|
| a value of any other type: a function, `me`, `me.rng`, a range, an iterator | `memory holds a range; only None, bools, numbers, strings, lists, tuples and dicts may stay in it` (`a function` for anything callable, `me` for the cell itself) |
| a key of any other type | `memory has a tuple as a key; keys must be strings, numbers, bools or None` |
| a container at depth 17 | `memory nested deeper than 16` |
| one list or dict in two places, or containing itself | `memory holds one list or dict in two places, or inside itself; keep a copy in each` |
| more than 2048 characters as JSON | `memory over 2048 chars as JSON` |

In the smoke test each reason ends with ` (tick N)`, the round it happened on.

The check is one walk over the memory, then `json.dumps` only when the walk cannot settle
the length on its own. The walk is not an optimisation: `json.dumps` cannot see that one
list sits in two places, and on Python 3.12 and later it recurses thousands of levels
deeper than `deepcopy` does. It keeps a lower and an upper bound on the JSON length as it
goes, stops as soon as the lower one passes the cap, and skips `json.dumps` when the upper
one is under it, so its work is bounded by the cap and not by the memory: a list that
repeats a nested list a thousand times three levels down is a billion leaves as JSON and is
refused in microseconds. For a cell with an empty memory, as in every fossil, it costs
nothing measurable; for a cell keeping a six-int trail about a microsecond; on a 72×34 dish
of 588 such cells stepped flat out about 0.5 ms on 2.9 ms per tick, and nothing at
`TICK_SECONDS` = 0.5. `tests/test_membrane.py` pins, on two thousand seeded memories, that
the walk's two bounds bracket the real length, so neither short cut can change a verdict.

### the file format

JSON cannot tell a tuple from a list or an int key from a string key, so `dish.json` and
strain samples tag them (`encode_memory` and `decode_memory` in `bio/dish.py`): a tuple is
`{"~t": [items]}`; a dict whose keys are all strings and none begins with `~` is a plain
object; any other dict is `{"~d": [[key, value], ...]}`, which also carries a key that
happens to begin with `~`. Everything the rule admits goes through exactly, insertion order
included, and comes back with its types. The cap in rule 4 above is measured on the plain form
(`json.dumps(memory)`), not on this tagged file, so a memory that is admitted can serialise to
somewhat more than `MEMORY_MAX_CHARS` on disk when it holds many tuples or numeric keys. A
`dish.json` or a sample written before the tags,
or by hand with plain lists and string keys, reads as JSON gives it; a malformed tag is left
as the plain JSON it is; memory an older save had already flattened to a string stays flat,
since nothing can tell what it was. Forbidding tuples and numeric keys would have been
simpler than tagging, and would have pushed evolution toward a JSON dialect; the tag costs
nothing per tick.

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

The child also caps its own resources before it reads the source: `RLIMIT_AS` and
`RLIMIT_DATA` at 2 GiB, `RLIMIT_CPU` at 15 s. A resource bomb whose size is only known at
runtime — `n = 10**9; [0] * n` — is one the static gate cannot see, and without a cap it
would exhaust the box before the 20 s timeout reaped it; under the cap it fails as a
`MemoryError` the smoke test reports as an ordinary throw. The caps are set inside the
child after it starts, not through a `preexec_fn` — a `preexec_fn` runs in a fork of the
multithreaded mutagen process and can deadlock on the fork-with-threads interaction. They
are best-effort: macOS refuses to lower the address-space limit below an infinite hard
limit, so there the static gate and the wall-clock timeout are the backstop, while
`RLIMIT_CPU` works on both.

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

`tests/fixtures/genomes/` holds ten fossils copied verbatim from `vessel/soma/` of the first
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
not a hung suite), all refused before anything runs. The resource-bomb rules add one
genome per form to the escape-class set — an oversized, an unrepresentable and a computed
exponent, a list and a string repeated by a huge constant and by a chain of constants, and
a huge `range` in its plain and negative-step forms — and a genome that hides each constant
form (`sum(range(10**12))`, `2 ** 10**19`, `[0] * 1000 * 1000 * 1000`) behind
`if me.tick > 40:` proves the static gate refuses it at admission with the smoke test
replaced, so nothing runs; positive controls (a float, a small-integer and a division
exponent, a runtime-sized and a chained runtime-sized repeat, a runtime-sized `range` and a
short high-numbered window) pin that the ordinary forms stay admitted, since the thaw screen
re-inspects them. `admit_isolated`
is exercised with a Python-level loop, which the child's own budget answers, a C-level one
whose count is computed at runtime, which the wall-clock timeout ends, and (on Linux) a
runtime-sized memory bomb, which the child's `RLIMIT_AS` turns into a `MemoryError`, each
leaving no process behind. The built-in founder and the ten fossils are
the positive control, and one genome using every benign construct at once — generator
expressions, `try/except` on the whitelisted names alone, as a tuple and with `as`,
`del` of a local, `match` with a wildcard, a walrus, f-strings, underscore-prefixed
locals, module-level constants with arithmetic, a tuple and an alias of `random`, a
helper with constant defaults and annotations, a docstring, `random.random()` and
`random.choice()` — must be admitted. The tests that prove the static gate alone refuses
a construct replace the smoke test with one that fails loudly, so "nothing ran" is a
structural fact and not a timing. The memory rule has one case per reason string, through
the rule and through the smoke test, a lysis in the dish that comes before the cell's
action, and the seeded bound test above; genomes keeping trails, tuples and int-keyed
dicts are its positive control. `tests/test_persistence.py` resumes a genome with the
fullest module level the gate admits, and one that keeps a tuple, a dict keyed by
direction, a counter past 2**63 and a `~` key in memory, and asserts an exact twin for
fifty ticks, once in the same interpreter and once in a child interpreter under a different
`PYTHONHASHSEED`, with a control twin built from plain JSON that leaves the trajectory; it
pins the codec and the file format; and it runs a genome whose counter passes the cap to
see every cell burst on the same tick in the dish and in its twin. `tests/test_culture.py`
runs a culture whose `dish.json` cannot be written, checks that the culture's generator
comes back from a save, thaws a dish holding a strain with a bare `except` to see it lysed,
named and marked extinct when the culture runs, and loads a `dish.json` in which one cell's
memory is over the cap to see that cell alone burst on the first tick.

## Thawing a dish

`dish.json` is the freezer. It holds the agar, the pheromone, every cell with its energy,
age and memory, every genome, the dish's generator and, since this release, the culture's
own generator, which rolls the mutations, so a resumed culture rolls them at the divisions
the running one would have. The culture writes it every 150 ticks and once more on the
way out, atomically. A save that fails, whatever the reason, is logged once as a
`freezer` event (`≣` in the incubator log), tried again at every later save, and
announced again when writing works; the dish keeps stepping meanwhile, and the last
`dish.json` that was written stands.

Of `me.memory` the freezer keeps everything. The rule above runs after every tick, so at
any save every cell's memory is something the codec carries exactly: tuples, numeric keys,
nesting and ints of any width the cap admits. The 64-key, 200-character-per-value and
`[-2**63, 2**63)` limits of earlier builds are gone. A cell whose memory is over the cap
when a dish is loaded — a hand edit, or a vessel saved before the rule — is not refused at
load (`biotic status` reads the same file); it bursts on the first tick the culture runs,
alone, and the next save no longer holds it. A strain sample whose memory breaks the rule
is refused by name before the pre-revive freeze, because both revives save right after
placing the cells, before any tick runs the rule.

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

- **A runtime-sized resource bomb is bounded in the child, not in the dish.** The alarm
  is delivered between bytecodes, so a single C-level operation runs to completion before
  `Lysis` can be raised. The literal and constant forms named in the bug — `2 ** 10**9`,
  `[0] * 10**10`, `sum(range(10**12))` — are now refused by the static gate regardless of
  the tick that would run them (above), and the isolated child caps its own memory and CPU
  (`RLIMIT_AS`/`RLIMIT_DATA`/`RLIMIT_CPU`; best-effort — macOS cannot lower the
  address-space limit). What is left is a bomb whose count is computed at runtime
  (`n = 10**12; sum(range(n))`): the static gate cannot fold a value it does not have, so
  in the isolated child it is bounded by the wall-clock timeout and, on Linux, by
  `RLIMIT_AS`, but a genome that reaches the dish carrying such a form still stalls the
  culture for one operation, because the dish runs each cell in-process with no per-tick
  isolation — an in-dish pre-emptor is out of scope (a subprocess per tick is too slow, a
  watchdog that kills the process too blunt). `sorted(huge)` is covered by the same walls:
  the huge sequence has to be built first, and building it meets the range or repeat rule
  or the child's memory cap. The memory check itself cannot be made to stall: its work is
  bounded by `MEMORY_MAX_CHARS`, not by the memory (above).
- **`%`-formatting and `repr` are a read-only channel.** `"%r" % me`, `str(random)` and
  `str(live)` reveal a class name and an address. Nothing can be called through it, but
  the address differs from process to process, so a genome that branches on such a
  string is the one admitted thing that can diverge from its twin across a resume. No
  model writes that by accident, which is why it is a limit and not a rule.
- **The stand-in cell is not the dish.** Forty rounds against random situations find
  genomes that throw on ordinary inputs. They do not find one that throws on a state
  only a real dish produces; that is what lysis in the dish is for.
- **A thawed strain is inspected, not smoke-tested.** The screening at the start of a run
  applies the static rules only. A genome that a newer smoke test would refuse but the
  older one admitted keeps living until the dish itself lyses it.
