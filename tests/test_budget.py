"""The budget, end to end: the mutagen backs off from a failing mind and stops when the money is
spent; the culture persists the ledger, grows on without variation, and shows spent / budget."""

from __future__ import annotations

import http.client
import json
import re
import threading
import time

import pytest
from rich.console import Console

import bio.__main__ as cli
import bio.culture
import bio.mutagen
from bio import config, tui
from bio.culture import FALLBACK_GENESIS, HIDDEN, Culture
from bio.dish import Dish
from bio.membrane import Verdict
from bio.mutagen import Mutagen, fmt_wait

from .conftest import DAUGHTER, FakeMind, http_error


def _failures(events: list[dict]) -> list[dict]:
    return [ev for ev in events if ev["kind"] == "mind" and ev["msg"].startswith("mutagen call failed")]


def _exhaustions(events: list[dict]) -> list[dict]:
    return [ev for ev in events if ev["kind"] == "mind" and ev["msg"].startswith("mutagen exhausted")]


def _founder(c: Culture) -> str:
    return next(iter(c.registry.strains))


def _one_call() -> FakeMind:
    """A mind that can afford exactly one call: 2000 tokens at $5 per M is a cent."""
    return FakeMind(budget_usd=0.01)


def _dormant(budget_usd: float | None = 0.0) -> FakeMind:
    m = FakeMind(budget_usd=budget_usd)
    m.key = None
    return m


def _render(renderable, width: int = 80) -> str:
    console = Console(record=True, width=width, force_terminal=False)
    console.print(renderable)
    return console.export_text()


def _logged() -> list[dict]:
    """Every event in events.jsonl: the complete record, as against the culture's recent events."""
    if not config.EVENTS.exists():
        return []
    return [json.loads(line) for line in config.EVENTS.read_text().splitlines()]


def _said(prefix: str) -> list[dict]:
    return [ev for ev in _logged() if ev["msg"].startswith(prefix)]


def _run_a_tick(c: Culture) -> None:
    """One tick through run(): what a resumed process does first. The mutagen thread is started
    and closed with it; a dormant or exhausted mind makes no call, and at tick 1 nothing divides,
    so an idle one has nothing to pick either."""
    c.run(ticks=1, tick_seconds=0)
    c.mutagen.join(2)
    assert not c.mutagen.is_alive()


# --- the mutagen: backoff -------------------------------------------------------


def test_dead_endpoint_backs_off_exponentially(mutagen, clock):
    m = mutagen(FakeMind(replies=[http_error(503)]))
    called_at = []
    while clock.now <= 3600:
        called_at.append(clock.now)
        m._mutate("f")
        clock.now = m.retry_at
    assert called_at == [0, 15, 45, 105, 225, 465, 945, 1545, 2145, 2745, 3345]
    events = _failures(m.mind.events)
    assert len(events) == 11, "eleven error events in the first hour, not 240"
    assert m.failures == 11
    assert m.state == "error"
    assert [ev["retry_in"] for ev in events] == [15, 30, 60, 120, 240, 480, 600, 600, 600, 600, 600]
    assert [ev["failures"] for ev in events] == list(range(1, 12))
    assert all(ev["status"] == 503 and "latency" in ev for ev in events)
    assert events[0]["msg"].endswith("next attempt in 15s")
    assert events[-1]["msg"].endswith("next attempt in 10m00s")
    assert m.mind.spent_usd == 0.0 and m.mind.calls == 0


def test_a_reply_cut_short_is_a_failed_call(mutagen, clock):
    """`IncompleteRead` is an `HTTPException`, not an `OSError`: it must still come out of `think`
    as a `MindError`, so the mutagen backs off with a status and a latency instead of catching
    it as a fault, and genesis does not end `biotic seed` with a traceback."""
    m = mutagen(FakeMind(replies=[http.client.IncompleteRead(b"")]))
    m._mutate("f")
    assert m.state == "error" and m.failures == 1
    failed = _failures(m.mind.events)
    assert len(failed) == 1 and "IncompleteRead" in failed[0]["msg"]
    assert not [ev for ev in m.mind.events if ev["msg"].startswith("mutagen fault")]
    assert m.mind.last_error is not None and m.mind.last_error.startswith("IncompleteRead")


