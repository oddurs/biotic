"""The mutagen's two clocks. On the tick clock the dish calls the mind itself, at most once every
MUTAGEN_EVERY_TICKS ticks, and waits: attempts, births and counts are a function of the seed and
the replies, not of --tick, latency or the machine. On the wall clock the dish never waits. Every
mind here is fake and deterministic; nothing reaches the network."""

from __future__ import annotations

import json
import math
import re
import statistics
import time

import pytest
from rich.console import Console

import bio.__main__ as cli
import bio.culture
import bio.mutagen
from bio import config, curve, freezer, tui
from bio.culture import Culture, incubating
from bio.membrane import Verdict

from .conftest import DAUGHTER, FakeMind, Variator, dish_state, http_error


def _founder(c: Culture) -> str:
    return next(iter(c.registry.strains))


def _logged() -> list[dict]:
    if not config.EVENTS.exists():
        return []
    return [json.loads(line) for line in config.EVENTS.read_text().splitlines()]


def _kinds(kind: str) -> list[dict]:
    return [ev for ev in _logged() if ev["kind"] == kind]


def _failures() -> list[dict]:
    return [ev for ev in _kinds("mind") if ev["msg"].startswith("mutagen call failed")]


def _render(renderable, width: int = 80) -> str:
    console = Console(record=True, width=width, force_terminal=False)
    console.print(renderable)
    return console.export_text()


def _dormant() -> FakeMind:
    m = FakeMind()
    m.key = None
    return m


def _step(c: Culture, n: int) -> None:
    for _ in range(n):
        c.step()


def _gaps(ticks: list[int]) -> list[int]:
    return [b - a for a, b in zip(ticks, ticks[1:])]


def _every_division_rolls(c: Culture) -> Culture:
    """On the 24×12 test dish there are some ten births per 200 ticks once the bloom is over, so at
    the default 6 % a roll is rarer than the interval. With every division rolling, the interval is
    the one limit on attempts, which is the property under test; the roll RNG is drawn once per
    division whatever the rate, so a dormant twin still walks the same path."""
    c.mutation_rate = 1.0
    return c


# --- criterion 1: attempts do not depend on tick speed ------------------------------


def test_attempts_do_not_depend_on_tick_speed(make_culture, ticked, no_subprocess):
    """Two runs from the same seed, one as fast as it goes and one at two milliseconds a tick,
    make their attempts at the same ticks and walk the same trajectory, cell for cell. At
    --tick 0 the old wall clock made one call per thousands of ticks; here the clock is the dish."""
    runs = {}
    for name, dt in (("fast", 0.0), ("slow", 0.002)):
        ticks: list[int] = []
        c = _every_division_rolls(make_culture(mind=Variator(on_call=lambda: ticks.append(c.dish.tick))))
        ticked(c, every=40)
        c.run(ticks=800, tick_seconds=dt)
        runs[name] = (c, ticks)
    fast, slow = runs["fast"], runs["slow"]
    assert len(fast[1]) >= 8, "non-vacuous: the fast run made attempts"
    assert fast[1] == slow[1], "the attempt ticks are the same at both speeds"
    for a, b in zip(fast[1], fast[1][1:]):
        assert b - a >= 40
    for key in ("attempted", "viable", "nonviable"):
        assert getattr(fast[0].mutagen, key) == getattr(slow[0].mutagen, key)
    assert fast[0].metrics()["arisen"] == slow[0].metrics()["arisen"] > 1
    assert dish_state(fast[0].dish) == dish_state(slow[0].dish), "the whole trajectory, not just the count"
    assert not fast[0].mutagen.is_alive() and not slow[0].mutagen.is_alive(), (
        "the thread exits at once on the tick clock"
    )


# --- criterion 2: the wall clock never waits on the mind ----------------------------


