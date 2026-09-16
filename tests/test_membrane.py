"""The membrane: what code is allowed to become a cell.

One test per escape class. Every negative case asserts that the reason string
names the class, so a rule that quietly stops firing is caught by name, not by
a count.
"""

from __future__ import annotations

import os
import random
import shutil
import signal
import subprocess
import sys
import time

import pytest

from bio import config, membrane
from bio.culture import FALLBACK_GENESIS
from bio.dish import Dish
from bio.membrane import (
    ALLOWED_EXCEPTIONS,
    SAFE_BUILTINS,
    Budget,
    Lysis,
    admit,
    admit_isolated,
    compile_genome,
    inspect,
    smoke_test,
)

from .conftest import fixture_genomes, make_dish

LIVE_REST = "def live(me):\n    return 'rest'\n"
EXCEPT_RULE = "except may only name"
CONSTANT_RULE = "module-level values must be constants (numbers, strings, tuples; no calls, lists or dicts)"
SET_RULE = "sets not allowed (their order depends on the interpreter, not the seed; use a tuple, list or dict)"


@pytest.fixture
def tight_budget(monkeypatch):
    """The production budget, so tests about the budget stay fast."""
    monkeypatch.setattr(config, "CELL_TIME_BUDGET", 0.004)


@pytest.fixture
def no_smoke_test(monkeypatch):
    """For tests that prove the static gate alone refuses a genome: `admit` may not reach the
    smoke test, so nothing in the genome is executed. A regression is a plain failure here, not
    a hang or a timing measurement."""

    def ran(source, rounds=40):
        raise AssertionError("the static gate let this genome through to the smoke test")

    monkeypatch.setattr(membrane, "smoke_test", ran)


# --- static gate: one genome per escape class -------------------------------