def test_retry_after_is_honoured_and_capped(mutagen, clock):
    m = mutagen(FakeMind(replies=[http_error(429, "90"), http_error(429, "999999"), http_error(429, "1")]))
    m._mutate("f")
    assert m.retry_at - clock.now == 90
    assert _failures(m.mind.events)[-1]["status"] == 429
    clock.now = m.retry_at
    m._mutate("f")
    assert m.retry_at - clock.now == config.RETRY_AFTER_MAX
    clock.now = m.retry_at
    m._mutate("f")
    assert m.retry_at - clock.now == 60, "a short Retry-After never shortens the exponential schedule"


def test_success_resets_backoff_and_fills_the_pool(mutagen, clock, no_subprocess):
    m = mutagen(FakeMind(replies=[http_error(500)] * 3 + [DAUGHTER]))
    for _ in range(3):
        m._mutate("f")
        clock.now = m.retry_at
    assert m.failures == 3
    m._mutate("f")
    assert (m.failures, m.retry_at, m.state) == (0, 0.0, "idle")
    assert m.ready() == 1
    assert m.produced == 1
    prepared = [ev for ev in m.mind.events if ev["kind"] == "prepared"]
    assert len(prepared) == 1 and "divides a little sooner" in prepared[0]["msg"]
    dname, note, src = m.take("f")
    assert dname == "bud" and "0.9" in src
    # the next failure starts the schedule from the beginning
    m.mind.replies = [http_error(500)]
    m._mutate("f")
    assert m.retry_at - clock.now == 15


def test_nothing_is_picked_while_backing_off(mutagen, clock, monkeypatch):
    m = mutagen(FakeMind(replies=[http_error(500)]))
    m.last_call = -1000
    m.request("f")
    assert m._cycle() is False
    assert (m.failures, m.retry_at) == (1, 15)
    waited = []
    monkeypatch.setattr(m.stop, "wait", lambda t: waited.append(t) or False)
    m.request("f")
    for now in (0.0, 7.0, 14.9):
        clock.now = now
        assert m._cycle() is False
    assert m.pending() == 1, "the request waits in the queue, not in a strain picked and held"
    assert m.mind.chat_requests == 1
    assert waited == [], "the loop polls; it does not sleep out the backoff"
    clock.now = m.retry_at
    assert m._cycle() is False
    assert m.mind.chat_requests == 2
    assert m.pending() == 0
    assert m.failures == 2


def test_close_interrupts_the_interval_wait(mutagen, clock):
    m = mutagen(FakeMind())
    m.last_call = clock.now  # a call just happened: the next must wait the interval
    m.request("f")
    m.close()
    assert m._cycle() is True
    assert m.mind.chat_requests == 0


# --- the mutagen: exhaustion ----------------------------------------------------


def test_exhaustion_logs_once_and_stops_calling(mutagen, clock, no_subprocess):
    m = mutagen(_one_call())
    m._mutate("f")
    assert m.mind.calls == 1
    assert m.mind.exhausted
    assert m.state == "exhausted"
    assert m.ready() == 1, "the daughter from the exhausting call was paid for and stays in the pool"
    events = _exhaustions(m.mind.events)
    assert len(events) == 1
    assert "$0.010 / $0.01" in events[0]["msg"]
    assert events[0]["spent_usd"] == pytest.approx(0.01)
    for _ in range(2):
        m.request("f")
        assert m._cycle() is False
    assert m.mind.calls == 1
    assert m.mind.chat_requests == 1
    assert len(_exhaustions(m.mind.events)) == 1
    assert m.state == "exhausted"


def test_a_mutagen_restored_exhausted_starts_exhausted_without_an_event(mutagen, clock):
    m = mutagen(FakeMind(budget_usd=0.0))
    assert m.state == "exhausted", "a resumed dish that already spent its budget starts exhausted"
    m.request("f")
    m._cycle()
    assert m.mind.calls == 0
    assert m.pending() == 1
    assert _exhaustions(m.mind.events) == [], "nothing new to say: the earlier event is in the log"


def test_raising_the_budget_resumes(mutagen, clock, no_subprocess):
    m = mutagen(FakeMind(budget_usd=0.0))
    m.request("f")
    m._cycle()
    assert m.mind.calls == 0
    m.mind.budget_usd = 1.0
    m.last_call = -1000
    m._cycle()
    assert m.state == "idle"
    assert m.mind.calls == 1
    assert m.ready() == 1


