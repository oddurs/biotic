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
| no `def live` | `no live(me) function` |
| `def live(me, other)` | `live() must take exactly one argument` |
| `eval` `exec` `compile` `open` `input` `__import__` `globals` `locals` `vars` `getattr` `setattr` `delattr` `breakpoint` `memoryview` `type` `super` `object` `classmethod` `staticmethod` `property` `exit` `quit` `help` `dir` `id` `hash` `iter` `next` `print` | `forbidden name: <name>` |
| any other name beginning with `__` | `dunder name: <name>` |
| any attribute beginning with `__` (`me.__class__`, `[].__class__.__subclasses__()`, `me.rng.__dict__`) | `dunder access: .<attr>` |
| any attribute beginning with `_` (`random._os`) | `private attribute: .<attr>` |
| `.format`, `.format_map`, `.mro` | `forbidden attribute: .<attr>` |
| `except:` with no type | `bare except not allowed` |
| `global`, `nonlocal` | `global/nonlocal not allowed` |
| `async def`, `await`, `yield`, `yield from` | `async/generators not allowed` |
| `class` | `classes not allowed` |

Why those three attributes: `str.format` and `str.format_map` read attributes named
inside their replacement fields, so `"{0.__class__}".format(me)` would reach a dunder
the syntax tree never shows. `.mro()` is the one attribute without a leading underscore
that leads from an exception class to `BaseException`, and `BaseException` is what a
burst is (below).

Names with a single leading underscore (`_`, `_tmp`, `def _helper`) stay legal. The
rule is about attributes, which are how a genome would reach out of its namespace.

What a genome has: `math`, `random` (see below), and these builtins — `abs` `all` `any`
`bool` `dict` `divmod` `enumerate` `filter` `float` `int` `isinstance` `len` `list`
`map` `max` `min` `pow` `range` `reversed` `round` `set` `sorted` `str` `sum` `tuple`
`zip` `True` `False` `None` `Exception` `ValueError` `KeyError` `IndexError`
`ZeroDivisionError` `TypeError`. Nothing else is defined; `BaseException`, for one,
is a `NameError`.

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
| a round returned, but only after its budget had run out | `too slow: outlived the time budget without bursting` |
| an exception escaped `live` | `threw on tick N: <Type>: <msg>` |
| a return value `parse_action` rejects | `returned an unknown action: <repr>` |
| the source did not compile | `failed to compile: <Type>: <msg>` |

## Lysis: why a genome cannot catch the budget

`Budget` arms a repeating `SIGALRM` interval timer; when it fires, the handler raises
`Lysis`. Three things make that uncatchable from inside a genome:

- `Lysis` derives from `BaseException`, not `Exception`. `Exception` is the widest
  name a genome can write, and `except Exception:` does not see it.
- Every route from a name a genome does have to `BaseException` is closed: `.mro()`,
  every `__dunder__`, `type`, `object`, and the bare `except:` that would catch
  anything at all.
- The timer repeats. A `finally:` block that keeps looping after the first `Lysis`
  receives another one a budget later, and cannot outlive it.

Behind those, the smoke test also measures each round with a clock. A round that
returns without bursting, but after its budget has passed, is rejected regardless of
how that came about, so the guarantee does not rest on the route analysis alone.

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
genomes to the same state, tick for tick.

The flip side is that a genome can call `random.seed(...)`, and that reseeds the dish.
The result is still deterministic — the same genome does the same thing on every
replay — but one strain can perturb the randomness every other cell sees. If that
ever matters, the remedy is a per-cell generator derived from the dish's. It is not
done today.

## The fixture set

`tests/fixtures/genomes/` holds ten fossils copied verbatim from `soma/` of the first
"tide" run: the founder, `tide_drifter`, and nine of its descendants. They are the
membrane's positive control. Every one must be admitted, and the suite names the one
that stops being when a rule changes. Do not edit them; ruff is told to leave them
alone, and their trailing whitespace is part of the record.

## Known limits

- **Only interruptible code is bounded.** The alarm is delivered between bytecodes. A
  single C-level operation — `sum(range(10**12))`, `2 ** 10**9`, `[0] * 10**10`,
  sorting an enormous list — runs to completion before `Lysis` can be raised. The
  smoke test catches such a genome if it does this within its forty rounds; in the
  isolated child the 20 s ceiling ends it. A genome that only does it later, in the
  dish, stalls the culture until the operation finishes. There is no memory cap
  either.
- **`%`-formatting and `repr` are a read-only channel.** `"%r" % me` reveals a class
  name and an address. Nothing can be called through it.
- **The stand-in cell is not the dish.** Forty rounds against random situations find
  genomes that throw on ordinary inputs. They do not find one that throws on a state
  only a real dish produces; that is what lysis in the dish is for.