def test_wall_clock_never_waits_on_the_mind(make_culture, monkeypatch):
    """A mind that takes a second to answer does not slow a tick: the ticks run on while the call
    is in flight, the reply lands in the pool afterwards, and the dish stepped meanwhile is the
    dormant twin's. The membrane is stubbed because the thread cannot run its alarm."""
    monkeypatch.setattr(bio.mutagen, "admit_isolated", lambda src: Verdict(True))
    asked: list[int] = []
    mind = Variator(sleep=1.0, on_call=lambda: asked.append(c.dish.tick))  # on_call runs before the sleep
    c = _every_division_rolls(make_culture(mind=mind))
    assert c.use_clock(None, "live") == "wall"
    twin = _every_division_rolls(make_culture(mind=_dormant()))
    c.mutagen.start()
    try:
        times = []
        for _ in range(200):
            t0 = time.perf_counter()
            c.step()
            times.append(time.perf_counter() - t0)
            twin.step()
        assert len(asked) == 1 and asked[0] < 100, "a division rolled a mutation and the thread asked the mind"
        assert mind.calls == 0 and c.mutagen.state == "thinking", "the reply had not arrived: the call was in flight"
        assert max(times) < 0.5 and statistics.median(times) < 0.02, "no tick waited on the sleeping mind"
        assert dish_state(c.dish) == dish_state(twin.dish), "no daughter was taken during the sleep"
    finally:
        c.mutagen.close()
        c.mutagen.join(3)
    assert not c.mutagen.is_alive()
    assert mind.calls == 1 and c.mutagen.ready() == 1, "the reply landed in the pool, off the dish's path"
    assert c.mutagen.viable == 1 and c.mutagen.attempted == 1


# --- criterion 3: at most one call per interval, and each is born at once -----------


def test_tick_clock_makes_at_most_one_call_per_interval(make_culture, ticked, no_subprocess):
    ticks: list[int] = []
    c = _every_division_rolls(make_culture(mind=Variator(on_call=lambda: ticks.append(c.dish.tick))))
    ticked(c, every=40)
    c.run(ticks=2000, tick_seconds=0)
    m, mind = c.mutagen, c.mind
    assert 10 <= m.attempted <= 50, m.attempted
    assert ticks and min(_gaps(ticks)) >= 40, "never two calls fewer than 40 ticks apart"
    assert mind.calls == m.attempted == mind.chat_requests == len(ticks)
    assert m.nonviable == 0 and m.viable == m.attempted
    mt = c.metrics()
    assert mt["mutations_taken"] == m.viable == mt["arisen"] - 1, (
        "each viable daughter is born in the division that asked"
    )
    assert mt["mutations_attempted"] == m.attempted and mt["mutations_viable"] == m.viable
    assert m.ready() == m.pending() == 0, "no pool, no queue"
    assert _kinds("prepared") == [], "nothing is prepared ahead of a division"
    assert len(_kinds("arose")) == m.viable
    last = curve.read()[-1]
    assert last["tick"] == 2000
    assert last["mutations_attempted"] == m.attempted and last["mutations_viable"] == m.viable
    start = [ev for ev in _kinds("mind") if ev["msg"].startswith("mutagen clock")]
    assert len(start) == 1
    assert start[0]["msg"] == "mutagen clock: tick, every 40 ticks"
    assert (start[0]["clock"], start[0]["every_ticks"]) == ("tick", 40)
    assert c.snapshot()["mutagen"]["clock"] == "tick" and c.snapshot()["mutagen"]["every_ticks"] == 40