def test_forgotten_strain_does_not_kill_the_thread(mutagen, clock, monkeypatch):
    m = mutagen(FakeMind())
    m._mutate("gone")
    assert m.mind.chat_requests == 0
    assert m.state == "idle"

    def boom(strain):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(m, "_mutate", boom)
    m.request("f")
    m.last_call = -1000
    assert m._cycle() is False
    assert (m.state, m.failures) == ("error", 1)
    faults = [ev for ev in m.mind.events if ev["msg"].startswith("mutagen fault")]
    assert len(faults) == 1 and "RuntimeError" in faults[0]["msg"]
    assert m.retry_at == 15


def test_a_fault_in_the_fault_handling_does_not_end_the_thread(mutagen, clock):
    """`_turn` is the loop body. When even `_fail` raises — here the log is what is broken — the
    turn ends in the error state with the longest wait, nothing propagates, and the next turn
    backs off like any other."""
    m = mutagen(FakeMind(replies=[http_error(500)]))
    recorded = m.mind._record

    def broken_log(kind, msg, **data):
        if msg.startswith("mutagen"):
            raise OSError("disk full")
        recorded(kind, msg, **data)

    m.log = broken_log
    m.last_call = -1000
    m.request("f")
    assert m._turn() is False
    assert m.state == "error"
    assert m.failures == 3, "the failed call, the fault in saying so, and the last resort"
    assert m.retry_at == clock.now + config.MUTAGEN_BACKOFF_MAX
    assert m.mind.chat_requests == 1
    assert [ev for ev in m.mind.events if ev["msg"].startswith("mutagen")] == []
    m.request("f")
    assert m._turn() is False
    assert m.mind.chat_requests == 1, "backing off"
    assert m.pending() == 1


def test_a_keyless_mind_with_no_budget_is_dormant_not_exhausted(mutagen):
    m = mutagen(_dormant(budget_usd=0.0))
    assert m.state == "dormant"
    m.request("f")
    assert m._cycle() is False
    assert m.state == "dormant"
    assert m.mind.chat_requests == 0
    assert _exhaustions(m.mind.events) == []


def test_waits_are_printed_for_people():
    assert [fmt_wait(s) for s in (15, 120, 600, 3600, 5400)] == ["15s", "2m00s", "10m00s", "1h00m", "1h30m"]


def test_run_loop_respects_exhaustion(monkeypatch):
    """The one test that starts the thread: the real loop on the real clock, with the membrane
    stubbed (its alarm only works on the main thread)."""
    monkeypatch.setattr(bio.mutagen, "admit_isolated", lambda src: Verdict(True))
    mind = _one_call()
    exhausted = threading.Event()

    def log(kind: str, msg: str, **data) -> None:
        mind._record(kind, msg, **data)
        if msg.startswith("mutagen exhausted"):
            exhausted.set()

    m = Mutagen(mind, "test", log)
    m.know("f", "founder", FALLBACK_GENESIS)
    m.context = {"census": {"f": 5}}
    m.start()
    try:
        m.request("f")
        assert exhausted.wait(5), "the first call spends the budget and the loop says so"
        m.request("f")
        m.wake.set()
        time.sleep(0.2)  # room for a second call, were the loop going to make one
    finally:
        m.close()
        m.join(2)
    assert not m.is_alive()
    assert (mind.chat_requests, mind.calls) == (1, 1)
    assert m.state == "exhausted"
    assert m.ready() == 1
    assert len(_exhaustions(mind.events)) == 1
    assert _failures(mind.events) == []


# --- the culture ----------------------------------------------------------------


def test_exhausted_dish_keeps_growing(make_culture, no_subprocess, monkeypatch):
    monkeypatch.setattr(config, "BUDGET_USD", 0.01)  # BIOTIC_BUDGET_USD=0.01
    c = make_culture(mind=FakeMind(budget_usd=None))
    assert c.mind.budget_usd == 0.01
    c.mutagen._mutate(_founder(c))
    assert c.mind.spent_usd == pytest.approx(0.01)
    assert c.mind.exhausted and c.mutagen.state == "exhausted"
    assert c.mutagen.ready() == 1
    before = len(c.dish.cells)
    for _ in range(150):
        c.step()
    assert c.dish.tick == 150
    assert len(c.dish.cells) > before >= config.INOCULUM
    assert c.dish.births > 0
    c.mutagen.request(_founder(c))  # a division rolled a mutation with nothing in the pool
    assert c.mutagen._cycle() is False
    assert (c.mind.calls, c.mind.chat_requests) == (1, 1), "no call after the budget was spent"
    assert c.mutagen.pending() == 1, "the request waits, in case the budget is raised"
    assert len(_exhaustions(c.events)) == 1
    snap = c.snapshot()
    assert snap["mind"]["exhausted"] is True and snap["mutagen"]["state"] == "exhausted"