REJECTED = [
    ("import", "import os\n" + LIVE_REST, "imports are not allowed"),
    ("import_from", "from os import system\n" + LIVE_REST, "imports are not allowed"),
    ("dunder_class", "def live(me):\n    return me.__class__\n", "dunder access: .__class__"),
    (
        "dunder_subclasses",
        "def live(me):\n    [].__class__.__subclasses__()\n    return 'rest'\n",
        "dunder access: .__subclasses__",
    ),
    ("rng_dict", "def live(me):\n    me.rng.__dict__\n    return 'rest'\n", "dunder access: .__dict__"),
    ("dunder_name", "def live(me):\n    return __builtins__\n", "dunder name: __builtins__"),
    ("getattr", "def live(me):\n    return getattr(me, 'x')\n", "forbidden name: getattr"),
    ("open", "def live(me):\n    open('x')\n    return 'rest'\n", "forbidden name: open"),
    ("eval", "def live(me):\n    return eval('1')\n", "forbidden name: eval"),
    ("exec", "def live(me):\n    exec('x = 1')\n    return 'rest'\n", "forbidden name: exec"),
    ("type", "def live(me):\n    return type(me)\n", "forbidden name: type"),
    ("module_level_call", "math.floor(1.5)\n" + LIVE_REST, "module-level expression with side effects"),
    ("module_level_try", "try:\n    x = 1\nexcept Exception:\n    x = 2\n" + LIVE_REST, "module-level Try not allowed"),
    ("module_level_draw", "BOLD = random.random()\n" + LIVE_REST, CONSTANT_RULE),
    ("module_level_call_in_assignment", "DIRS = list(range(8))\n" + LIVE_REST, CONSTANT_RULE),
    ("module_level_list", "SEEN = []\n" + LIVE_REST, CONSTANT_RULE),
    ("module_level_dict", "WEIGHTS: dict = {'eat': 1.0}\n" + LIVE_REST, CONSTANT_RULE),
    ("module_level_set", "TRIED = set()\n" + LIVE_REST, CONSTANT_RULE),
    ("set_call", "def live(me):\n    seen = set()\n    return 'rest'\n", SET_RULE),
    ("frozenset", "def live(me):\n    seen = frozenset()\n    return 'rest'\n", SET_RULE),
    ("set_display", "def live(me):\n    return ('move', list({'N', 'S', 'E', 'W'}).index('S'))\n", SET_RULE),
    (
        "set_comprehension",
        "def live(me):\n    for d in {d % 8 for d in range(16)}:\n        pass\n    return 'rest'\n",
        SET_RULE,
    ),
    ("module_level_comprehension", "DIRS = tuple(d for d in range(8))\n" + LIVE_REST, CONSTANT_RULE),
    ("module_level_lambda", "PICK = lambda me: me.here\n" + LIVE_REST, CONSTANT_RULE),
    ("mutable_default", "def helper(me, seen=[]):\n    return seen\n\n" + LIVE_REST, CONSTANT_RULE),
    ("default_draw", "def helper(me, x=random.random()):\n    return x\n\n" + LIVE_REST, CONSTANT_RULE),
    ("annotation_call", "def helper(me) -> random.random():\n    return 1\n\n" + LIVE_REST, CONSTANT_RULE),
    ("annotation_list", "def helper(me: [1]):\n    return 1\n\n" + LIVE_REST, CONSTANT_RULE),
    ("decorator", "def wrap(f):\n    return f\n\n@wrap\ndef live(me):\n    return 'rest'\n", "decorators not allowed"),
    ("class", "class X:\n    pass\n" + LIVE_REST, "classes not allowed"),
    ("generator", "def live(me):\n    yield 'rest'\n", "async/generators not allowed"),
    ("async", "async def live(me):\n    return 'rest'\n", "async/generators not allowed"),
    ("global", "x = 0\n\ndef live(me):\n    global x\n    x += 1\n    return 'rest'\n", "global/nonlocal not allowed"),
    (
        "nonlocal",
        "def live(me):\n    x = 0\n    def bump():\n        nonlocal x\n        x += 1\n    bump()\n    return 'rest'\n",
        "global/nonlocal not allowed",
    ),
    ("random_os", "def live(me):\n    random._os.system('true')\n    return 'rest'\n", "private attribute: ._os"),
    (
        "str_format",
        "def live(me):\n    s = '{0.__class__}'.format(me)\n    return 'rest'\n",
        "forbidden attribute: .format",
    ),
    (
        "format_map",
        "def live(me):\n    s = '{me.__class__}'.format_map({'me': me})\n    return 'rest'\n",
        "forbidden attribute: .format_map",
    ),
    (
        "mro_route_to_base_exception",
        "def live(me):\n    try:\n        while True:\n            pass\n    except Exception.mro()[1]:\n        return 'rest'\n",
        ("forbidden attribute: .mro", EXCEPT_RULE),
    ),
    (
        "bare_except",
        "def live(me):\n    try:\n        return 'eat'\n    except:\n        return 'rest'\n",
        "bare except not allowed",
    ),
    (
        "finally",
        "def live(me):\n    try:\n        return 'eat'\n    finally:\n        return 'rest'\n",
        "finally not allowed",
    ),
    (
        "except_base_exception",
        "def live(me):\n    try:\n        return 'eat'\n    except BaseException:\n        return 'rest'\n",
        EXCEPT_RULE,
    ),
    (
        "except_attribute",
        "def live(me):\n    try:\n        return 'eat'\n    except me.oops:\n        return 'rest'\n",
        EXCEPT_RULE,
    ),
    (
        "except_local_name",
        "def live(me):\n    err = ValueError\n    try:\n        return 'eat'\n    except err:\n        return 'rest'\n",
        EXCEPT_RULE,
    ),
    (
        "except_tuple_with_a_stranger",
        "def live(me):\n    try:\n        return 'eat'\n    except (ValueError, BaseException):\n        return 'rest'\n",
        EXCEPT_RULE,
    ),
    (
        "except_star",
        "def live(me):\n    try:\n        return 'eat'\n    except* ValueError:\n        return 'rest'\n",
        "except* not allowed",
    ),
    ("with", "def live(me):\n    with me.memory:\n        pass\n    return 'rest'\n", "with not allowed"),
    ("attribute_store_math", "def live(me):\n    math.pi = 0\n    return 'rest'\n", "attributes are read-only: .pi"),
    (
        "attribute_store_rng",
        "def live(me):\n    random.tally = 1\n    return 'rest'\n",
        "attributes are read-only: .tally",
    ),
    (
        "attribute_store_me",
        "def live(me):\n    me.energy = 2.0\n    return 'rest'\n",
        "attributes are read-only: .energy",
    ),
    (
        "attribute_store_function",
        "def helper():\n    return 1\n\ndef live(me):\n    helper.n = me.tick\n    return 'rest'\n",
        "attributes are read-only: .n",
    ),
    ("attribute_del", "def live(me):\n    del math.pi\n    return 'rest'\n", "attributes are read-only: .pi"),
    ("rebind_local", "def live(me):\n    ValueError = 5\n    return 'rest'\n", "cannot rebind ValueError"),
    ("rebind_module_level", "ValueError = 5\n" + LIVE_REST, "cannot rebind ValueError"),
    (
        "rebind_later_in_function",
        "def live(me):\n    try:\n        return 'eat'\n    except ValueError:\n        pass\n    ValueError = 5\n",
        "cannot rebind ValueError",
    ),
    (
        "rebind_as",
        "def live(me):\n    try:\n        return 'eat'\n    except KeyError as ValueError:\n        return 'rest'\n",
        "cannot rebind ValueError",
    ),
    ("rebind_parameter", "def helper(me, KeyError):\n    return 1\n\n" + LIVE_REST, "cannot rebind KeyError"),
    (
        "rebind_lambda_parameter",
        "def live(me):\n    f = lambda KeyError: 1\n    return 'rest'\n",
        "cannot rebind KeyError",
    ),
    (
        "rebind_for_target",
        "def live(me):\n    for KeyError in range(3):\n        pass\n    return 'rest'\n",
        "cannot rebind KeyError",
    ),
    (
        "rebind_comprehension_target",
        "def live(me):\n    x = [1 for KeyError in me.around]\n    return 'rest'\n",
        "cannot rebind KeyError",
    ),
    (
        "rebind_walrus",
        "def live(me):\n    if (KeyError := 3):\n        pass\n    return 'rest'\n",
        "cannot rebind KeyError",
    ),
    ("rebind_tuple_unpack", "def live(me):\n    a, Exception = 1, 2\n    return 'rest'\n", "cannot rebind Exception"),
    ("rebind_augassign", "def live(me):\n    TypeError += 1\n    return 'rest'\n", "cannot rebind TypeError"),
    ("rebind_annassign", "def live(me):\n    IndexError: int = 1\n    return 'rest'\n", "cannot rebind IndexError"),
    ("rebind_del", "def live(me):\n    del ZeroDivisionError\n    return 'rest'\n", "cannot rebind ZeroDivisionError"),
    ("rebind_def", "def KeyError():\n    return 1\n\n" + LIVE_REST, "cannot rebind KeyError"),
    (
        "rebind_match_capture",
        "def live(me):\n    match me.tick:\n        case KeyError:\n            pass\n    return 'rest'\n",
        "cannot rebind KeyError",
    ),
    (
        "rebind_match_star",
        "def live(me):\n    match me.around:\n        case [*KeyError]:\n            pass\n    return 'rest'\n",
        "cannot rebind KeyError",
    ),
    (
        "rebind_match_mapping_rest",
        "def live(me):\n    match me.memory:\n        case {**KeyError}:\n            pass\n    return 'rest'\n",
        "cannot rebind KeyError",
    ),
    ("two_args", "def live(me, other):\n    return 'rest'\n", "live() must take exactly one argument"),
    ("no_live", "def grow(me):\n    return 'eat'\n", "no live(me) function"),
    ("syntax_error", "def live(me)\n    return 'rest'\n", "SyntaxError:"),
]