def test_boost_divides_the_tick_interval_and_expires(make_culture, ticked, no_subprocess):
    """`drop mutagen` shortens the interval six-fold for 300 ticks on the tick clock as it does the
    wall interval; when it wears off the interval, the rate and dish.json all go back to 1."""
    ticks: list[int] = []
    c = _every_division_rolls(make_culture(mind=Variator(on_call=lambda: ticks.append(c.dish.tick))))
    ticked(c, every=40)
    c.drop("mutagen")
    assert (c.mutagen.boost, c.mutagen.boost_until) == (6.0, 300)
    assert c.mutagen.interval() == pytest.approx(40 / 6)
    c.run(ticks=800, tick_seconds=0)
    boosted = [t for t in ticks if t < 300]
    assert len(boosted) >= 3 and min(_gaps(boosted)) >= 7 and min(_gaps(boosted)) < 40, _gaps(boosted)
    assert (c.mutagen.boost, c.state_dict()["boost"]) == (1.0, 1.0), "the boost expired, in memory and in dish.json"
    assert c.mutagen.interval() == 40
    later = [(a, b) for a, b in zip(ticks, ticks[1:]) if b >= 300]
    assert later and all(b - a >= 40 for a, b in later), later
    # the wall-clock side of the same fix: the interval used to stay divided forever after the drop
    w = make_culture(mind=_dormant())
    w.mutagen.boost, w.mutagen.boost_until = 6.0, 10
    _step(w, 9)
    assert w.mutagen.boost == 6.0
    w.step()
    assert w.mutagen.boost == 1.0 and w.mutagen.interval() == config.MUTAGEN_INTERVAL


# --- criterion 4: a failing mind backs off in ticks and the culture grows -----------


def test_a_failing_mind_backs_off_in_ticks_and_the_culture_grows(make_culture, ticked):
    ticks: list[int] = []
    mind = FakeMind(replies=[http_error(503)])
    c = _every_division_rolls(make_culture(mind=mind))
    ticked(c, every=40)
    real = mind._request

    def counted(path, body=None, timeout=120):
        if path == "/chat/completions":
            ticks.append(c.dish.tick)
        return real(path, body, timeout)

    mind._request = counted
    twin = _every_division_rolls(make_culture(mind=_dormant()))
    c.run(ticks=2000, tick_seconds=0)
    _step(twin, 2000)
    assert dish_state(c.dish) == dish_state(twin.dish), "identical, not within noise: the roll is consumed either way"
    failed = _failures()
    n = len(failed)
    assert 3 <= n <= 6, n
    assert [ev["retry_in"] for ev in failed] == [80, 160, 320, 640, 1280, 2000][:n]
    assert all(ev["unit"] == "ticks" for ev in failed)
    assert failed[0]["msg"].endswith("next attempt in 80 ticks") and failed[1]["msg"].endswith(
        "next attempt in 160 ticks"
    )
    assert all(ev["status"] == 503 for ev in failed)
    for (a, b), ev in zip(zip(ticks, ticks[1:]), failed):
        assert b - a >= ev["retry_in"], "each attempt waited out the backoff before it"
    m = c.mutagen
    assert m.attempted == n == mind.chat_requests and mind.calls == 0 and m.state == "error"
    assert m.retry_at == ticks[-1] + failed[-1]["retry_in"]
    snap = c.snapshot()
    assert snap["mutagen"]["retry_in"] == m.retry_at - c.dish.tick, "the countdown is in ticks"
    assert re.search(rf"retry in {int(snap['mutagen']['retry_in'])} ticks", _render(tui.vitals(c, snap)))


def test_retry_after_is_a_wall_floor_on_the_tick_clock(make_culture, ticked, no_subprocess, monkeypatch):
    """The tick backoff keeps a fast run from stalling on a dead endpoint; an endpoint that names a
    wait is stating its own constraint, so on the tick clock a Retry-After is a floor on the wall
    clock during which no attempt is made, and a success clears it."""
    mind = FakeMind(replies=[http_error(429, "90")])
    c = make_culture(mind=mind)
    ticked(c, every=40)
    m = c.mutagen
    t0 = time.time()
    assert m.mutate_now(_founder(c)) is None
    assert m.retry_at == 80 and m.failures == 1
    assert t0 + 90 <= m.retry_wall_at <= time.time() + 90
    ev = _failures()[-1]
    assert ev["msg"].endswith("next attempt in 80 ticks (Retry-After 1m30s)") and ev["retry_in"] == 80
    c.dish.tick = 80
    assert m.mutate_now(_founder(c)) is None and mind.chat_requests == 1, "the tick schedule is open; the floor is not"
    monkeypatch.setattr(bio.mutagen.time, "time", lambda: t0 + 91)
    mind.replies = [DAUGHTER]
    got = m.mutate_now(_founder(c))
    assert got is not None and got[0] == "bud" and mind.chat_requests == 2
    assert (m.failures, m.retry_at, m.retry_wall_at, m.state) == (0, 0.0, 0.0, "idle")
    assert (m.attempted, m.viable) == (2, 1)