def test_bookkeeping_does_not_crowd_the_incubator_log(make_culture):
    """One `call` every twelve seconds would push the dish's own events out of the 200 the
    eyepiece keeps. Bookkeeping goes to events.jsonl only, on a live dish and on a resumed one."""
    c = make_culture(mind=_dormant())
    c.save()
    for i in range(300):
        c.log("call", f"call {i}", usd=0.0)
        c.log("prepared", f"variant {i}")
        if i % 10 == 0:
            c.log("arose", f"strain {i} arose")
    assert len(_logged()) == 630
    assert [ev["kind"] for ev in c.events] == ["arose"] * 30
    back = Culture.load(mind=_dormant())
    assert [ev["kind"] for ev in back.events] == ["arose"] * 30, "resumed: the last visible events, not the last lines"
    assert "strain 290 arose" in tui.events(back, 7).plain


def test_growth_is_the_same_with_and_without_a_ledger(make_culture):
    """The tick path draws nothing new from the RNG: an exhausted dish and a dormant one grow identically."""
    exhausted = make_culture(mind=FakeMind(budget_usd=0.0))
    dormant = make_culture(mind=_dormant())
    assert exhausted.mutagen.state == "exhausted" and dormant.mutagen.state == "dormant"
    for _ in range(120):
        exhausted.step()
        dormant.step()
    assert exhausted.dish.census() == dormant.dish.census()
    assert exhausted.dish.rng.getstate() == dormant.dish.rng.getstate()
    assert exhausted.dish.nutrient_mean() == dormant.dish.nutrient_mean()
    assert exhausted.dish.births == dormant.dish.births


def test_budget_and_spend_round_trip_through_the_vessel(make_culture, no_subprocess):
    c = make_culture(mind=_one_call())
    c.mutagen._mutate(_founder(c))
    for _ in range(5):
        c.step()
    c.save()
    raw = json.loads(config.DISH_FILE.read_text())
    assert raw["mind"] == {
        "model": "test/model",
        "budget_usd": 0.01,
        "spent_usd": pytest.approx(0.01),
        "calls": 1,
        "prompt_tokens": 1000,
        "completion_tokens": 1000,
    }
    assert Dish.from_dict(raw).census() == c.dish.census(), "the physics layer ignores the ledger"

    back = Culture.load(mind=FakeMind())
    assert (back.dish.tick, back.dish.census()) == (c.dish.tick, c.dish.census())
    assert back.mind.spent_usd == pytest.approx(0.01)
    assert back.mind.calls == 1
    assert back.mind.budget_usd == 0.01, "the dish's budget wins over the mind's construction default"
    assert back.mutagen.state == "exhausted"
    assert _exhaustions(back.events)[-1]["tick"] == 0, "the event is the old one, read back from the log"
    assert not [ev for ev in back.events if ev["msg"].startswith("ledger caught up")]

    raised = Culture.load(mind=FakeMind(), budget=0.5)
    assert raised.mind.budget_usd == 0.5
    assert raised.mutagen.state == "idle"
    raised.save()
    assert json.loads(config.DISH_FILE.read_text())["mind"]["budget_usd"] == 0.5

    raised.mind.budget_usd = float("inf")
    raised.save()
    assert json.loads(config.DISH_FILE.read_text())["mind"]["budget_usd"] is None
    assert Culture.load(mind=FakeMind()).mind.budget_usd == float("inf")


def test_old_dish_json_loads_without_a_ledger(monkeypatch):
    dish = Dish("test", 24, 12)
    dish.register("f", FALLBACK_GENESIS)
    dish.inoculate("f")
    config.DISH_FILE.write_text(json.dumps(dish.to_dict()))
    config.SEED_FILE.write_text("test\n")
    monkeypatch.setattr(config, "BUDGET_USD", 1.25)
    c = Culture.load(mind=FakeMind(budget_usd=None))
    assert c.mind.budget_usd == 1.25
    assert c.mind.spent_usd == 0.0
    assert c.mind.calls == 0
    assert c.mutagen.state == "idle"
    assert c.dish.census() == {"f": config.INOCULUM}