@pytest.mark.parametrize("name,source,expected", REJECTED, ids=[r[0] for r in REJECTED])
def test_escape_class_is_rejected_and_named(name, source, expected):
    v = inspect(source)
    assert not v
    for want in (expected,) if isinstance(expected, str) else expected:
        assert any(want in r for r in v.reasons), (want, v.reasons)


def test_except_rule_lists_every_name_a_genome_may_catch():
    """The reason string is built from the whitelist, so the two cannot drift apart."""
    assert ALLOWED_EXCEPTIONS == {"Exception", "ValueError", "KeyError", "IndexError", "ZeroDivisionError", "TypeError"}
    v = inspect("def live(me):\n    try:\n        return 'eat'\n    except BaseException:\n        return 'rest'\n")
    (reason,) = v.reasons
    assert reason.startswith(EXCEPT_RULE)
    assert all(name in reason for name in ALLOWED_EXCEPTIONS)


def test_every_name_except_may_catch_is_pinned_to_the_builtin():
    """The except whitelist is checked by identifier, so each identifier has to keep meaning the
    builtin: every name on the list, and only those, is refused as a binding target."""
    for name in ALLOWED_EXCEPTIONS:
        assert inspect(f"def live(me):\n    {name} = 1\n    return 'rest'\n").reasons == [f"cannot rebind {name}"]
    assert inspect("def live(me):\n    err = total = 0\n    return 'rest'\n")  # any other name is the genome's