def test_an_apparatus_fault_does_not_lyse_the_dividing_cell(make_culture, ticked, monkeypatch):
    """A fault inside the mutagen's own code, on the dish thread, would surface inside Dish._apply,
    where anything a genome does wrong is lysis. It is a `mutagen fault` event instead, backed off
    in ticks, and the division is faithful."""

    def boom(**kw):
        raise RuntimeError("no prompt today")

    monkeypatch.setattr(bio.mutagen.prompts, "mutagen_user", boom)
    c = make_culture(mind=FakeMind())
    ticked(c, every=40)
    twin = make_culture(mind=_dormant())
    _step(c, 300)
    _step(twin, 300)
    faults = [ev for ev in c.events if ev["msg"].startswith("mutagen fault")]
    assert faults and "RuntimeError: no prompt today" in faults[0]["msg"]
    assert faults[0]["unit"] == "ticks" and faults[0]["retry_in"] == 80
    assert c.mutagen.state == "error" and c.mind.chat_requests == 0
    assert dish_state(c.dish) == dish_state(twin.dish)
    assert c.dish.deaths.get("lysed", 0) == twin.dish.deaths.get("lysed", 0)


def test_ctrl_c_inside_a_call_ends_the_run_at_a_tick_boundary(make_culture, ticked):
    """An interrupt that arrives while the dish waits on the mind ends the run after this tick, so
    the dish saved on the way out is whole and the resumed one is the twin of an uninterrupted dish."""
    ticks: list[int] = []

    class Interrupted(FakeMind):
        def _request(self, path, body=None, timeout=120):
            if path == "/chat/completions":
                ticks.append(c.dish.tick)
                raise KeyboardInterrupt
            return super()._request(path, body, timeout)

    c = make_culture(mind=Interrupted())
    ticked(c, every=40)
    with pytest.raises(KeyboardInterrupt):
        c.run(ticks=500, tick_seconds=0)
    assert len(ticks) == 1
    assert c.dish.tick == ticks[0] + 1, "the tick the roll happened in was finished"
    assert c.mutagen.attempted == 0, "an interrupted call is not an attempt"
    assert incubating() is None, "the incubator lock was released"
    back = Culture.load(mind=FakeMind())
    assert dish_state(back.dish) == dish_state(c.dish), "a whole tick was saved"
    twin = make_culture(mind=_dormant())
    _step(twin, c.dish.tick)
    assert dish_state(twin.dish) == dish_state(c.dish)


# --- the schedule and the counters are state --------------------------------------


