"""The culture end to end, in a temporary vessel, with a mind that never calls out."""

from __future__ import annotations

import json

import pytest
from conftest import dish_state

from bio import config
from bio.culture import FALLBACK_GENESIS, Culture
from bio.membrane import inspect
from bio.mind import Mind

# admitted under 0.1.0, refused now: the construct this release closes
RELIC = "def live(me):\n    try:\n        return 'eat'\n    except:\n        return 'rest'\n"


def _events(kind: str) -> list[dict]:
    if not config.EVENTS.exists():
        return []
    return [e for e in (json.loads(ln) for ln in config.EVENTS.read_text().splitlines()) if e["kind"] == kind]


def test_culture_germinates_runs_and_reloads_in_a_temp_vessel(monkeypatch):
    monkeypatch.setenv("BIOTIC_WIDTH", "24")
    monkeypatch.setenv("BIOTIC_HEIGHT", "12")
    mind = Mind()
    assert not mind.awake  # the autouse vessel fixture leaves it no key and no local endpoint

    c = Culture.germinate("test", mind, fresh=True)
    assert (c.dish.w, c.dish.h) == (24, 12)
    (founder,) = c.registry.strains.values()
    assert founder.source == FALLBACK_GENESIS
    assert c.dish.genomes == {founder.id: FALLBACK_GENESIS}
    fossils = list(config.SOMA.glob("*.py"))
    assert [p.name.split("_")[0] for p in fossils] == [founder.id]

    c.run(ticks=60, tick_seconds=0)
    c.mutagen.join(timeout=5)
    assert not c.mutagen.is_alive()
    assert c.mutagen.state == "dormant"
    assert c.dish.tick == 60
    events = [json.loads(ln) for ln in config.EVENTS.read_text().splitlines()]
    assert {"mind", "genesis"} <= {e["kind"] for e in events}

    again = Culture.load(Mind())
    assert dish_state(again.dish) == dish_state(c.dish)
    assert again.registry.strains.keys() == c.registry.strains.keys()


def test_reloaded_culture_rolls_mutations_where_the_running_one_would(make_culture):
    """The culture's own generator decides which divisions roll a mutation. It is saved with
    the dish, so a resumed culture continues the same sequence instead of starting it over."""
    c = make_culture()
    for _ in range(40):
        c.step()
    c.save()
    again = Culture.load(Mind())
    assert again.rng.getstate() == c.rng.getstate()
    assert [again.rng.random() for _ in range(5)] == [c.rng.random() for _ in range(5)]
    blob = json.loads(config.DISH_FILE.read_text())
    del blob["culture"]  # a dish.json from before the generator was saved
    config.DISH_FILE.write_text(json.dumps(blob))
    assert Culture.load(Mind()).dish.tick == c.dish.tick


def test_save_failure_does_not_stop_the_culture(make_culture, monkeypatch, tmp_path):
    """A dish.json that cannot be written, for whatever reason, is logged once as a `freezer`
    event and tried again at every later save; the loop goes on. run() saves every 150 ticks
    and once more on the way out, so two failures here make one event."""
    c = make_culture()
    monkeypatch.setattr(config, "DISH_FILE", tmp_path / "nowhere" / "dish.json")  # OSError: no such directory
    c.run(ticks=150, tick_seconds=0)
    c.mutagen.join(timeout=5)
    assert c.dish.tick == 150 and c.dish.cells
    (ev,) = _events("freezer")
    assert ev["msg"].startswith("dish.json not written from tick 150") and ev["tick"] == 150
    monkeypatch.setattr(config, "DISH_FILE", tmp_path / "vessel" / "dish.json")
    c.save()
    assert config.DISH_FILE.exists()
    assert [e["msg"] for e in _events("freezer")][-1] == "dish.json written again at tick 150"
    # the other way a save can fail: the blob itself will not serialise
    monkeypatch.setattr(c.dish, "to_dict", lambda: {"cells": object()})
    c.save()
    assert len(_events("freezer")) == 3
    assert Culture.load(Mind()).dish.tick == 150  # the last good dish.json stands


def test_thawed_strain_the_membrane_now_refuses_is_lysed_when_the_culture_runs(make_culture):
    """A dish saved under older rules may hold strains the static gate now refuses; they do
    not get to run. Loading leaves the dish as it was (`biotic status` must not rewrite what it
    reads); run() screens every strain first, lyses the ones the gate refuses, and says why."""
    assert inspect(RELIC).reasons == ["bare except not allowed"]
    c = make_culture()
    (founder,) = c.registry.strains
    relic = c.registry.new(RELIC, founder, 0, "relic", "")
    c.dish.register(relic.id, RELIC)
    placed = [c.dish.place(x, 1, relic.id) for x in (8, 10, 12)]
    assert all(placed)
    c.step()  # one tick as a 0.1.0 culture: the registry records the relic's peak
    c.save()

    again = Culture.load(Mind())
    assert again.dish.census()[relic.id] == 3
    assert _events("nonviable") == []

    lysed_before = again.dish.deaths["lysed"]
    again.run(ticks=1, tick_seconds=0)
    again.mutagen.join(timeout=5)
    census = again.dish.census()
    assert relic.id not in census and census[founder] > 0
    assert again.dish.deaths["lysed"] == lysed_before + 3
    assert relic.id not in again.dish.genomes and founder in again.dish.genomes
    (ev,) = _events("nonviable")
    assert ev["strain"] == relic.id
    assert ev["msg"] == "relic no longer passes the membrane — bare except not allowed; 3 cells lysed"
    assert again.registry.strains[relic.id].extinct_at == 2
    assert [e["strain"] for e in _events("extinct")] == [relic.id]
    assert relic.id not in Culture.load(Mind()).dish.genomes  # the save on the way out carries it


def test_network_guard_is_armed():
    """An awake mind that tries to think hits the suite's guard, not the network, so a test
    that forgets to fake Mind.think fails loudly instead of spending from the key."""
    m = Mind()
    m.key = "test-key"
    assert m.awake
    with pytest.raises(AssertionError, match="network"):
        m.think("system", "user")