def test_ledger_catches_up_from_the_log_after_a_hard_kill(make_culture, no_subprocess, monkeypatch, capsys):
    c = make_culture(mind=FakeMind())
    c.save()  # the last save the process managed
    for _ in range(2):
        c.mutagen._mutate(_founder(c))  # two calls later the process is killed
    assert json.loads(config.DISH_FILE.read_text())["mind"]["spent_usd"] == 0.0
    lines = len(_logged())

    monkeypatch.setattr(bio.culture, "Mind", lambda: FakeMind())
    cli.main(["status"])
    out = capsys.readouterr().out
    assert re.search(r"^spent\s+\$0\.020 / \$2\.00  \(2 calls\)$", out, re.M), out
    assert len(_logged()) == lines, "status shows the true figure and writes nothing: it may run beside a live dish"

    back = Culture.load(mind=FakeMind())
    assert back.mind.spent_usd == pytest.approx(0.02)
    assert back.mind.calls == 2
    assert not [ev for ev in back.events if ev["msg"].startswith("ledger caught up")], "nothing said until it runs"
    _run_a_tick(back)  # the process that runs the dish says it, and saves it
    said = _said("ledger caught up")
    assert len(said) == 1 and "$0.000 saved, $0.020 spent" in said[0]["msg"]
    assert json.loads(config.DISH_FILE.read_text())["mind"]["spent_usd"] == pytest.approx(0.02)

    again = Culture.load(mind=FakeMind())
    assert again.mind.spent_usd == pytest.approx(0.02)
    _run_a_tick(again)
    assert len(_said("ledger caught up")) == 1, "said once, when it changed something"


def test_the_log_is_read_from_its_tail(make_culture):
    """A week's log is tens of megabytes. A load reads its last 64 KiB, and the whole of it only
    when the tail holds no call at all."""
    c = make_culture(mind=_dormant())
    c.save()
    pad = "x" * 200
    c.log("call", "early", spent_usd=0.5, calls=1)
    for i in range(600):
        c.log("curve", f"row {i} {pad}")
    assert config.EVENTS.stat().st_size > 2 * 64 * 1024
    lines, whole = bio.culture._tail(config.EVENTS)
    assert not whole
    assert 100 < len(lines) < 600
    assert all(json.loads(line)["kind"] == "curve" for line in lines), "the cut line is dropped; the rest parse"
    assert bio.culture._last_call(config.EVENTS)["spent_usd"] == 0.5, "found past the tail when the tail holds none"
    c.log("call", "late", spent_usd=0.7, calls=2)
    assert bio.culture._last_call(config.EVENTS)["spent_usd"] == 0.7
    back = Culture.load(mind=_dormant())
    assert back.mind.spent_usd == 0.7
    assert len(back.events) == 60 and all(ev["kind"] == "curve" for ev in back.events)
    assert back.events[-1]["msg"].startswith("row 599")


def test_lowering_the_budget_below_the_spend_exhausts_once(make_culture, no_subprocess):
    c = make_culture(mind=FakeMind())
    for _ in range(2):
        c.mutagen._mutate(_founder(c))
    c.save()
    assert _said("mutagen exhausted") == []
    back = Culture.load(mind=FakeMind(), budget=0.015)
    assert back.mind.exhausted and back.mutagen.state == "exhausted"
    assert _said("mutagen exhausted") == [], "load says nothing"
    _run_a_tick(back)
    said = _said("mutagen exhausted")
    assert len(said) == 1
    assert "$0.020 / $0.015" in said[0]["msg"] and "lowered below the spend" in said[0]["msg"]
    assert (said[0]["spent_usd"], said[0]["budget_usd"]) == (pytest.approx(0.02), 0.015)
    assert back.mind.calls == 2, "no call was made"
    again = Culture.load(mind=FakeMind())
    assert (again.mind.budget_usd, again.mutagen.state) == (0.015, "exhausted")
    _run_a_tick(again)
    assert len(_said("mutagen exhausted")) == 1, "resumed as it is, nothing more is said"