@pytest.mark.skipif(sys.version_info < (3, 12), reason="type parameters arrived in Python 3.12")
def test_type_parameter_cannot_rebind_an_exception_name():
    """`def helper[KeyError](x)` binds KeyError to a TypeVar inside helper."""
    v = inspect("def helper[KeyError](x):\n    return x\n\n" + LIVE_REST)
    assert v.reasons == ["cannot rebind KeyError"]


def test_module_level_constants_are_admitted():
    """What module level may hold: numbers, strings, tuples, arithmetic, an f-string, `math.pi`,
    an alias of the generator, and a helper whose defaults and annotations are the same."""
    src = (
        "THRESH = 0.04\n"
        "HALF = THRESH / 2\n"
        "DIRS = (0, 1, 2, 3) + (4, 5, 6, 7)\n"
        "LABEL = f'{THRESH:.2f}'\n"
        "TAU: float = math.pi * 2\n"
        "FIRST = DIRS[0]\n"
        "SIGN = -1 if THRESH > 1 else +1\n"
        "R = random\n"
        "\n"
        "def helper(me, dirs=DIRS, k: int = FIRST) -> float:\n"
        "    return R.random() + dirs[k] + SIGN\n"
        "\n"
        "def live(me):\n"
        "    return 'eat' if helper(me) > HALF else 'rest'\n"
    )
    v = admit(src)
    assert v, v.reasons


def test_too_long_source_is_rejected_without_parsing(monkeypatch):
    """Parsing megabytes of model output is itself a cost; the length check comes first."""
    source = LIVE_REST + "# " + "x" * (3 * 1024 * 1024)
    parsed = []
    real_parse = membrane.ast.parse
    monkeypatch.setattr(membrane.ast, "parse", lambda *a, **k: (parsed.append(1), real_parse(*a, **k))[1])
    v = inspect(source)
    monkeypatch.undo()  # pytest itself parses source when it reports a failure
    assert not v
    assert v.reasons == [f"genome too long ({len(source)} > {config.GENOME_MAX_CHARS} chars)"]
    assert parsed == []


def test_reasons_are_deduplicated():
    v = inspect("def live(me):\n    eval('1')\n    eval('2')\n    return 'rest'\n")
    assert v.reasons.count("forbidden name: eval") == 1


# --- dynamic gate: the budget and the smoke test ----------------------------


def test_lysis_is_not_a_catchable_builtin():
    """Nothing a genome can name catches a burst. `Exception` is the widest class in scope,
    every class the except whitelist admits sits below it, and (test_every_name_except_may_catch_
    is_pinned_to_the_builtin) none of those names can be made to mean anything else."""
    assert issubclass(Lysis, BaseException)
    assert not issubclass(Lysis, Exception)
    assert "BaseException" not in SAFE_BUILTINS
    assert not any(isinstance(v, type) and issubclass(Lysis, v) for v in SAFE_BUILTINS.values())
    assert all(issubclass(SAFE_BUILTINS[n], Exception) for n in ALLOWED_EXCEPTIONS)


def test_budget_bursts_a_loop_and_disarms_the_timer_on_exit():
    with pytest.raises(Lysis):
        with Budget(0.01):
            while True:
                pass
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


def test_budget_is_one_shot():
    """One alarm per call. A repeating interval could raise a second Lysis while the first
    is still unwinding through the dish's handler, and that one would escape the tick."""
    with Budget(0.5):
        _, interval = signal.getitimer(signal.ITIMER_REAL)
    assert interval == 0.0


