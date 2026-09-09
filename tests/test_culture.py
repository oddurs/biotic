"""The culture end to end, in a temporary vessel, with a mind that never calls out."""

from __future__ import annotations

import json

import pytest
from conftest import dish_state

from bio import config
from bio.culture import FALLBACK_GENESIS, Culture
from bio.mind import Mind


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


def test_network_guard_is_armed():
    """An awake mind that tries to think hits the suite's guard, not the network, so a test
    that forgets to fake Mind.think fails loudly instead of spending from the key."""
    m = Mind()
    m.key = "test-key"
    assert m.awake
    with pytest.raises(AssertionError, match="network"):
        m.think("system", "user")
