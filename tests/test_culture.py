"""The culture end to end, in a temporary vessel, with a mind that never calls out."""

from __future__ import annotations

import json
import time

import pytest

from bio import config, curve, plot
from bio.__main__ import main
from bio.culture import FALLBACK_GENESIS, Culture
from bio.membrane import inspect
from bio.mind import Mind

from .conftest import dish_state

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


def test_a_cell_whose_saved_memory_breaks_the_rule_is_lysed_on_the_first_tick(make_culture):
    """dish.json is a file too. A cell whose memory is over the cap when the dish is loaded (a
    hand edit, or a vessel saved before the rule) is not refused at load — `biotic status` reads
    the same file — but bursts on the first tick the culture runs, alone: every other cell lives
    on, nothing else dies, and the save on the way out no longer holds it."""
    c = make_culture()
    for _ in range(20):
        c.step()
    c.save()
    blob = json.loads(config.DISH_FILE.read_text())
    x, y = blob["cells"][0][0], blob["cells"][0][1]
    blob["cells"][0][6] = {"x": "y" * (config.MEMORY_MAX_CHARS + 52)}
    config.DISH_FILE.write_text(json.dumps(blob))
    again = Culture.load(Mind())
    n, deaths = len(again.dish.cells), dict(again.dish.deaths)
    assert again.dish.cells[(x, y)].memory == {"x": "y" * (config.MEMORY_MAX_CHARS + 52)}
    again.run(ticks=1, tick_seconds=0)
    again.mutagen.join(timeout=5)
    assert (x, y) not in again.dish.cells
    assert len(again.dish.cells) == n - 1 + (again.dish.births - c.dish.births)
    assert again.dish.deaths == {**deaths, "lysed": deaths["lysed"] + 1}
    assert _events("nonviable") == [], "the genome is fine; the cell's memory was not"
    saved = json.loads(config.DISH_FILE.read_text())
    assert saved["tick"] == 21 and all(not (row[0] == x and row[1] == y) for row in saved["cells"])


def _set_saved_at(t: float) -> None:
    blob = json.loads(config.DISH_FILE.read_text())
    blob["saved_at"] = t
    config.DISH_FILE.write_text(json.dumps(blob))


def test_a_resumed_dish_logs_the_gap_once_and_the_curve_marks_it(make_culture):
    """A dish taken up after longer than BIOTIC_INCUBATION_GAP away logs one `gap` event at the
    resume tick — not a faked tick — and `biotic curve` draws it as a marker there. Resuming again
    from a fresh save logs nothing: the gap is the absence, not the resume."""
    c = make_culture()
    for _ in range(40):
        c.step()
    resume_tick = c.dish.tick
    c.save()
    _set_saved_at(time.time() - 43440)  # 12h04m ago

    again = Culture.load(Mind())
    assert again.saved_at is not None and again._resume == {"gap": pytest.approx(43440, abs=5), "tick": resume_tick}
    again.run(ticks=20, tick_seconds=0)  # a curve row lands at ticks 50 and 60, both past the resume tick
    again.mutagen.join(timeout=5)

    gaps = _events("gap")
    assert len(gaps) == 1
    (gap,) = gaps
    assert gap["tick"] == resume_tick
    assert gap["msg"].startswith("incubation resumed after ")
    assert gap["branch"] == 0

    evs = curve.events()
    marks = plot.markers(evs)
    assert any(m.kind == "gap" and m.tick == resume_tick and m.branch == 0 for m in marks)
    fig = plot.figure(curve.read(), evs, ["population"])
    assert any(m.kind == "gap" for m in fig.markers)

    third = Culture.load(Mind())  # dish.json now carries a fresh saved_at from again.run()'s final save
    assert third._resume is None
    third.run(ticks=5, tick_seconds=0)
    third.mutagen.join(timeout=5)
    assert len(_events("gap")) == 1  # the gap is logged once, for the absence that happened


def test_a_brief_absence_and_a_never_run_dish_log_no_gap(make_culture):
    """No gap for a resume within the threshold, and none for a dish that has never run: a dish
    germinated but not incubated saves at tick 0, and the tick>0 guard keeps it from a phantom gap."""
    c = make_culture()
    for _ in range(20):
        c.step()
    c.save()  # a fresh saved_at, so the absence is seconds, well under the threshold
    brief = Culture.load(Mind())
    assert brief._resume is None
    brief.run(ticks=5, tick_seconds=0)
    brief.mutagen.join(timeout=5)
    assert _events("gap") == []

    fresh = make_culture()
    fresh.save()  # tick 0: germinated, never incubated
    _set_saved_at(time.time() - 43440)
    never = Culture.load(Mind())
    assert never._resume is None  # the dish.tick > 0 guard
    never.run(ticks=1, tick_seconds=0)
    never.mutagen.join(timeout=5)
    assert _events("gap") == []


def test_status_shows_last_active(make_culture, capsys):
    """`biotic status` reports when the dish was last written, and says nothing about it for a
    dish.json from before the field existed."""
    c = make_culture()
    for _ in range(10):
        c.step()
    c.save()
    _set_saved_at(time.time() - 43440)
    main(["status"])
    out = capsys.readouterr().out
    assert "last active" in out and "ago" in out

    blob = json.loads(config.DISH_FILE.read_text())
    del blob["saved_at"]
    config.DISH_FILE.write_text(json.dumps(blob))
    main(["status"])
    assert "last active" not in capsys.readouterr().out


def test_network_guard_is_armed():
    """An awake mind that tries to think hits the suite's guard, not the network, so a test
    that forgets to fake Mind.think fails loudly instead of spending from the key."""
    m = Mind()
    m.key = "test-key"
    assert m.awake
    with pytest.raises(AssertionError, match="network"):
        m.think("system", "user")