def test_while_true_is_too_slow(tight_budget):
    v = admit("def live(me):\n    while True:\n        pass\n")
    assert not v
    assert v.reasons == ["too slow: exceeded time budget"]


def test_except_exception_cannot_swallow_lysis(tight_budget):
    src = (
        "def live(me):\n    try:\n        while True:\n            pass\n    except Exception:\n        return 'rest'\n"
    )
    v = admit(src)
    assert not v
    assert v.reasons == ["too slow: exceeded time budget"]


def test_finally_return_is_rejected_before_it_can_run(no_smoke_test):
    """A `return` in `finally` discards the exception on its way out, Lysis included, and it is
    instant, so no timer can help. The static gate refuses the construct; nothing is executed."""
    src = "def live(me):\n    try:\n        while True:\n            pass\n    finally:\n        return 'rest'\n"
    v = admit(src)
    assert v.reasons == ["finally not allowed"]


def test_except_laundering_is_rejected_before_it_can_run(no_smoke_test):
    """`except BaseException` is a NameError inside a genome, which an outer `except Exception`
    would catch after the loop has burst. The whitelist stops it at the inner handler."""
    src = (
        "def live(me):\n"
        "    try:\n"
        "        try:\n"
        "            while True:\n"
        "                pass\n"
        "        except BaseException:\n"
        "            pass\n"
        "    except Exception:\n"
        "        return 'rest'\n"
    )
    v = admit(src)
    assert len(v.reasons) == 1 and v.reasons[0].startswith(EXCEPT_RULE)


LAUNDERED = [
    (
        "local_rng",
        "def live(me):\n"
        "    KeyError = me.rng\n"
        "    try:\n"
        "        try:\n"
        "            while True:\n"
        "                pass\n"
        "        except KeyError:\n"
        "            pass\n"
        "    except Exception:\n"
        "        return 'rest'\n",
        "KeyError",
    ),
    (
        "local_int_outer_type_error",
        "def live(me):\n"
        "    ValueError = 5\n"
        "    try:\n"
        "        try:\n"
        "            while True:\n"
        "                pass\n"
        "        except ValueError:\n"
        "            pass\n"
        "    except TypeError:\n"
        "        return 'rest'\n",
        "ValueError",
    ),
    (
        "module_level_int",
        "ValueError = 5\n"
        "\n"
        "def live(me):\n"
        "    try:\n"
        "        try:\n"
        "            while True:\n"
        "                pass\n"
        "        except ValueError:\n"
        "            pass\n"
        "    except TypeError:\n"
        "        return 'rest'\n",
        "ValueError",
    ),
    (
        "unbound_local",
        "def live(me):\n"
        "    try:\n"
        "        try:\n"
        "            while True:\n"
        "                pass\n"
        "        except ValueError:\n"
        "            pass\n"
        "    except Exception:\n"
        "        ValueError = 5\n"
        "        return 'rest'\n",
        "ValueError",
    ),
    (
        "as_shadow",
        "def live(me):\n"
        "    try:\n"
        "        {}[1]\n"
        "    except KeyError as ValueError:\n"
        "        pass\n"
        "    try:\n"
        "        try:\n"
        "            while True:\n"
        "                pass\n"
        "        except ValueError:\n"
        "            pass\n"
        "    except Exception:\n"
        "        return 'rest'\n",
        "ValueError",
    ),
    (
        "parameter",
        "def helper(me, KeyError):\n"
        "    try:\n"
        "        try:\n"
        "            while True:\n"
        "                pass\n"
        "        except KeyError:\n"
        "            pass\n"
        "    except Exception:\n"
        "        return 'rest'\n"
        "\n"
        "def live(me):\n"
        "    return helper(me, me.rng)\n",
        "KeyError",
    ),
]


@pytest.mark.parametrize("name,source,rebound", LAUNDERED, ids=[r[0] for r in LAUNDERED])
def test_rebound_except_name_is_rejected_before_it_can_run(name, source, rebound, no_smoke_test):
    """`except KeyError:` where KeyError is bound to anything but an exception class, whether
    locally, at module level, as a parameter, through `as`, or merely later in the function
    (which makes the name an unbound local), is a TypeError or UnboundLocalError raised while
    the Lysis is being matched. Both are Exceptions, so an outer `except Exception:` or
    `except TypeError:` catches one after the loop has burst, with the one-shot timer already
    spent. Before the rebind rule every genome here was admitted in about 0.8 s: forty bursts,
    each swallowed. Now nothing is executed."""
    v = admit(source)
    assert v.reasons == [f"cannot rebind {rebound}"]