def test_the_tick_schedule_and_counters_survive_a_resume(make_culture, ticked, no_subprocess):
    """A resumed run continues the attempt schedule where it stopped, so a run broken in two has
    the attempt ticks and the dish of one run unbroken; the counters are monotone across it."""
    first: list[int] = []
    c = _every_division_rolls(make_culture(mind=Variator(on_call=lambda: first.append(c.dish.tick))))
    ticked(c, every=40)
    c.run(ticks=600, tick_seconds=0)
    assert first and c.mutagen.attempted == len(first)
    counts = (c.mutagen.attempted, c.mutagen.viable, c.mutagen.nonviable)
    blob = json.loads(config.DISH_FILE.read_text())["culture"]
    assert (blob["attempted"], blob["viable"], blob["nonviable"]) == counts
    assert blob["last_call_tick"] == first[-1] and blob["retry_at_tick"] == 0.0

    second: list[int] = []
    back = Culture.load(mind=Variator(start=counts[0], on_call=lambda: second.append(back.dish.tick)))
    _every_division_rolls(back)
    assert back.last_call_tick == first[-1] and back.mutagen.last_call == 0.0, "applied by use_clock, not before"
    ticked(back, every=40)
    assert back.mutagen.last_call == c.mutagen.last_call == first[-1]
    assert (back.mutagen.attempted, back.mutagen.viable, back.mutagen.nonviable) == counts
    back.run(ticks=600, tick_seconds=0)
    assert second and second[0] >= first[-1] + 40, "the slot did not open at once on the resume"

    whole: list[int] = []
    u = _every_division_rolls(make_culture(mind=Variator(on_call=lambda: whole.append(u.dish.tick))))
    ticked(u, every=40)
    u.run(ticks=1200, tick_seconds=0)
    assert first + second == whole
    assert dish_state(back.dish) == dish_state(u.dish)
    assert back.mutagen.attempted == u.mutagen.attempted == len(whole)

    # a dish sample carries the counters and the schedule with the rest of the culture's state
    sample = freezer.read(back.freeze("check"))["culture"]
    assert (sample["attempted"], sample["last_call_tick"]) == (back.mutagen.attempted, whole[-1])


def test_a_dish_json_from_before_the_clock_opens_the_slot_at_once(make_culture):
    c = make_culture(mind=_dormant())
    c.save()
    blob = json.loads(config.DISH_FILE.read_text())
    for key in ("clock", "clock_used", "every_ticks_used", "attempted", "viable", "nonviable", "last_call_tick"):
        blob["culture"].pop(key, None)
    blob["culture"].pop("retry_at_tick", None)
    config.DISH_FILE.write_text(json.dumps(blob))
    back = Culture.load(mind=FakeMind())
    assert (back.clock_choice, back.clock_used, back.every_ticks_used) == (None, None, None)
    assert back.use_clock(None, "run") == "tick"
    m = back.mutagen
    assert (m.attempted, m.viable, m.nonviable) == (0, 0, 0)
    assert m.last_call == -math.inf and m.retry_at == 0.0
    assert m._open(0.0), "nothing remembered: the first roll may call"


def test_clock_precedence(make_culture, monkeypatch):
    c = make_culture(mind=_dormant())
    assert c.use_clock(None, "live") == "wall" and not c.mutagen.ticked
    assert (
        c.use_clock(None, "run") == "tick" and c.mutagen.ticked and c.mutagen.every_ticks == config.MUTAGEN_EVERY_TICKS
    )
    assert c.use_clock("wall", "run") == "wall" and c.clock_choice == "wall"
    c.save()
    back = Culture.load(mind=_dormant())
    assert back.clock_choice == "wall"
    assert back.use_clock(None, "run") == "wall", "the flag is remembered"
    assert back.use_clock(None, "live") == "wall"
    monkeypatch.setattr(config, "MUTAGEN_CLOCK", "tick")
    assert back.use_clock(None, "run") == "tick" and back.clock_choice == "wall", (
        "env wins per process, not in the dish"
    )
    assert back.use_clock("wall", "run") == "wall", "the flag wins over the environment"
    monkeypatch.setattr(config, "MUTAGEN_CLOCK", "sundial")
    with pytest.raises(ValueError, match=r"^the mutagen clock is wall or tick, not 'sundial'$"):
        back.use_clock(None, "run")
    monkeypatch.setattr(config, "MUTAGEN_CLOCK", None)
    assert back.use_clock("tick", "live") == "tick" and back.clock_choice == "tick"
    back.save()
    assert json.loads(config.DISH_FILE.read_text())["culture"]["clock"] == "tick"