def test_genesis_calls_are_costed(monkeypatch, no_subprocess):
    monkeypatch.setattr(bio.culture, "trial", lambda seed, src: (20, 20, 500))
    monkeypatch.setattr(bio.culture, "_fit_dish", lambda: (24, 12))

    mind = FakeMind(replies=[DAUGHTER])
    c = Culture.germinate("test", mind, fresh=True, budget=0.75)
    assert mind.calls == 1
    assert mind.spent_usd == pytest.approx(0.01)
    assert mind.budget_usd == 0.75
    founder = next(iter(c.registry.strains.values()))
    assert founder.name == "bud"
    assert json.loads(config.DISH_FILE.read_text())["mind"]["budget_usd"] == 0.75
    events = [json.loads(line) for line in config.EVENTS.read_text().splitlines()]
    calls = [ev for ev in events if ev["kind"] == "call"]
    assert len(calls) == 1 and calls[0]["usd"] == pytest.approx(0.01)
    assert config.PRICES_FILE.exists()

    broke = FakeMind(replies=[DAUGHTER], budget_usd=0.0)
    c = Culture.germinate("test", broke, fresh=True)
    assert broke.calls == 0
    assert broke.chat_requests == 0
    founder = next(iter(c.registry.strains.values()))
    assert founder.name == "founder" and founder.source == FALLBACK_GENESIS
    stopped = [ev for ev in c.events if ev["msg"].startswith("genesis stopped")]
    assert len(stopped) == 1 and "budget spent: $0.000 / $0.00" in stopped[0]["msg"]
    assert not [ev for ev in c.events if "could not write a founder" in ev["msg"]], "it never tried; it had nothing"
    said = _exhaustions(c.events)
    assert len(said) == 1 and "nothing to spend" in said[0]["msg"] and "$0.000 / $0.00" in said[0]["msg"]
    assert [ev["kind"] for ev in c.events if ev["kind"] == "mind"] == ["mind", "mind"], "stopped, and exhausted"
    assert c.mutagen.state == "exhausted"
    back = Culture.load(mind=FakeMind(budget_usd=None))
    assert back.mutagen.state == "exhausted"
    _run_a_tick(back)
    assert len(_said("mutagen exhausted")) == 1, "taken up again, nothing more is said"


def test_a_budget_spent_by_the_founding_calls_is_said_once(monkeypatch, no_subprocess):
    """The founder call can cost the whole budget, or attempts that did not take can spend it
    before one does. Either way the dish would grow for a week without variation, so `seed` says
    why, once, after the genesis event; the resumed dish is built exhausted from the ledger and
    neither load() nor run() says it again."""
    monkeypatch.setattr(bio.culture, "trial", lambda seed, src: (20, 20, 500))
    monkeypatch.setattr(bio.culture, "_fit_dish", lambda: (24, 12))

    mind = FakeMind(replies=[DAUGHTER], budget_usd=0.01)  # the founder call is the one call it can afford
    c = Culture.germinate("test", mind, fresh=True)
    assert (mind.calls, mind.exhausted) == (1, True)
    assert next(iter(c.registry.strains.values())).name == "bud"
    said = _exhaustions(c.events)
    assert len(said) == 1 and "$0.010 / $0.01" in said[0]["msg"] and "spent by the founding calls" in said[0]["msg"]
    assert (said[0]["spent_usd"], said[0]["budget_usd"]) == (pytest.approx(0.01), 0.01)
    # said after the genesis event; the genesis freeze comes last of all
    assert [ev["kind"] for ev in c.events][-3:] == ["genesis", "mind", "frozen"]
    assert c.mutagen.state == "exhausted"
    back = Culture.load(mind=FakeMind(budget_usd=None))
    assert back.mutagen.state == "exhausted"
    _run_a_tick(back)
    assert len(_said("mutagen exhausted")) == 1, "taken up again, nothing more is said"

    reaching = "NAME: escapee\nNOTE: reaches out of the dish\n---\nimport os\n\ndef live(me):\n    return 'rest'\n"
    mind = FakeMind(replies=[reaching], budget_usd=0.02)  # two attempts the membrane rejects, then nothing left
    c = Culture.germinate("test", mind, fresh=True)
    assert (mind.calls, mind.chat_requests, mind.exhausted) == (2, 2, True)
    founder = next(iter(c.registry.strains.values()))
    assert founder.name == "founder" and founder.source == FALLBACK_GENESIS
    assert len([ev for ev in c.events if ev["kind"] == "nonviable"]) == 2
    stopped = _said("genesis stopped")
    assert len(stopped) == 1 and "budget spent: $0.020 / $0.02" in stopped[0]["msg"]
    assert "built-in default" in stopped[0]["msg"]
    assert not _said("mind could not write a founder"), "it did not try and fail; it ran out of money"
    said = _exhaustions(c.events)
    assert len(said) == 1 and "$0.020 / $0.02" in said[0]["msg"] and "spent by the founding calls" in said[0]["msg"]
    _run_a_tick(Culture.load(mind=FakeMind(budget_usd=None)))
    assert len(_said("mutagen exhausted")) == 1