def test_loop_after_a_laundered_lysis_is_rejected_before_it_can_run(tight_budget):
    """The worst case of the above: a genome that loops in the outer handler runs unbounded
    after its Lysis, with no timer left, and in the dish there is no ceiling. Admitted through
    the child interpreter so that a regression is a timeout and not a hung suite."""
    src = LAUNDERED[0][1].replace("        return 'rest'\n", "        while True:\n            pass\n")
    t0 = time.perf_counter()
    v = admit_isolated(src, timeout=5.0)
    assert time.perf_counter() - t0 < 5.0
    assert v.reasons == ["cannot rebind KeyError"]


def test_recursion_bomb_throws():
    v = admit("def live(me):\n    return live(me)\n")
    assert not v
    assert v.reasons[0].startswith("threw on tick 0: RecursionError")


def test_module_level_work_is_budgeted(tight_budget):
    """The static gate refuses a call at module level, so this genome never compiles through
    `admit`; if one ever got past it, the smoke test budgets the module body as well. Both
    gates are asserted so that neither can quietly stand in for the other."""
    src = "x = sum(i for i in range(10**9))\n" + LIVE_REST
    assert inspect(src).reasons == [CONSTANT_RULE]
    t0 = time.perf_counter()
    v = smoke_test(src)
    assert time.perf_counter() - t0 < 2.0
    assert not v
    assert v.reasons == ["too slow: module level exceeded time budget"]


def test_genome_that_throws_fails_the_smoke_test():
    v = admit("def live(me):\n    return me.around[99]\n")
    assert not v
    assert v.reasons[0].startswith("threw on tick 0: IndexError")


def test_unknown_action_fails_the_smoke_test():
    v = admit("def live(me):\n    return 'photosynthesize'\n")
    assert not v
    assert v.reasons == ["returned an unknown action: 'photosynthesize'"]


# --- positive: what must get through -----------------------------------------


def test_fallback_genesis_is_admitted():
    v = admit(FALLBACK_GENESIS)
    assert v
    assert v.reasons == []


def test_fixture_set_holds_ten_fossils():
    assert len(fixture_genomes()) == 10


@pytest.mark.parametrize("stem,source", fixture_genomes(), ids=[s for s, _ in fixture_genomes()])
def test_fixture_genomes_are_admitted(stem, source):
    v = admit(source)
    assert v, (stem, v.reasons)
    assert v.reasons == []


BENIGN = '''\
"""A genome may carry a docstring."""

THRESH = 0.5
LIMIT: int = 3
HALF = THRESH / 2
NAMES = ("N", "NE", "E", "SE") + ("S", "SW", "W", "NW")
LABEL = f"{THRESH:.1f}"
R = random


def _helper(me, _tmp, names=NAMES, k: int = LIMIT) -> float:
    return sum(x for x in me.around if x > THRESH) + _tmp + R.random() * k + len(names[0])


def live(me):
    _ = me.tick
    err = None
    try:
        n = int("x")
    except ValueError as e:
        err = e
        n = LIMIT
    del err
    try:
        me.memory["seen"] = me.around[me.memory["dir"]]
    except (KeyError, IndexError) as e:
        me.memory["dir"] = len(str(e)) % 8
    match me.age % 3:
        case 0:
            me.memory["mood"] = NAMES[me.memory["dir"]]
        case _:
            pass
    label = f"{me.energy:.2f}{LABEL}"
    if (roll := random.random()) < HALF and len(label) > n and roll < 1.0:
        return ("move", random.choice(range(8)))
    return "eat" if _helper(me, 0.0) >= 0 else "rest"
'''


def test_benign_constructs_are_admitted():
    """Generator expressions, try/except on the whitelisted names (alone, as a tuple, with `as`),
    `del` of a local, `match` with a wildcard, a walrus, f-strings, local underscore names,
    module-level constants with arithmetic, a tuple and an alias of `random`, a helper with
    constant defaults and annotations, a docstring and the random functions in scope are all
    legal."""
    v = admit(BENIGN)
    assert v, v.reasons