# --- run, status, the vitals --------------------------------------------------------


def test_run_prints_the_clock_and_status_shows_it(make_culture, monkeypatch, capsys):
    c = make_culture(mind=_dormant())
    c.save()
    monkeypatch.setattr(bio.culture, "Mind", lambda: _dormant())
    cli.main(["status"])
    assert re.search(r"^mutagen     clock: not yet run \(live: wall, run: tick\)$", capsys.readouterr().out, re.M)

    cli.main(["run", "--ticks", "3", "--tick", "0", "--clock", "wall"])
    lines = capsys.readouterr().err.splitlines()
    assert lines[0].startswith("budget ") and lines[1] == "mutagen clock: wall, at least 12 s between calls", lines
    blob = json.loads(config.DISH_FILE.read_text())["culture"]
    assert (blob["clock"], blob["clock_used"], blob["every_ticks_used"]) == ("wall", "wall", None)
    cli.main(["status"])
    assert re.search(
        r"^mutagen     clock: wall  \(last run\)  · --clock wall remembered$", capsys.readouterr().out, re.M
    )

    cli.main(["run", "--ticks", "1", "--tick", "0"])
    assert capsys.readouterr().err.splitlines()[1] == "mutagen clock: wall, at least 12 s between calls", "it sticks"
    cli.main(["run", "--ticks", "1", "--tick", "0", "--quiet"])
    assert len(capsys.readouterr().err.splitlines()) == 2, "--quiet: no clock line either"

    monkeypatch.setattr(config, "MUTAGEN_CLOCK", "sundial")
    with pytest.raises(SystemExit, match=r"the mutagen clock is wall or tick, not 'sundial'"):
        cli.main(["run", "--ticks", "1", "--tick", "0"])
    capsys.readouterr()
    monkeypatch.setattr(config, "MUTAGEN_CLOCK", None)

    fresh = make_culture(mind=_dormant())
    fresh.save()
    cli.main(["run", "--ticks", "3", "--tick", "0"])
    lines = capsys.readouterr().err.splitlines()
    assert lines[1] == f"mutagen clock: tick, every {config.MUTAGEN_EVERY_TICKS} ticks"
    cli.main(["status"])
    out = capsys.readouterr().out
    assert re.search(rf"^mutagen     clock: tick, every {config.MUTAGEN_EVERY_TICKS} ticks  \(last run\)$", out, re.M)
    assert "remembered" not in out
    started = [ev for ev in _kinds("mind") if ev["msg"].startswith("mutagen clock")]
    assert [ev["clock"] for ev in started] == ["wall", "wall", "wall", "tick"]


def test_vitals_show_the_clock(make_culture, ticked):
    c = make_culture(mind=FakeMind())
    snap = c.snapshot()
    snap["mutagen"].update(viable=123, nonviable=456)
    text = _render(tui.vitals(c, snap), 48)
    assert re.search(r"^\s+mutagen ○ idle  0 ready · 0 queued\s*$", text, re.M), text
    assert re.search(r"^\s+wall 123 viable · 456 nonviable\s*$", text, re.M), text
    ticked(c, every=40)
    snap = c.snapshot()
    text = _render(tui.vitals(c, snap), 48)
    assert re.search(r"^\s+mutagen ○ idle  every 40 ticks\s*$", text, re.M), text
    assert re.search(r"^\s+tick 0 viable · 0 nonviable\s*$", text, re.M), text
    assert " · tick · " in tui.vitals_strip(c, snap).plain and "ready" not in tui.vitals_strip(c, snap).plain
    c.mutagen.state, c.mutagen.failures, c.mutagen.retry_at = "error", 1, 80.0
    c.dish.tick = 30
    snap = c.snapshot()
    assert snap["mutagen"]["retry_in"] == 50.0
    assert re.search(r"^\s+mutagen ! error  every 40 ticks  retry in 50 ticks\s*$", _render(tui.vitals(c, snap)), re.M)
