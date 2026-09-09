"""dish.json: a saved dish is an exact twin of the one that was running."""

from __future__ import annotations

import copy
import json

from conftest import dish_state, make_dish

from bio import config
from bio.culture import FALLBACK_GENESIS
from bio.dish import Dish
from bio.membrane import inspect

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
