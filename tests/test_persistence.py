"""dish.json: a saved dish is an exact twin of the one that was running."""

from __future__ import annotations

import copy
import json

from conftest import dish_state, make_dish

from bio import config
from bio.culture import FALLBACK_GENESIS
from bio.dish import Dish

# the founder, remembering how many ticks it has lived, so primitive memory is exercised
MEMORY_GENOME = FALLBACK_GENESIS.replace(
    "def live(me):\n", "def live(me):\n    me.memory['n'] = me.memory.get('n', 0) + 1\n"
)


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