def test_set_is_not_in_scope():
    """The static gate refuses the name (above); the namespace does not hold it either, so a
    genome that reached `set` some other way would find a NameError, and `frozenset` was never
    there. Dicts stay: they iterate in insertion order whatever the hash seed."""
    assert "set" not in SAFE_BUILTINS and "frozenset" not in SAFE_BUILTINS
    assert "dict" in SAFE_BUILTINS


def test_random_in_scope_is_the_dish_rng():
    src = "def live(me):\n    return ('move', random.randrange(8))\n"
    fn = compile_genome(src, random.Random(7))
    ref = random.Random(7)
    assert [fn(None)[1] for _ in range(5)] == [ref.randrange(8) for _ in range(5)]
    # the module is out of reach: no SystemRandom, no fresh unseeded generators
    fn = compile_genome("def live(me):\n    return random.SystemRandom\n", random.Random(7))
    with pytest.raises(AttributeError):
        fn(None)


# --- isolation: admit_isolated in a child interpreter -------------------------


def _no_membrane_children() -> bool:
    if shutil.which("pgrep") is None:
        pytest.skip("pgrep is not available")
    r = subprocess.run(["pgrep", "-P", str(os.getpid()), "-f", "bio.membrane"], capture_output=True, text=True)
    return r.stdout.strip() == ""


def test_isolated_busy_loop_is_too_slow():
    t0 = time.perf_counter()
    v = admit_isolated("def live(me):\n    while True:\n        pass\n", timeout=10.0)
    assert time.perf_counter() - t0 < 5.0
    assert not v
    assert v.reasons == ["too slow: exceeded time budget"]
    assert _no_membrane_children()


def test_isolated_uninterruptible_loop_hits_the_timeout():
    """A C-level loop cannot be interrupted by the alarm; the child is killed instead."""
    t0 = time.perf_counter()
    v = admit_isolated("def live(me):\n    return sum(range(10**12))\n", timeout=1.0)
    elapsed = time.perf_counter() - t0
    assert 1.0 <= elapsed < 6.0
    assert not v
    assert v.reasons == ["too slow: smoke test timed out"]
    assert _no_membrane_children()


def test_isolated_admits_the_founder():
    v = admit_isolated(FALLBACK_GENESIS)
    assert v
    assert v.reasons == []


def test_isolated_reports_a_crashed_child(monkeypatch):
    class Crashed:
        stdout = "Traceback (most recent call last):\n"
        stderr = "boom"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Crashed())
    v = admit_isolated(LIVE_REST)
    assert not v
    assert v.reasons[0].startswith("membrane crashed")


# --- in the dish: lysis is a death, not a crash --------------------------------


def test_throwing_genome_is_lysed_in_the_dish(monkeypatch):
    """Every cell bursts on the tick it throws, and its necromass goes back to the tile."""
    monkeypatch.setattr(Dish, "_diffuse", lambda self: None)  # keep the agar still so the return is exact
    src = "def live(me):\n    if me.tick == 3:\n        return me.around[99]\n    return 'rest'\n"
    d = make_dish(genome=src, replenish=0.0)
    n = len(d.cells)
    for _ in range(3):
        d.step()
    assert d.tick == 3 and len(d.cells) == n and d.deaths["lysed"] == 0
    before = {(c.x, c.y): (d.nutrient[c.y][c.x], c.energy) for c in d.cells.values()}
    d.step()
    assert not d.cells
    assert d.deaths["lysed"] == n
    assert d.deaths["starved"] == 0
    for (x, y), (nut, energy) in before.items():
        back = (energy - config.BASAL_COST) * config.NECROMASS + config.CORPSE_NUTRIENT
        assert d.nutrient[y][x] == pytest.approx(min(1.0, nut + back))
    d.step()
    assert d.tick == 5


def test_busy_genome_is_lysed_within_a_tick(tight_budget):
    d = make_dish(genome="def live(me):\n    while True:\n        pass\n", n=1)
    t0 = time.perf_counter()
    d.step()
    assert time.perf_counter() - t0 < 1.0
    assert not d.cells
    assert d.deaths["lysed"] == 1
