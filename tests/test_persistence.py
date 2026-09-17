"""dish.json: a saved dish is an exact twin of the one that was running, whatever its cells keep in memory."""

from __future__ import annotations

import copy
import json
import math
import os
import subprocess
import sys

import pytest

from bio import config
from bio.culture import FALLBACK_GENESIS
from bio.dish import Dish, decode_memory, encode_memory
from bio.membrane import admit, inspect, memory_fault

from .conftest import MODULE_GENOME, TOO_MUCH_GENOME, TUPLE_GENOME, dish_state, make_dish

# the founder, remembering how many ticks it has lived, so primitive memory is exercised
MEMORY_GENOME = FALLBACK_GENESIS.replace(
    "def live(me):\n", "def live(me):\n    me.memory['n'] = me.memory.get('n', 0) + 1\n"
)


def _grown(ticks: int = 120) -> Dish:
    d = make_dish(genome=MEMORY_GENOME)
    for _ in range(ticks):
        d.step()
    return d


def _trajectory(d: Dish) -> tuple:
    """Where the cells are and what the dish has done, without the memories themselves."""
    return (
        d.tick,
        sorted((c.x, c.y, c.strain, c.energy, c.age) for c in d.cells.values()),
        d.rng.getstate(),
        d.births,
        dict(d.deaths),
    )


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


@pytest.mark.parametrize("genome", [MODULE_GENOME, TUPLE_GENOME], ids=["module_level", "tuple_memory"])
def test_resumed_dish_is_an_exact_twin_in_another_process(genome):
    """A resume is a process boundary, and the twins above are checked inside one interpreter,
    where anything that depends on the hash seed agrees with itself. Here the saved dish is
    thawed by a child interpreter under a different `PYTHONHASHSEED` and stepped fifty ticks,
    and its save must equal the parent's. This is what refusing sets buys: before the rule a
    genome that walked a set of strings diverged here and nowhere else. The tuple genome's
    save carries tuples, int keys and a `~` key through the tags, in insertion order."""
    d = make_dish(genome=genome)
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
    assert d.births > 0 and len(d.cells) > 5


# --- what a cell keeps in memory comes back exactly ---------------------------------------------


def test_memory_codec_is_the_identity_on_what_the_rule_admits():
    """encode_memory tags what JSON cannot tell apart and decode_memory undoes the tags: a tuple
    stays a tuple, an int, bool, None or float key stays what it was, a key beginning with `~` is
    a plain string again, an int of any width the cap admits and -0.0 come back exactly, and
    insertion order is kept at every level."""
    m = {
        "home": (1, 2),
        "counts": {3: 4, True: 5, None: 6, 1.5: 7, "~t": 8},
        "nested": [(), (1, (2, [3])), {"a": [1]}],
        "wide": 10**600,
        "neg": -(10**600),
        "zero": -0.0,
        "flags": [True, False, None],
        "text": 'é\n"\\',
        "~x": 1,
        "empty": ({}, [], ()),
    }
    assert memory_fault(m) is None
    back = decode_memory(json.loads(json.dumps(encode_memory(m))))
    assert back == m
    assert list(back) == list(m)
    assert type(back["home"]) is tuple
    assert type(back["nested"][1]) is tuple and type(back["nested"][1][1]) is tuple
    assert type(back["nested"][1][1][1]) is list and type(back["nested"][2]) is dict
    assert [type(k) for k in back["counts"]] == [int, bool, type(None), float, str]
    assert list(back["counts"]) == [3, True, None, 1.5, "~t"]
    assert type(back["wide"]) is int and type(back["neg"]) is int
    assert math.copysign(1.0, back["zero"]) == -1.0
    assert [type(x) for x in back["empty"]] == [dict, list, tuple]


def test_memory_encoding_is_pinned_and_untagged_json_reads_as_it_is():
    """The file format: a dict whose keys are all strings and none begins with `~` is a plain
    object; anything else is `~d` pairs; a tuple is `~t`. A dish.json or a sample written before
    the tags, or by hand with plain lists and string keys, decodes to what JSON gives, and a
    malformed tag is left as the plain JSON it is rather than raising."""
    tagged = '{"~d": [["home", {"~t": [1, 2]}], ["c", {"~d": [[3, 4]]}], ["~x", 1]]}'
    assert json.dumps(encode_memory({"home": (1, 2), "c": {3: 4}, "~x": 1})) == tagged
    plain = '{"n": 3, "trail": [1, 2], "d": {"k": {"~t": [1]}}}'
    assert json.dumps(encode_memory({"n": 3, "trail": [1, 2], "d": {"k": (1,)}})) == plain
    untagged = {"n": 3, "trail": [1, 2], "d": {"3": 4}, "s": "[1, 2, 3]"}
    assert decode_memory(untagged) == untagged
    assert decode_memory({"~t": [1]}) == {}, "a top level that is not a dict is an empty memory"
    assert decode_memory([1, 2]) == {} and decode_memory(None) == {}
    for odd in ({"~t": 5}, {"~d": [[1, 2, 3]]}, {"~d": [[[1], 2]]}, {"~d": 7}, {"~d": [["a"]]}, {"~t": [1], "x": 2}):
        assert decode_memory(odd) == odd, odd
    assert decode_memory({"~d": []}) == {}


