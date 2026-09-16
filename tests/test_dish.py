"""The dish's memory: a daughter's is her own, a dish written to a dict comes back as exactly the dish
it was, and an inoculum placed at a point lands on the nearest free tiles."""

import json

from bio.culture import FALLBACK_GENESIS
from bio.dish import Dish
from bio.membrane import memory_fault

from .conftest import WANDERER


def dish_state(d: Dish) -> tuple:
    return (
        d.tick,
        [(k, c.strain, c.energy, c.age, c.born, c.memory) for k, c in d.cells.items()],
        d.rng.getstate(),
        d.nutrient,
        d.pheromone,
        list(d.history),
        d.births,
        dict(d.deaths),
    )


def test_a_daughter_inherits_a_copy_of_her_mothers_memory_not_the_memory_itself():
    """WANDERER keeps a list in memory and mutates it in place. Every cell must own its list:
    a shared one would make kin write into each other's memory, and would make the dish
    impossible to save and resume exactly, since a save separates what was shared."""
    dish = Dish("test", width=24, height=12)
    dish.register("w", WANDERER)
    dish.inoculate("w")
    for _ in range(60):
        dish.step()
    trails = [c.memory["trail"] for c in dish.cells.values() if "trail" in c.memory]
    assert len(trails) > 5, "the colony should have grown"
    assert len({id(t) for t in trails}) == len(trails), "two cells share one trail list"
    mother = dish.place(0, 6, "w", memory={"trail": [1, 2], "deep": {"k": [3]}})
    daughter = dish.place(1, 6, "w", memory=mother.memory)
    daughter.memory["trail"].append(9)
    daughter.memory["deep"]["k"].append(4)
    assert mother.memory == {"trail": [1, 2], "deep": {"k": [3]}}


def test_dish_dict_is_lossless():
    """A dish serialised through JSON and read back is a twin: cells, energies, memories, agar,
    pheromone and the RNG all continue identically for 100 more ticks. WANDERER makes every one
    of those load-bearing; before energies were stored exactly the twins parted at the first
    tick."""
    dish = Dish("test", width=24, height=12)
    dish.register("w", WANDERER)
    dish.inoculate("w")
    for _ in range(100):
        dish.step()
    assert len(dish.cells) > 5
    assert any(isinstance(c.memory.get("trail"), list) for c in dish.cells.values())
    twin = Dish.from_dict(json.loads(json.dumps(dish.to_dict())))
    assert dish_state(twin) == dish_state(dish)
    for _ in range(100):
        dish.step()
        twin.step()
        assert dish_state(twin) == dish_state(dish)
    assert dish.tick == 200


def test_rounded_energy_would_not_have_been_lossless():
    """The control for the test above: a twin whose energies are rounded to four decimals, as the
    dish used to save them, leaves the trajectory."""
    dish = Dish("test", width=24, height=12)
    dish.register("w", WANDERER)
    dish.inoculate("w")
    for _ in range(100):
        dish.step()
    d = dish.to_dict()
    d["cells"] = [[x, y, s, round(e, 4), age, born, mem] for x, y, s, e, age, born, mem in d["cells"]]
    twin = Dish.from_dict(json.loads(json.dumps(d)))
    diverged = False
    for _ in range(100):
        dish.step()
        twin.step()
        if dish_state(twin) != dish_state(dish):
            diverged = True
            break
    assert diverged


def test_memory_survives_the_dict_exactly():
    """Everything the memory rule admits comes back from the dict with its types: a tuple, a list
    of 300 ints, a dict keyed by an int, a bool, None and a float, a key beginning with `~`, an
    int wider than 64 bits and an int key at the top level. Hand-made memory the rule would
    refuse (a set, a range) is still written, as its str(), and the save does not raise."""
    dish = Dish("test", width=24, height=12)
    dish.register("f", FALLBACK_GENESIS)
    memory = {
        "n": 3,
        "trail": [1, 2, [3, (4,)]],
        "pt": (4, 5),
        "big": list(range(300)),
        "counts": {3: 1, True: 2, None: 3, 0.5: 4},
        "~odd": 1,
        "wide": 2**70,
        7: "int key",
    }
    assert memory_fault(memory) is None
    dish.place(12, 6, "f", memory=memory)
    twin = Dish.from_dict(json.loads(json.dumps(dish.to_dict())))
    (cell,) = twin.cells.values()
    assert cell.memory == memory and list(cell.memory) == list(memory)
    assert type(cell.memory["pt"]) is tuple and type(cell.memory["trail"][2][1]) is tuple
    assert [type(k) for k in cell.memory["counts"]] == [int, bool, type(None), float]
    assert 7 in cell.memory and "7" not in cell.memory
    assert type(cell.memory["wide"]) is int
    dish.place(13, 6, "f", memory={"odd": {1, 2}, "r": range(3), "grid": {(0, 1): 2}})
    blob = json.loads(json.dumps(dish.to_dict()))
    (mem,) = [row[6] for row in blob["cells"] if row[0] == 13]
    assert mem == {"odd": "{1, 2}", "r": "range(0, 3)", "grid": {"~d": [[{"~t": [0, 1]}, 2]]}}
    assert Dish.from_dict(blob).cells[(13, 6)].memory == {"odd": "{1, 2}", "r": "range(0, 3)", "grid": {(0, 1): 2}}


def test_inoculate_at_takes_the_nearest_free_tiles_and_leaves_the_rng_alone():
    dish = Dish("test", width=24, height=12)
    dish.register("f", FALLBACK_GENESIS)
    dish.place(2, 6, "f")  # already taken: the inoculum must go around it
    before = dish.rng.getstate()
    placed = dish.inoculate("f", 3, at=(2, 6), memory={"trail": [1]})
    assert placed == 3
    assert dish.rng.getstate() == before
    # nearest by the dish's 2:1 metric: the horizontal neighbours are a quarter step away, (2,5) a whole one
    assert set(dish.cells) == {(2, 6), (1, 6), (3, 6), (2, 5)}
    trails = [c.memory["trail"] for c in dish.cells.values() if c.memory]
    assert len(trails) == 3 and all(t == [1] for t in trails)
    assert len({id(t) for t in trails}) == 3, "each cell must get its own copy of the memory"


def test_inoculate_without_a_point_is_seeded_by_the_dish_rng():
    a, b = Dish("test", width=24, height=12), Dish("test", width=24, height=12)
    for d in (a, b):
        d.register("f", FALLBACK_GENESIS)
        d.inoculate("f")
    assert list(a.cells) == list(b.cells)
    assert a.rng.getstate() == b.rng.getstate() != Dish("test", width=24, height=12).rng.getstate()
