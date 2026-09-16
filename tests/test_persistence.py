"""dish.json: a saved dish is an exact twin of the one that was running."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys

from conftest import dish_state, make_dish

from bio import config
from bio.culture import FALLBACK_GENESIS
from bio.dish import MEMORY_CHARS, MEMORY_INT, MEMORY_KEYS, Dish, _jsonable
from bio.membrane import admit, inspect

# the founder, remembering how many ticks it has lived, so primitive memory is exercised
MEMORY_GENOME = FALLBACK_GENESIS.replace(
    "def live(me):\n", "def live(me):\n    me.memory['n'] = me.memory.get('n', 0) + 1\n"
)

# the fullest module level the membrane admits: constants, arithmetic on them, a tuple, an
# f-string, math.pi, an alias of the generator, and a helper with constant defaults and
# annotations; live() draws through the alias every tick and counts the ticks it has lived
MODULE_GENOME = '''\
"""A genome with module-level state, all of it constant."""

THRESH = 0.04
HALF = THRESH / 2
DIRS = (0, 1, 2, 3, 4, 5, 6, 7)
LABEL = f"{THRESH:.2f}"
PI: float = math.pi
R = random


def wander(me, dirs=DIRS, jitter: float = HALF):
    free = [d for d in dirs if not me.crowd[d]]
    return ("move", R.choice(free)) if free and R.random() < jitter * 10 else "rest"


def live(me):
    me.memory["n"] = me.memory.get("n", 0) + 1
    free = [d for d in DIRS if not me.crowd[d]]
    if me.energy > 1.0 and free:
        return "divide"
    if me.here > THRESH:
        return "eat"
    return wander(me)
'''


def _grown(ticks: int = 120) -> Dish:
    d = make_dish(genome=MEMORY_GENOME)
    for _ in range(ticks):
        d.step()
    return d


def test_dish_round_trips_through_dict():
    d = _grown()
    blob = json.loads(json.dumps(d.to_dict()))
    clone = Dish.from_dict(copy.deepcopy(blob))
    assert dish_state(clone) == dish_state(d)
    assert json.loads(json.dumps(clone.to_dict())) == blob
    assert any(c.memory.get("n") for c in clone.cells.values())


def test_resumed_dish_is_an_exact_twin():
    """The next 50 ticks of a reloaded dish match the dish that never left memory,
    RNG state included. This is what the freezer stands on."""
    d = _grown()
    clone = Dish.from_dict(json.loads(json.dumps(d.to_dict())))
    for _ in range(50):
        d.step()
        clone.step()
        assert dish_state(clone) == dish_state(d), f"diverged at tick {d.tick}"


def test_module_level_draw_is_refused_because_it_would_not_resume():
    """`Dish.from_dict` compiles its genomes afresh, so module level runs again on the first tick
    after a load. A module-level `random.random()` draws from the generator at a different point
    than the original run did and hands every cell a different constant: before the rule, such a
    dish diverged from its twin on that tick. The membrane refuses it, so no admitted genome can."""
    src = "BOLD = random.random()\n" + FALLBACK_GENESIS
    assert inspect(src).reasons == [
        "module-level values must be constants (numbers, strings, tuples; no calls, lists or dicts)"
    ]


def test_resumed_dish_with_module_level_constants_is_an_exact_twin():
    """What module level may hold changes nothing when it runs again: a genome using every
    module-level form the gate admits resumes exactly, drawing through its alias of the
    generator every tick."""
    assert inspect(MODULE_GENOME).reasons == []
    d = make_dish(genome=MODULE_GENOME)
    for _ in range(120):
        d.step()
    clone = Dish.from_dict(json.loads(json.dumps(d.to_dict())))
    for _ in range(50):
        d.step()
        clone.step()
        assert dish_state(clone) == dish_state(d), f"diverged at tick {d.tick}"
    assert d.births > 0 and any(c.memory.get("n") for c in d.cells.values())


def test_resumed_dish_is_an_exact_twin_in_another_process():
    """A resume is a process boundary, and the twin above is checked inside one interpreter,
    where anything that depends on the hash seed agrees with itself. Here the saved dish is
    thawed by a child interpreter under a different `PYTHONHASHSEED` and stepped fifty ticks,
    and its save must equal the parent's. This is what refusing sets buys: before the rule a
    genome that walked a set of strings diverged here and nowhere else."""
    d = make_dish(genome=MODULE_GENOME)
    for _ in range(120):
        d.step()
    frozen = json.dumps(d.to_dict())
    for _ in range(50):
        d.step()
    want = json.loads(json.dumps(d.to_dict()))
    child = (
        "import json, sys\n"
        "from bio import config\n"
        "from bio.dish import Dish\n"
        f"config.CELL_TIME_BUDGET = {config.CELL_TIME_BUDGET!r}\n"
        "d = Dish.from_dict(json.loads(sys.stdin.read()))\n"
        "for _ in range(50):\n"
        "    d.step()\n"
        "print(json.dumps(d.to_dict()))\n"
    )
    seed = "2" if os.environ.get("PYTHONHASHSEED") == "1" else "1"
    r = subprocess.run(
        [sys.executable, "-c", child],
        input=frozen,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(config.ROOT),
        env={**os.environ, "PYTHONHASHSEED": seed},
    )
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == want


def test_memory_keeps_primitives_exactly_and_bounds_the_rest():
    """What dish.json keeps of me.memory: ints that fit a signed 64-bit word, floats, strings,
    bools and None as they are; a wider int, and anything that is not a primitive, as the first
    80 characters of its str(). bool is an int and must stay a bool. An int with no decimal
    form at all (past sys.get_int_max_str_digits()) and a list nested past the recursion limit
    get a placeholder instead of raising, and non-string keys are stringified the same way."""
    deep: list = []
    for _ in range(50_000):  # one level per tick is enough; str() of this raises RecursionError on every Python
        deep = [deep]
    m = {
        "hi": MEMORY_INT - 1,
        "lo": -MEMORY_INT,
        "wide": MEMORY_INT,
        "neg_wide": -MEMORY_INT - 1,
        "huge": 10**5000,
        "in_list": [10**5000],
        "deep": deep,
        "f": 0.1,
        "s": "x" * 200,
        "t": True,
        "n": None,
        "lst": list(range(100)),
        3: "int key",
        10**5000: "unprintable key",
    }
    out = _jsonable(m)
    assert out["hi"] == MEMORY_INT - 1 and type(out["hi"]) is int
    assert out["lo"] == -MEMORY_INT and type(out["lo"]) is int
    assert out["wide"] == str(MEMORY_INT) and out["neg_wide"] == str(-MEMORY_INT - 1)
    assert out["huge"] == "<int>" and out["in_list"] == "<list>" and out["deep"] == "<list>"
    assert out["f"] == 0.1 and out["s"] == "x" * 200 and out["t"] is True and out["n"] is None
    assert out["lst"] == str(list(range(100)))[:MEMORY_CHARS]
    assert out["3"] == "int key" and out["<int>"] == "unprintable key"
    assert json.loads(json.dumps(out)) == out
    assert len(_jsonable({i: i for i in range(MEMORY_KEYS + 20)})) == MEMORY_KEYS


def test_memory_int_past_the_json_limit_does_not_break_the_save():
    """A genome that multiplies a counter every tick is admitted (the smoke test sees forty
    rounds of it) and reaches 4300 digits, where json.dumps refuses the int, in the dish. That
    used to make Culture.save() raise at the next save and kill the loop; now the int is kept as
    text and the save goes through."""
    src = FALLBACK_GENESIS.replace(
        "def live(me):\n", "def live(me):\n    me.memory['x'] = me.memory.get('x', 1) * 10**100\n"
    )
    assert admit(src), admit(src).reasons
    d = make_dish(genome=src)
    for _ in range(60):
        d.step()
    widest = max(c.memory["x"] for c in d.cells.values())
    assert widest.bit_length() > 4300 * 3  # past the decimal limit: str(widest) itself would raise
    blob = json.loads(json.dumps(d.to_dict()))
    assert all(isinstance(mem["x"], str) for *_, mem in blob["cells"])
    clone = Dish.from_dict(blob)
    clone.step()  # the twin does not hold for a stringified value, but the dish still runs
    assert clone.tick == d.tick + 1


def test_from_dict_tolerates_missing_optional_keys():
    """Older dish.json files may lack these; loading falls back to defaults."""
    d = _grown(20)
    blob = d.to_dict()
    for key in ("history", "deaths", "births", "replenish", "rng"):
        del blob[key]
    clone = Dish.from_dict(blob)
    assert clone.tick == d.tick
    assert clone.census() == d.census()
    assert clone.replenish == config.REPLENISH
    assert clone.births == 0
    assert list(clone.history) == []
    assert clone.deaths == {"starved": 0, "lysed": 0, "senescent": 0, "killed": 0}
