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
import time

import pytest
from conftest import fixture_genomes, make_dish

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
)

LIVE_REST = "def live(me):\n    return 'rest'\n"
EXCEPT_RULE = "except may only name"


@pytest.fixture
def tight_budget(monkeypatch):
    """The production budget, so tests about the budget stay fast."""
    monkeypatch.setattr(config, "CELL_TIME_BUDGET", 0.004)


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
    and every class the except whitelist admits sits below it."""
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


def test_finally_return_is_rejected_before_it_can_run(tight_budget):
    """A `return` in `finally` discards the exception on its way out, Lysis included, and it is
    instant, so no timer can help. The static gate refuses the construct; nothing is executed."""
    src = "def live(me):\n    try:\n        while True:\n            pass\n    finally:\n        return 'rest'\n"
    t0 = time.perf_counter()
    v = admit(src)
    assert time.perf_counter() - t0 < 0.5
    assert v.reasons == ["finally not allowed"]


def test_except_laundering_is_rejected_before_it_can_run(tight_budget):
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
    t0 = time.perf_counter()
    v = admit(src)
    assert time.perf_counter() - t0 < 0.5
    assert len(v.reasons) == 1 and v.reasons[0].startswith(EXCEPT_RULE)


def test_recursion_bomb_throws():
    v = admit("def live(me):\n    return live(me)\n")
    assert not v
    assert v.reasons[0].startswith("threw on tick 0: RecursionError")


def test_module_level_work_is_budgeted(tight_budget):
    src = "x = sum(i for i in range(10**9))\n" + LIVE_REST
    t0 = time.perf_counter()
    v = admit(src)
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


def _helper(me, _tmp):
    return sum(x for x in me.around if x > THRESH) + _tmp


def live(me):
    _ = me.tick
    try:
        n = int("x")
    except ValueError:
        n = LIMIT
    try:
        me.memory["seen"] = me.around[me.memory["dir"]]
    except (KeyError, IndexError) as e:
        me.memory["dir"] = len(str(e)) % 8
    label = f"{me.energy:.2f}"
    if random.random() < 0.5 and len(label) > n:
        return ("move", random.choice(range(8)))
    return "eat" if _helper(me, 0.0) >= 0 else "rest"
'''


def test_benign_constructs_are_admitted():
    """Generator expressions, try/except on the whitelisted names (alone, as a tuple, with `as`),
    f-strings, local underscore names, module-level constants, a docstring and the random
    functions in scope are all legal."""
    v = admit(BENIGN)
    assert v, v.reasons


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