def test_resumed_dish_is_an_exact_twin_for_memory_plain_json_cannot_carry():
    """TUPLE_GENOME keeps a tuple, a dict keyed by direction, a counter past 2**63 and a `~` key
    in memory, and branches on the tuple and the int key: the twin of a dish of it holds for
    fifty ticks, types included."""
    d = make_dish(genome=TUPLE_GENOME)
    for _ in range(120):
        d.step()
    mems = [c.memory for c in d.cells.values()]
    assert len(mems) > 5 and d.births > 0
    assert any(type(m.get("home")) is tuple for m in mems)
    assert any(any(type(k) is int for k in m.get("counts", {})) for m in mems)
    assert any(m.get("big", 0) > 2**63 for m in mems)
    assert all("~odd" in m for m in mems)
    clone = Dish.from_dict(json.loads(json.dumps(d.to_dict())))
    assert dish_state(clone) == dish_state(d)
    assert all(type(c.memory["home"]) is tuple for c in clone.cells.values())
    for _ in range(50):
        d.step()
        clone.step()
        assert dish_state(clone) == dish_state(d), f"diverged at tick {d.tick}"


def test_plain_json_memory_would_not_have_been_a_twin():
    """The control for the test above: a twin whose memories went through plain JSON, as the dish
    used to save them (a tuple as a list, an int key as a string), leaves the trajectory within
    fifty ticks, not only the memories."""
    d = make_dish(genome=TUPLE_GENOME)
    for _ in range(120):
        d.step()
    blob = json.loads(json.dumps(d.to_dict()))
    blob["cells"] = [
        [x, y, s, e, a, b, json.loads(json.dumps(decode_memory(mem)))] for x, y, s, e, a, b, mem in blob["cells"]
    ]
    twin = Dish.from_dict(blob)
    assert _trajectory(twin) == _trajectory(d), "the cells, the agar and the generator are the same at the save"
    assert all(type(c.memory["home"]) is list for c in twin.cells.values())
    diverged = None
    for _ in range(50):
        d.step()
        twin.step()
        if _trajectory(twin) != _trajectory(d):
            diverged = d.tick
            break
    assert diverged is not None


def test_a_memory_over_the_cap_bursts_the_cell_on_the_same_tick_in_both_twins():
    """TOO_MUCH_GENOME multiplies one int by 10**50 every tick: admitted (the smoke test's forty
    rounds stay under the cap) and over MEMORY_MAX_CHARS on the tick computed here, where every
    cell bursts — in the running dish and in a twin resumed from a save taken before it, on the
    same tick, since the rule runs at the same point of every tick in both."""
    v = admit(TOO_MUCH_GENOME)
    assert v, v.reasons
    cap = config.MEMORY_MAX_CHARS
    first = next(k for k in range(1, 10_000) if len(json.dumps({"x": 10 ** (50 * k)})) > cap)
    assert 30 < first <= 70, f"the cap moved: the lineage now bursts at tick {first}; pick a new multiplier"
    d = make_dish(genome=TOO_MUCH_GENOME)
    for _ in range(30):
        d.step()
    assert d.deaths["lysed"] == 0 and len(d.cells) > 5
    clone = Dish.from_dict(json.loads(json.dumps(d.to_dict())))
    assert dish_state(clone) == dish_state(d)
    lysed_at = None
    while d.tick < 70:
        d.step()
        clone.step()
        assert dish_state(clone) == dish_state(d), f"diverged at tick {d.tick}"
        if lysed_at is None and d.deaths["lysed"]:
            lysed_at = d.tick
            assert not d.cells, "every cell held the same int, so every cell burst on that tick"
    assert lysed_at == first
    assert d.deaths["lysed"] > 5 and clone.deaths["lysed"] == d.deaths["lysed"]


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
    assert clone.deaths == {"starved": 0, "lysed": 0, "senescent": 0, "killed": 0, "predated": 0}
