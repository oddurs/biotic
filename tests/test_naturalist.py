"""The naturalist: notes are looked for on the cadence and never sooner than the wall-clock floor;
each is composed against the previous one, so the record continues; a sweep is a computed remark
in the next prompt; a revive puts a seam in the notebook; the baseline survives a save and a hard
kill; the dish never waits on the thread and walks the same path with or without notes; nothing
the culture is told leaks into the observer's prompt; `biotic notes` prints the notebook and the
eyepiece's footer shows the latest entry.

Every call goes to a FakeMind on the main thread, except the one test of the thread itself, which
runs no mutagen and no membrane."""

from __future__ import annotations

import io
import json
import threading
import time

import pytest
from rich.cells import cell_len
from rich.console import Console
from rich.screen import Screen

import bio.culture
from bio import config, naturalist, prompts
from bio.__main__ import main
from bio.culture import FALLBACK_GENESIS, Culture
from bio.dish import Dish
from bio.mind import Mind, backoff
from bio.mutagen import Mutagen
from bio.naturalist import (
    CENSUS_ROWS,
    LOG_LINES,
    NOTE_EVENTS,
    Naturalist,
    append_note,
    clean_reply,
    compose,
    first_sentence,
    read_notes,
    remarks,
    sketch,
)
from bio.strains import Registry
from bio.tui import build, events, footer

from .conftest import WANDERER, Clock, FakeMind, http_error, state

FIRST = "Five cells of founder sit in the middle of rich agar; nothing has divided yet. The dish is quiet."
SECOND = "Founder has spread north and holds the whole census. One reading is that the agar there was richer."
THIRD = "The population has levelled off. Nothing else changed."

# what the culture is told and the observer must never be: the cell API, the membrane, the reply forms
LEAKS = (
    "def live",
    "me.energy",
    "me.memory",
    "membrane",
    "NAME:",
    "NOTE:",
    "daughter",
    "mutation is",
    "Write the daughter",
    "Write the founding cell",
)