# --- status, run, the eyepiece --------------------------------------------------


def test_status_prints_spent_over_budget(make_culture, no_subprocess, monkeypatch, capsys):
    c = make_culture(mind=_one_call())
    c.mutagen._mutate(_founder(c))
    c.save()
    monkeypatch.setattr(bio.culture, "Mind", lambda: FakeMind())
    cli.main(["status"])
    out = capsys.readouterr().out
    assert re.search(r"^spent\s+\$0\.010 / \$0\.01  \(1 call\)  — exhausted$", out, re.M), out
    assert re.search(r"^mind\s+test/model  awake$", out, re.M)


def test_status_of_a_dormant_dish_does_not_say_exhausted(make_culture, monkeypatch, capsys):
    c = make_culture(mind=_dormant(budget_usd=0.0))
    c.save()
    monkeypatch.setattr(bio.culture, "Mind", lambda: _dormant(budget_usd=None))
    cli.main(["status"])
    out = capsys.readouterr().out
    assert re.search(r"^mind\s+test/model  dormant$", out, re.M), out
    assert re.search(r"^spent\s+\$0\.000 / \$0\.00  \(0 calls\)$", out, re.M), out
    assert "exhausted" not in out


def test_budget_flag_sticks_after_a_headless_run(make_culture, monkeypatch, capsys):
    c = make_culture(mind=_dormant())
    c.save()
    monkeypatch.setattr(bio.culture, "Mind", lambda: _dormant(budget_usd=None))
    cli.main(["run", "--ticks", "3", "--tick", "0", "--budget", "0.25"])
    err = capsys.readouterr().err
    assert err.startswith("budget $0.000 / $0.25\n"), err
    assert re.search(r"^tick\s+3 .* \$0\.000$", err, re.M), err
    assert json.loads(config.DISH_FILE.read_text())["mind"]["budget_usd"] == 0.25
    cli.main(["status"])
    assert re.search(r"^spent\s+\$0\.000 / \$0\.25  \(0 calls\)$", capsys.readouterr().out, re.M)
    cli.main(["run", "--ticks", "1", "--tick", "0", "--quiet", "--budget", "inf"])
    lines = capsys.readouterr().err.splitlines()
    assert not [ln for ln in lines if ln.startswith("budget")], "--quiet: no budget line and no progress reports"
    assert len(lines) == 2 and lines[1].startswith("done in"), "only the summary at the end"
    assert re.search(r"^tick\s+4 .* \$0\.000$", lines[0]), lines
    assert json.loads(config.DISH_FILE.read_text())["mind"]["budget_usd"] is None


def test_eyepiece_hides_call_events_and_shows_the_budget(make_culture, no_subprocess):
    c = make_culture(mind=_one_call())
    c.mutagen._mutate(_founder(c))
    assert [ev["kind"] for ev in _logged()].count("call") == 1, "the call is in events.jsonl"
    assert not any(ev["kind"] in HIDDEN for ev in c.events), "and not among the recent events"
    log = tui.events(c, 20).plain
    assert "tok ·" not in log
    assert "mutagen exhausted" in log
    text = _render(tui.vitals(c, c.snapshot()))
    assert re.search(r"spent\s+\$0\.010 / \$0\.01", text), text
    assert "exhausted" in text
    # the whole frame still composes
    frame = Console(record=True, width=120, height=40, force_terminal=False)
    frame.print(tui.build(c, (120, 40)))
    assert "$0.010 / $0.01" in frame.export_text()
    # a dish with no mind has nothing to show
    quiet = make_culture(mind=_dormant())
    assert "spent" not in _render(tui.vitals(quiet, quiet.snapshot()))


def test_eyepiece_shows_the_retry_countdown(make_culture):
    c = make_culture(mind=FakeMind())
    c.mutagen.clock = lambda: 1000.0
    c.mutagen.state = "error"
    c.mutagen.failures = 2
    c.mutagen.retry_at = 1042.0
    snap = c.snapshot()
    assert (snap["mutagen"]["retry_in"], snap["mutagen"]["failures"]) == (42.0, 2)
    assert "retry in 42s" in _render(tui.vitals(c, snap))
