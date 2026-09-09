"""The culture end to end, in a temporary vessel, with a mind that never calls out."""

from __future__ import annotations

import json

import pytest
from conftest import dish_state

from bio.culture import FALLBACK_GENESIS, Culture
from bio.mind import Mind


def test_culture_germinates_runs_and_reloads_in_a_temp_vessel(vessel, dormant_mind):
    c = Culture.germinate("test", dormant_mind, fresh=True)
    assert (c.dish.w, c.dish.h) == (24, 12)
    (founder,) = c.registry.strains.values()
    assert founder.source == FALLBACK_GENESIS
    assert c.dish.genomes == {founder.id: FALLBACK_GENESIS}
    fossils = list((vessel / "soma").glob("*.py"))
    assert [p.name.split("_")[0] for p in fossils] == [founder.id]

    c.run(ticks=60, tick_seconds=0)
    c.mutagen.join(timeout=5)
    assert not c.mutagen.is_alive()
    assert c.mutagen.state == "dormant"
    assert c.dish.tick == 60

    rows = (vessel / "vessel" / "curve.csv").read_text().splitlines()
    assert rows[0] == "tick,population,strains,nutrient,phase,births,starved,lysed,senescent"
    assert [int(r.split(",")[0]) for r in rows[1:]] == [10, 20, 30, 40, 50, 60]
    events = [json.loads(ln) for ln in (vessel / "vessel" / "events.jsonl").read_text().splitlines()]
    assert {"mind", "genesis"} <= {e["kind"] for e in events}

    again = Culture.load(dormant_mind)
    assert dish_state(again.dish) == dish_state(c.dish)
    assert again.registry.strains.keys() == c.registry.strains.keys()


def test_network_guard_is_armed():
    """An awake mind that tries to think hits the suite's guard, not the network.
    A test that forgets to fake Mind.think fails loudly instead of spending the key."""
    m = Mind()
    m.key = "test-key"
    m.base = "https://example.invalid"
    assert m.awake
    with pytest.raises(RuntimeError, match="network"):
        m.think("system", "user")