class Recorder(FakeMind):
    """A FakeMind that keeps every prompt it was sent."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.prompts: list[str] = []

    def _request(self, path, body=None, timeout=120):
        if path == "/chat/completions":
            self.prompts.append(body["messages"][1]["content"])
        return super()._request(path, body, timeout)


def logged(kind: str | None = None) -> list[dict]:
    if not config.EVENTS.exists():
        return []
    evs = [json.loads(ln) for ln in config.EVENTS.read_text().splitlines()]
    return [e for e in evs if kind is None or e["kind"] == kind]


def step(c: Culture, n: int) -> None:
    for _ in range(n):
        c.step()


def look(c: Culture) -> bool:
    """One look, on the main thread: the packet the culture would hand over, written now."""
    return c.naturalist._write(c._packet(c.dish.census(), c.last_phase or c.dish.phase()))


def inline(c: Culture) -> None:
    """Write notes on the main thread as soon as the culture hands a packet over: what the thread
    would do, without the thread."""
    n = c.naturalist
    hand = n.observe

    def observe(packet):
        hand(packet)
        with n.lock:
            taken, n.pending = n.pending, None
        n._write(taken)

    n.observe = observe


def packet(tick: int, t: float, census: dict[str, int], tiles: int = 100, **metrics) -> dict:
    """A synthetic packet, as Culture._packet builds one, for a census given by hand."""
    total = sum(census.values())
    rows = [
        {"id": sid, "name": f"strain_{sid}", "note": "", "generation": 1, "cells": n, "share": n / total}
        for sid, n in sorted(census.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    m = {
        "tick": tick,
        "population": total,
        "strains": len(census),
        "nutrient": 0.4,
        "pheromone": 0.0,
        "shannon": 0.5,
        "dominance": max(census.values()) / total,
        "births": 0,
        "starved": 0,
        "lysed": 0,
        "senescent": 0,
        "killed": 0,
        "mean_gen": 1.0,
        "arisen": len(census),
        "extinct": 0,
        "phase": "log",
    }
    m.update(metrics)
    return {
        "seed": "t",
        "tick": tick,
        "t": t,
        "branch": 0,
        "phase": "log",
        "tiles": tiles,
        "tick_seconds": 0.5,
        "metrics": m,
        "census": rows,
        "events": [],
        "sketch": {"scale": 1, "rows": ["a"], "legend": [("a", rows[0]["name"])]},
    }


def paint(renderable, w: int, h: int) -> str:
    con = Console(width=w, height=h, file=io.StringIO(), force_terminal=True, color_system="truecolor", record=True)
    con.print(Screen(renderable))
    return con.export_text()


# --- criterion 1: the cadence, the floor, and the record that continues -----------------------------


def test_looks_come_on_the_cadence_with_an_awake_mind_and_never_without(make_culture, monkeypatch):
    """Every NOTES_EVERY ticks the culture hands the naturalist a packet, and at no other tick;
    a dormant mind and BIOTIC_NOTES_EVERY=0 mean no packet at all, and the step is otherwise
    what it was."""
    monkeypatch.setattr(config, "NOTES_EVERY", 10)
    c = make_culture(mind=FakeMind(replies=[FIRST]))
    clock = Clock()
    c.naturalist.clock = clock
    seen: list[int] = []
    hand = c.naturalist.observe

    def observe(p):
        seen.append(p["tick"])
        hand(p)

    c.naturalist.observe = observe
    for _ in range(35):
        clock.now += 200  # well past the floor every tick
        c.step()
    assert seen == [10, 20, 30]
    assert c.naturalist.pending["tick"] == 30 and c.naturalist.dropped == 2, "one slot: each look replaced the last"

    dormant = make_culture(mind=Mind())
    assert not dormant.mind.awake
    step(dormant, 35)
    assert dormant.naturalist.pending is None and dormant.naturalist.dropped == 0

    monkeypatch.setattr(config, "NOTES_EVERY", 0)
    off = make_culture(mind=FakeMind(replies=[FIRST]))
    step(off, 35)
    assert off.naturalist.pending is None


def test_the_wall_clock_floor_refuses_a_look_sooner_than_two_minutes_after_the_last(make_culture, monkeypatch):
    """At --tick 0 the cadence alone would be one call per reply. The floor is on the look, not
    the note: a tick on the cadence inside the floor is skipped, and the next one on the cadence
    after it is taken."""
    monkeypatch.setattr(config, "NOTES_EVERY", 10)
    c = make_culture(mind=FakeMind(replies=[FIRST]))
    clock = Clock(1000.0)
    c.naturalist.clock = clock
    assert config.NOTES_MIN_SECONDS == 120.0
    step(c, 30)  # the clock never moves: 10 is a look, 20 and 30 are inside the floor
    assert c.naturalist.pending["tick"] == 10 and c.naturalist.dropped == 0
    clock.now += 119.9
    step(c, 10)
    assert c.naturalist.pending["tick"] == 10, "119.9 s is inside the floor"
    clock.now += 0.1
    step(c, 10)
    assert c.naturalist.pending["tick"] == 50 and c.naturalist.dropped == 1


def test_each_note_is_composed_against_the_one_before_it(make_culture):
    """The second prompt carries the first entry's text and tick and every delta since it; the
    notebook holds both in order; the baseline, `latest()` and the `note` event are the second."""
    mind = Recorder(replies=[FIRST, SECOND])
    c = make_culture(mind=mind)
    step(c, 30)
    assert look(c)
    t30 = c.naturalist.last["t"]
    step(c, 30)
    assert look(c)
    first, second = mind.prompts
    assert "This is the first entry; there is nothing earlier to compare with." in first
    assert "Your previous entry" not in first and "(was " not in first
    assert "Since the last entry (tick 30, 30 ticks" in second
    assert f"Your previous entry (tick 30):\n  {FIRST}" in second
    assert "population 20 → 103" in second and "births 83" in second  # what the founder did in thirty ticks
    assert "(was 100%)" in second
    assert "Write the next entry." in second and second.index("Your previous entry") < second.index(
        "Write the next entry"
    )

    notes = read_notes(config.FIELDNOTES)
    assert [(n.tick, n.text) for n in notes] == [(30, FIRST), (60, SECOND)]
    assert config.FIELDNOTES.read_text().startswith("# field notes — “test”\n\n## tick 30 · ")
    assert c.naturalist.latest() == {"tick": 60, "t": c.naturalist.last["t"], "text": SECOND}
    base = c.naturalist.baseline()
    assert base["tick"] == 60 and base["text"] == SECOND and base["seam"] is False and base["branch"] == 0
    assert base["metrics"]["population"] == 103 and base["census"] == c.dish.census()
    assert base["t"] > t30 and c.naturalist.written == 2

    a, b = logged("note")
    assert (a["tick"], a["text"]) == (30, FIRST) and (b["tick"], b["text"]) == (60, SECOND)
    assert a["msg"] == first_sentence(FIRST) and b["at"] == base["t"]
    assert b["metrics"] == base["metrics"] and b["census"] == base["census"] and b["branch"] == 0
    calls = logged("call")
    assert [ev["role"] for ev in calls] == ["naturalist", "naturalist"]
    assert c.mind.calls == 2 and c.mind.spent_usd == pytest.approx(0.02), "notes count against the dish budget"


def test_a_failed_call_backs_off_and_honours_retry_after(make_culture):
    """A MindError schedules the next attempt as the mutagen does — 15 s doubling, a Retry-After
    stretching it up to the cap — and due() is false until then; a success resets the schedule."""
    mind = FakeMind(replies=[http_error(503, retry_after="60"), http_error(503), FIRST])
    c = make_culture(mind=mind)
    clock = Clock(1000.0)
    n = c.naturalist
    n.clock = clock
    step(c, 10)
    assert not look(c)
    assert (n.failures, n.retry_at) == (1, 1060.0), "Retry-After 60 s beats the 15 s first backoff"
    (ev,) = [e for e in logged("mind") if e["msg"].startswith("field note at tick 10 not written")]
    assert ev["msg"].endswith('HTTP 503: {"error":"x"} — no note before 1m00s')
    assert (ev["status"], ev["retry_in"], ev["failures"]) == (503, 60.0, 1)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(config, "NOTES_EVERY", 10)
        assert not n.due(10)
        clock.now = 1059.9
        assert not n.due(10)
        clock.now = 1060.0
        assert n.due(10)
    assert not look(c)
    assert n.failures == 2 and n.retry_at == pytest.approx(1060.0 + backoff(2)) and backoff(2) == 30.0
    clock.now = 2000.0
    assert look(c)
    assert (n.failures, n.retry_at, n.written) == (0, 0.0, 1)
    assert n.mind.chat_requests == 3


def test_a_spent_budget_ends_the_notes_once_and_makes_no_request(make_culture, monkeypatch):
    monkeypatch.setattr(config, "NOTES_EVERY", 10)
    c = make_culture(mind=FakeMind(replies=[FIRST], budget_usd=0.0))
    step(c, 10)
    assert c.naturalist.pending["tick"] == 10, "the look is handed over; the budget is checked at the call"
    with c.naturalist.lock:
        c.naturalist.pending = None
    assert not look(c)
    assert not look(c)
    ended = [e for e in logged("mind") if e["msg"].startswith("field notes end")]
    assert len(ended) == 1
    assert ended[0]["msg"] == "field notes end at tick 10 — budget spent ($0.000 / $0.00)"
    assert c.naturalist.silenced and not c.naturalist.due(10)
    assert c.mind.chat_requests == 0 and not config.FIELDNOTES.exists()
    step(c, 30)
    assert c.naturalist.pending is None, "silenced: no look is handed over again in this process"


def test_an_empty_reply_writes_nothing_and_does_not_back_off(make_culture):
    c = make_culture(mind=FakeMind(replies=["```\n\n```", FIRST]))
    step(c, 10)
    assert not look(c)
    assert not config.FIELDNOTES.exists() and c.naturalist.baseline() == {}
    assert [e["msg"] for e in logged("mind") if "empty" in e["msg"]] == [
        "field note at tick 10 was empty — nothing written"
    ]
    assert (c.naturalist.failures, c.naturalist.retry_at) == (0, 0.0)
    assert look(c) and read_notes(config.FIELDNOTES)[0].text == FIRST


def test_a_notebook_that_cannot_be_written_is_said_and_the_baseline_stands(make_culture, monkeypatch, tmp_path):
    c = make_culture(mind=FakeMind(replies=[FIRST, SECOND]))
    step(c, 10)
    assert look(c)
    monkeypatch.setattr(config, "FIELDNOTES", tmp_path / "nowhere" / "x" / "fieldnotes.md")
    (tmp_path / "nowhere").write_text("a file where the directory should be")
    step(c, 10)
    assert not look(c)
    assert c.naturalist.baseline()["tick"] == 10, "the last note written is still the baseline"
    assert [e["tick"] for e in logged("note")] == [10]
    (ev,) = [e for e in logged("mind") if e["msg"].startswith("field note at tick 20 not written")]
    assert "fieldnotes.md" in ev["msg"] or "nowhere" in ev["msg"]


# --- criterion 2: a sweep is remarked on --------------------------------------------------------


def test_a_sweep_is_a_computed_remark_in_the_next_prompt(make_culture):
    """A strain under 10 % at the last entry (absent counts as nothing) and over 70 % now is put
    under "Changes worth noting" by the apparatus, not left to the model; the boundaries hold."""
    assert remarks(
        {"a": 95, "b": 5}, [{"id": "b", "name": "b", "share": 0.80}, {"id": "a", "name": "a", "share": 0.20}]
    ) == ["b went from 5% to 80% of the population"]
    assert remarks({"a": 100}, [{"id": "c", "name": "c", "share": 0.75}, {"id": "a", "name": "a", "share": 0.25}]) == [
        "c was not in the census at the last entry and is 75% of it now"
    ]
    assert remarks({"a": 91, "b": 9}, [{"id": "b", "name": "b", "share": 0.69}]) == [], "69 % is not a sweep"
    assert remarks({"a": 90, "b": 10}, [{"id": "b", "name": "b", "share": 0.90}]) == [], "10 % before is not under it"
    assert remarks(None, [{"id": "b", "name": "b", "share": 0.99}]) == [], "the first entry compares nothing"
    assert remarks({}, [{"id": "b", "name": "b", "share": 0.99}]) == [
        "b was not in the census at the last entry and is 99% of it now"
    ]

    mind = Recorder(replies=[FIRST, SECOND])
    c = make_culture(mind=mind)
    n = c.naturalist
    assert n._write(packet(600, 1000.0, {"aa00": 95, "bb00": 5}))
    assert n._write(packet(1200, 1400.0, {"aa00": 20, "bb00": 80}))
    second = mind.prompts[1]
    assert "Changes worth noting:\n  - strain_bb00 went from 5% to 80% of the population" in second
    assert "strain_bb00 (bb00) gen 1 · 80 cells · 80% (was 5%)" in second
    assert "strain_aa00 (aa00) gen 1 · 20 cells · 20% (was 95%)" in second
    assert "Changes worth noting" not in mind.prompts[0]
    assert read_notes(config.FIELDNOTES)[-1].text == SECOND
    # a third look with the same census: nothing swept since the last entry
    assert n._write(packet(1800, 1800.0, {"aa00": 20, "bb00": 80}))
    assert "Changes worth noting" not in mind.prompts[2]


# --- the seam: a revive compares nothing across it ---------------------------------------------


def test_a_revive_puts_a_seam_in_the_notebook_and_keeps_the_vessels_baseline(make_culture):
    """The next entry after a revive says the dish was replaced and compares no counts with the
    entry before; writing it clears the seam. The baseline is the vessel's, not the sample's: a
    dish frozen with note A, revived after note B, continues from B."""
    mind = Recorder(replies=[FIRST, SECOND, THIRD, "After the seam, deltas again."])
    c = make_culture(mind=mind)
    step(c, 30)
    assert look(c)
    sample = c.freeze("t")
    assert bio.culture.freezer.read(sample)["culture"]["naturalist"]["tick"] == 30, (
        "a sample carries the baseline it had"
    )
    step(c, 30)
    assert look(c)
    c.naturalist.observe(c._packet(c.dish.census(), "log"))  # a look not yet written when the dish is replaced
    c.revive(sample)
    n = c.naturalist
    assert c.dish.tick == 30
    assert n.pending is None, "the pending packet described the old dish"
    base = n.baseline()
    assert (base["tick"], base["text"], base["seam"]) == (60, SECOND, True)
    assert json.loads(config.DISH_FILE.read_text())["culture"]["naturalist"]["seam"] is True, "the revive saved it"

    step(c, 30)
    assert look(c)
    third = mind.prompts[2]
    assert (
        "Since the last entry (tick 60) the dish was replaced with a frozen sample; "
        "the counts above are not comparable with that entry's." in third
    )
    assert "(was " not in third and "population 103 →" not in third and "Changes worth noting" not in third
    assert f"Your previous entry (tick 60):\n  {SECOND}" in third, "the record still continues"
    assert "revived from tick 30" in third, "the revive is in the log the prompt shows"
    assert n.baseline()["seam"] is False and n.baseline()["tick"] == 60 and n.baseline()["branch"] == 1
    step(c, 30)
    assert look(c)
    assert "Since the last entry (tick 60, 30 ticks" in mind.prompts[3] and "(was " in mind.prompts[3]
    assert [nt.tick for nt in read_notes(config.FIELDNOTES)] == [30, 60, 60, 90]


def test_compose_across_a_seam_shows_events_since_the_entry_but_no_deltas():
    prev = {
        "tick": 600,
        "t": 1000.0,
        "text": FIRST,
        "branch": 0,
        "seam": True,
        "metrics": {"population": 5},
        "census": {"a": 5},
    }
    p = packet(300, 1200.0, {"a": 10, "b": 90})
    p["events"] = [
        {"t": 900.0, "tick": 590, "kind": "arose", "msg": "before"},
        {"t": 1100.0, "tick": 600, "kind": "revived", "msg": "revived from tick 300"},
    ]
    out = compose(p, prev)
    assert out["since"] == {"seam": True, "prev_tick": 600}
    assert out["remarks"] == [] and all("was" not in r for r in out["census"])
    assert [e["msg"] for e in out["events"]] == ["revived from tick 300"]
    assert out["previous"] == {"tick": 600, "text": FIRST}
    user = prompts.naturalist_user(out)
    assert "replaced with a frozen sample" in user and "(was" not in user and "new since" not in user


# --- persistence: a save, a hard kill, an older vessel -------------------------------------------


def test_the_baseline_round_trips_through_dish_json_and_catches_up_from_the_log(make_culture):
    c = make_culture(mind=FakeMind(replies=[FIRST]))
    step(c, 10)
    assert look(c)
    c.save()
    again = Culture.load(Mind())
    assert again.naturalist.baseline() == c.naturalist.baseline()
    assert again.naturalist.latest()["text"] == FIRST

    # killed between saves: a later note is in the log and the notebook, not in dish.json
    at = c.naturalist.last["t"] + 50
    c.log("note", "later", tick=20, at=at, text=SECOND, branch=0, metrics={"population": 7}, census={"x": 7})
    back = Culture.load(Mind())
    b = back.naturalist.baseline()
    assert (b["tick"], b["t"], b["text"], b["seam"]) == (20, at, SECOND, False)
    assert b["metrics"] == {"population": 7} and b["census"] == {"x": 7}
    assert c.naturalist.baseline()["tick"] == 10, "reading the log wrote nothing back"

    # an older event does not move the baseline backwards
    c.save()
    c.log("note", "older", tick=5, at=1.0, text="old", branch=0, metrics={}, census={})
    assert Culture.load(Mind()).naturalist.baseline()["tick"] == 10

    # a vessel from before the naturalist: no key, and nothing to say
    blob = json.loads(config.DISH_FILE.read_text())
    del blob["culture"]["naturalist"]
    config.DISH_FILE.write_text(json.dumps(blob))
    config.EVENTS.write_text("")
    old = Culture.load(Mind())
    assert old.naturalist.baseline() == {} and old.naturalist.latest() is None
    assert "Since the last entry" not in prompts.naturalist_user(compose(old._packet(old.dish.census(), "lag"), None))


def test_a_baseline_with_bad_or_missing_fields_is_no_baseline():
    n = Naturalist(FakeMind(), "t", lambda *a, **k: None)
    for junk in (None, {}, [], {"tick": 1}, {"text": "x"}, {"tick": "many", "text": "x"}):
        n.restore(junk)
        assert n.baseline() == {} and n.latest() is None
    n.restore({"tick": 3, "text": "x", "metrics": "not a dict", "census": None})
    assert n.baseline() == {"tick": 3, "t": 0.0, "text": "x", "branch": 0, "seam": False, "metrics": {}, "census": {}}


# --- the dish is not changed by being observed ---------------------------------------------------


def test_notes_do_not_change_the_trajectory(make_culture, monkeypatch):
    """Twins, one writing a note every ten ticks on the main thread and one writing none, are the
    same culture after sixty ticks, state for state. Building a packet reads the dish and draws
    nothing from it."""
    monkeypatch.setattr(config, "NOTES_MIN_SECONDS", 0.0)
    quiet = make_culture(genome=WANDERER, mind=FakeMind(replies=[FIRST]))
    step(quiet, 60)
    monkeypatch.setattr(config, "NOTES_EVERY", 10)
    noted = make_culture(genome=WANDERER, mind=FakeMind(replies=[FIRST, SECOND, THIRD]))
    inline(noted)
    step(noted, 60)
    assert noted.naturalist.written == 6 and [n.tick for n in read_notes(config.FIELDNOTES)] == [10, 20, 30, 40, 50, 60]
    assert state(noted) == state(quiet)
    assert len(noted.dish.cells) > 5


def test_the_sketch_and_the_census_are_functions_of_the_state(monkeypatch):
    """Two cultures in the same state sketch the same picture; a block with a tie shows the smaller
    strain id, and the census ranks ties by id, so the packet is deterministic under a seed."""
    monkeypatch.setattr(naturalist, "SKETCH_W", 4)  # an 8-wide dish at 2×2 tiles per glyph
    d, reg = Dish("t", 8, 4), Registry("t")
    a = reg.new(FALLBACK_GENESIS, None, 0, "a", "")
    b = reg.new(FALLBACK_GENESIS + "\n", None, 0, "b", "")
    lo, hi = sorted((a.id, b.id))
    for x, y in ((2, 0), (3, 0)):
        assert d.place(x, y, a.id, 1.0)
    for x, y in ((2, 1), (3, 1)):
        assert d.place(x, y, b.id, 1.0)
    names = {a.id: "a", b.id: "b"}
    sk = sketch(d, d.census(), names)
    assert sk["scale"] == 2 and len(sk["rows"]) == 2
    assert sk["legend"] == [("a", names[lo]), ("b", names[hi])], "equal counts: the smaller id ranks first"
    assert sk["rows"][0][1] == "a", "the tied block shows the smaller id, which ranks first"
    twin = Dish.from_dict(json.loads(json.dumps(d.to_dict())))
    assert sketch(twin, twin.census(), names) == sk
    # glyphs for agar by richness, blank for glass (one glyph per tile: the corner block above had a tile inside)
    monkeypatch.setattr(naturalist, "SKETCH_W", 48)
    bare = Dish("t", 8, 4)
    sk = sketch(bare, {}, {})
    rows = sk["rows"]
    assert sk["scale"] == 1 and sk["legend"] == []
    assert all(set(r) <= set(" .:#") for r in rows) and any("#" in r or ":" in r for r in rows)
    assert not bare.mask[0][0] and rows[0][0] == " "


def test_the_packet_carries_the_dish_and_not_the_apparatus(make_culture):
    """Names, ids, generations, counts, shares and the mutagen's note per strain; the dish's own
    events, not the bookkeeping; no genome anywhere in it."""
    c = make_culture(mind=FakeMind())
    step(c, 10)
    c.log("call", "a call", usd=0.0)
    c.log("mind", "the mind said something")
    c.log("curve", "widened")
    c.log("whisper", "more food at the edges")
    c.log("arose", "x arose from founder")
    p = c._packet(c.dish.census(), "lag")
    assert set(p) == {
        "seed",
        "tick",
        "t",
        "branch",
        "phase",
        "tiles",
        "tick_seconds",
        "metrics",
        "census",
        "events",
        "sketch",
    }
    assert set(p["census"][0]) == {"id", "name", "note", "generation", "cells", "share"}
    assert {e["kind"] for e in p["events"]} == {"genesis", "whisper", "arose"} or {e["kind"] for e in p["events"]} == {
        "whisper",
        "arose",
    }
    assert all(e["kind"] in NOTE_EVENTS for e in p["events"])
    assert "def live" not in json.dumps(p)
    assert p["tiles"] == c.dish.tiles and p["metrics"]["population"] == len(c.dish.cells)
    (row,) = p["census"]
    assert row["cells"] == len(c.dish.cells) and row["share"] == 1.0 and row["name"] == "founder"


# --- the thread: the dish never waits ------------------------------------------------------------


def test_the_dish_never_waits_on_the_naturalist(make_culture):
    """observe() returns at once while a call is in flight; a second packet handed over meanwhile
    replaces the one in the slot rather than queueing behind it; the thread writes what it has and
    stops when closed. No mutagen, no membrane."""
    mind = FakeMind(replies=["One.", "Two."])
    entered, gate = threading.Event(), threading.Event()
    real = mind._request

    def slow(path, body=None, timeout=120):
        if path == "/chat/completions":
            entered.set()
            assert gate.wait(5), "the test never opened the gate"
        return real(path, body, timeout)

    mind._request = slow
    c = make_culture(mind=mind)  # only to build packets; nothing here is started
    step(c, 10)
    n = Naturalist(mind, "t", c.log)
    n.start()
    try:
        t0 = time.monotonic()
        n.observe(c._packet(c.dish.census(), "lag"))
        assert time.monotonic() - t0 < 0.5
        assert entered.wait(5), "the thread took the packet and is in the call"
        step(c, 10)
        n.observe(c._packet(c.dish.census(), "lag"))  # into the slot, behind the call in flight
        step(c, 10)
        t0 = time.monotonic()
        n.observe(c._packet(c.dish.census(), "lag"))  # replaces it
        assert time.monotonic() - t0 < 0.5
        assert n.dropped == 1
        gate.set()
        deadline = time.monotonic() + 5
        while n.written < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert n.written == 2
    finally:
        n.close()
        n.join(2)
    assert not n.is_alive()
    assert [nt.tick for nt in read_notes(config.FIELDNOTES)] == [10, 30], "the tick-20 look was replaced, never written"
    assert [e["tick"] for e in logged("note")] == [10, 30]


def test_run_starts_the_naturalist_only_with_an_awake_mind_and_closes_it(make_culture, monkeypatch):
    monkeypatch.setattr(config, "NOTES_EVERY", 10)
    monkeypatch.setattr(config, "NOTES_MIN_SECONDS", 0.0)
    monkeypatch.setattr(Mutagen, "run", lambda self: None)  # an awake mind would otherwise start it varying
    c = make_culture(mind=FakeMind(replies=[FIRST]))
    c.save()
    c.run(ticks=30, tick_seconds=0.02)
    c.naturalist.join(2)
    assert c.naturalist.ident is not None and not c.naturalist.is_alive()
    assert c.naturalist.written >= 1 and read_notes(config.FIELDNOTES)[0].tick == 10
    assert c.tick_seconds == 0.02

    dormant = make_culture(mind=Mind())
    dormant.save()
    dormant.run(ticks=20, tick_seconds=0)
    assert dormant.naturalist.ident is None, "never started"
    monkeypatch.setattr(config, "NOTES_EVERY", 0)
    off = make_culture(mind=FakeMind(replies=[FIRST]))
    off.save()
    off.run(ticks=20, tick_seconds=0)
    assert off.naturalist.ident is None


# --- criterion 4: the prompt is in bio/prompts.py and nothing the culture is told leaks into it ---


def test_nothing_the_culture_is_told_leaks_into_the_naturalists_prompt(make_culture):
    for leak in LEAKS:
        assert leak not in prompts.NATURALIST_SYSTEM, leak
    for leak in ("def live", "membrane", "NAME:", "daughter"):  # and the mutagen's prompt does say these
        assert leak in prompts.MUTAGEN_SYSTEM
    c = make_culture(mind=FakeMind(replies=[FIRST]))
    step(c, 30)
    p = c._packet(c.dish.census(), "lag")
    first = prompts.naturalist_user(compose(p, None))
    assert look(c)
    step(c, 30)
    later = prompts.naturalist_user(compose(c._packet(c.dish.census(), "log"), c.naturalist.baseline()))
    for user in (first, later):
        for leak in LEAKS:
            assert leak not in user, leak
    for src in c.dish.genomes.values():
        assert src.strip() and src not in first and src not in later
    assert "founder" in later and "eats where it stands" not in later, (
        "the note is the strain's, and this founder has none"
    )


def test_the_prompt_reads_as_the_instruments_would(make_culture):
    """The prompt's fixed lines, in order, with the census capped at CENSUS_ROWS and the log at
    LOG_LINES; a pheromone reading appears only when there is one."""
    census = {f"{i:04x}": 200 - i for i in range(CENSUS_ROWS + 3)}
    p = packet(1200, 2000.0, census, tiles=1000, pheromone=0.0)
    p["events"] = [
        {"t": 1500.0 + i, "tick": 700 + i, "kind": "arose", "msg": f"event {i}"} for i in range(LOG_LINES + 5)
    ]
    prev = {
        "tick": 600,
        "t": 1499.5,
        "text": FIRST,
        "branch": 0,
        "seam": False,
        "metrics": {
            "population": 10,
            "strains": 1,
            "shannon": 0.0,
            "dominance": 1.0,
            "births": 5,
            "starved": 1,
            "lysed": 0,
            "senescent": 0,
            "killed": 0,
            "arisen": 1,
            "extinct": 0,
        },
        "census": {"0000": 10},
    }
    user = prompts.naturalist_user(compose(p, prev))
    lines = user.splitlines()
    assert lines[0] == "The dish was seeded with: t"
    assert (
        lines[2].startswith("tick 1200 · phase log · ")
        and "of the agar" in lines[2]
        and "15 living strains" in lines[2]
    )
    assert lines[3].startswith("diversity H 0.50 · dominance ") and "pheromone" not in lines[3]
    assert (
        "Since the last entry (tick 600, 600 ticks, about 5m00s at the incubator's pace; 8m20s of wall-clock time):"
        in user
    )
    assert "strains 1 → 15" in user and "births 0 · deaths 0 starved, 0 lysed, 0 of age" in user
    assert "Changes worth noting" not in user, "the top strain was 100 % before"
    assert user.count(" cells · ") + user.count(" cell · ") == CENSUS_ROWS
    assert "… 3 more strains, " in user and "cells between them" in user
    assert "(was 100%)" in user and user.count("(new since the last entry)") == CENSUS_ROWS - 1
    assert user.count("\n  tick ") == LOG_LINES and "event 4" not in user and "event 24" in user, "the last LOG_LINES"
    assert "one glyph per tile" in user and "  a strain_0000" in user
    assert user.rstrip().endswith("Your previous entry (tick 600):\n  " + FIRST + "\n\nWrite the next entry.")
    scented = prompts.naturalist_user(compose(packet(10, 1.0, {"a": 1}, pheromone=0.02, killed=3), None))
    assert "pheromone 0.020" in scented and "(nothing was logged)" in scented and "First entry" not in scented


# --- the notebook file, and the commands that read it -------------------------------------------


def test_the_notebook_has_one_title_and_tolerates_a_torn_tail(tmp_path):
    path = tmp_path / "notes.md"
    assert read_notes(path) == []
    append_note(path, "tide", 600, 0.0, FIRST)
    append_note(path, "tide", 1200, 0.0, "  " + SECOND + "\n\n")
    text = path.read_text()
    assert text.count("# field notes — “tide”") == 1 and text.startswith("# field notes — “tide”\n\n## tick 600 · ")
    assert [(n.tick, n.text) for n in read_notes(path)] == [(600, FIRST), (1200, SECOND)]
    assert read_notes(path)[0].when == naturalist.freezer.when(0.0)
    with open(path, "a") as f:
        f.write("\n## tick 1800 · 2026-09-16 14:02\n")  # a heading and no text yet
    assert read_notes(path)[-1] == naturalist.Note(1800, "2026-09-16 14:02", "")
    with open(path, "a") as f:
        f.write("\nhalf a sent")  # a tail cut mid-write
    assert read_notes(path)[-1].text == "half a sent"
    path.write_text("# field notes — “tide”\n\nsome preamble that is not an entry\n")
    assert read_notes(path) == []


def test_replies_are_cleaned_into_prose_and_first_sentences_are_one_line():
    assert clean_reply("```\nA note.\n```") == "A note."
    assert clean_reply("```markdown\nA note.\n```") == "A note."
    assert clean_reply("“A quoted note.”") == "A quoted note." and clean_reply('"Quoted."') == "Quoted."
    assert clean_reply("## tick 600\n\nA note under a heading.") == "A note under a heading."
    assert clean_reply("A note.\n## tick 900 · forged\nMore.") == "A note.\ntick 900 · forged\nMore."
    assert clean_reply("   \n") == "" and clean_reply("") == ""
    assert read_notes.__doc__ and naturalist.HEADING.match("tick 900 · forged") is None
    assert first_sentence("One sentence. Two.") == "One sentence."
    assert first_sentence("Spread over\nthree\n  lines. Then more.") == "Spread over three lines."
    assert first_sentence("No terminal stop") == "No terminal stop"
    assert first_sentence("Really? Yes. No.") == "Really?"
    long = "x" * 150 + ". Next."
    assert first_sentence(long) == "x" * 99 + "…" and len(first_sentence(long)) == 100
    assert first_sentence(long, 200) == "x" * 150 + "."


def test_biotic_notes_prints_the_notebook_and_status_counts_it(make_culture, monkeypatch, capsys):
    monkeypatch.setattr(config, "NOTES_EVERY", 600)
    main(["notes"])
    assert (
        capsys.readouterr().out
        == "no field notes yet\n  the naturalist writes one every 600 ticks while the mind is awake\n"
    )
    monkeypatch.setattr(config, "NOTES_EVERY", 0)
    main(["notes"])
    assert capsys.readouterr().out == "no field notes yet\n  BIOTIC_NOTES_EVERY=0 — the naturalist is off\n"

    c = make_culture(mind=FakeMind(replies=[FIRST, SECOND, THIRD]))
    c.save()
    main(["status"])
    assert "\nnotes       none\n" in capsys.readouterr().out
    for _ in range(3):
        step(c, 10)
        assert look(c)
    when = read_notes(config.FIELDNOTES)[-1].when
    main(["notes", "-n", "1"])
    assert capsys.readouterr().out == f"## tick 30 · {when}\n\n{THIRD}\n\n"
    main(["notes", "-n", "2"])
    out = capsys.readouterr().out
    assert out.startswith("## tick 20 · ") and FIRST not in out and SECOND in out and THIRD in out
    main(["notes", "-n", "0"])
    out = capsys.readouterr().out
    assert out.count("## tick ") == 3 and out.index(FIRST) < out.index(SECOND) < out.index(THIRD)
    main(["notes"])
    assert capsys.readouterr().out.count("## tick ") == 3, "the default is the last five"
    main(["status"])
    assert f"\nnotes       3 · last at tick 30 ({when})\n" in capsys.readouterr().out


# --- criterion 3: the eyepiece shows the latest line ----------------------------------------------


def test_the_footer_shows_the_latest_notes_first_sentence(make_culture):
    """With no note the footer is what it was, at every width. With one, its first sentence takes
    the commands' place; the ctrl-c hint yields first and the note is cut with an ellipsis."""
    for cols in range(14, 160):
        assert footer(cols).plain == footer(cols, None).plain
    assert footer(150).plain.endswith("ctrl-c to incubate (state is saved)")
    note = {"tick": 1800, "t": 0.0, "text": SECOND}
    wide = footer(150, note)
    assert wide.plain == f"  ¶ 1800  {first_sentence(SECOND, 200)}   ctrl-c to incubate (state is saved)"
    assert wide.plain.startswith("  ¶ 1800  Founder has spread north and holds the whole census.")
    narrow = footer(60, note)
    assert "ctrl-c" not in narrow.plain and narrow.plain.endswith("…") and cell_len(narrow.plain) == 60
    assert narrow.plain.startswith("  ¶ 1800  Founder has spread")
    for cols in range(14, 160):
        t = footer(cols, note)
        assert t.no_wrap and t.overflow == "ellipsis"
        assert cell_len(t.plain) <= cols
        assert t.plain.startswith("  ¶") if cols >= 3 else True
    lines = paint(footer(40, note), 40, 2).split("\n")
    assert lines[0].endswith("…") and len(lines[0]) == 40 and lines[1].strip() == ""

    c = make_culture(mind=FakeMind(replies=[FIRST]))
    step(c, 10)
    before = paint(build(c, (150, 50)), 150, 50).split("\n")
    assert before[-1].startswith('  biotic whisper "…"'), "no note yet: the commands"
    assert look(c)
    frame = paint(build(c, (150, 50)), 150, 50).split("\n")
    assert frame[-1].startswith(
        "  ¶ 10  Five cells of founder sit in the middle of rich agar; nothing has divided yet."
    )
    assert frame[-1].rstrip().endswith("ctrl-c to incubate (state is saved)")
    assert len(frame) == 50 and "vitals" in frame[1], "one footer row; the panels above are as they were"
    log = events(c, 5).plain
    assert "¶ " + first_sentence(FIRST) in log, "the note is in the incubator log too"
    assert c.snapshot()["note"]["tick"] == 10
    small = paint(build(c, (60, 20)), 60, 20).split("\n")
    assert small[-1].startswith("  ¶ 10  ") and small[-1].endswith("…")
