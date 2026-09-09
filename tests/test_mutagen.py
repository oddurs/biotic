"""The mutagen backs off from a failing mind, honours Retry-After, and stops when the budget is spent."""

from __future__ import annotations

import pytest

from bio import config
from bio.mutagen import _fmt_wait

from .conftest import DAUGHTER, FakeMind, http_error


def _failures(m):
    return [ev for ev in m.mind.events if ev["kind"] == "mind" and ev["msg"].startswith("mutagen call failed")]


def _exhaustions(m):
    return [ev for ev in m.mind.events if ev["kind"] == "mind" and ev["msg"].startswith("mutagen exhausted")]


def test_dead_endpoint_backs_off_exponentially(mutagen, clock):
    m = mutagen(FakeMind(replies=[http_error(503) for _ in range(50)]))
    called_at = []
    while clock.now <= 3600:
        called_at.append(clock.now)
        m._mutate("f")
        clock.now = m.retry_at
    assert called_at == [0, 15, 45, 105, 225, 465, 945, 1545, 2145, 2745, 3345]
    events = _failures(m)
    assert len(events) == 11
    assert m.failures == 11
    assert m.state == "error"
    assert [ev["retry_in"] for ev in events] == [15, 30, 60, 120, 240, 480, 600, 600, 600, 600, 600]
    assert [ev["failures"] for ev in events] == list(range(1, 12))
    assert all(ev["status"] == 503 for ev in events)
    assert events[0]["msg"].endswith("next attempt in 15s")
    assert events[-1]["msg"].endswith("next attempt in 10m00s")
    assert m.mind.spent_usd == 0.0


def test_retry_after_is_honoured_and_capped(mutagen, clock):
    m = mutagen(FakeMind(replies=[http_error(429, "90"), http_error(429, "999999"), http_error(429, "1")]))
    m._mutate("f")
    assert m.retry_at - clock.now == 90
    assert _failures(m)[-1]["status"] == 429
    clock.now = m.retry_at
    m._mutate("f")
    assert m.retry_at - clock.now == config.RETRY_AFTER_MAX
    clock.now = m.retry_at
    m._mutate("f")
    assert m.retry_at - clock.now == 60, "a short Retry-After never shortens the exponential schedule"


def test_success_resets_backoff_and_fills_the_pool(mutagen, clock):
    m = mutagen(FakeMind(replies=[http_error(500) for _ in range(3)] + [DAUGHTER]))
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
    m.mind.replies.append(http_error(500))
    m._mutate("f")
    assert m.retry_at - clock.now == 15


def test_exhaustion_logs_once_and_stops_calling(mutagen, clock):
    m = mutagen(FakeMind(budget_usd=0.01))
    m._mutate("f")
    assert m.mind.calls == 1
    assert m.mind.exhausted
    assert m.state == "exhausted"
    assert m.ready() == 1, "the daughter from the exhausting call was paid for and stays in the pool"
    events = _exhaustions(m)
    assert len(events) == 1
    assert "$0.010 / $0.01" in events[0]["msg"]
    assert events[0]["spent_usd"] == pytest.approx(0.01)
    for _ in range(2):
        m.request("f")
        assert m._cycle() is False
    assert m.mind.calls == 1
    assert m.mind.chat_requests == 1
    assert len(_exhaustions(m)) == 1
    assert m.state == "exhausted"


def test_cycle_respects_exhaustion_before_picking(mutagen, clock):
    m = mutagen(FakeMind(budget_usd=0.0))
    assert m.state == "exhausted", "a resumed dish that already spent its budget starts exhausted"
    m.request("f")
    m._cycle()
    assert m.mind.calls == 0
    assert m.pending() == 1
    assert _exhaustions(m) == [], "nothing new to say: the earlier event is in the log"


def test_raising_the_budget_resumes(mutagen, clock):
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


def test_cycle_waits_out_the_backoff(mutagen, clock, monkeypatch):
    m = mutagen(FakeMind(replies=[http_error(500)]))
    m.last_call = -1000
    m.request("f")
    m._cycle()
    assert m.failures == 1
    waited = []
    monkeypatch.setattr(m.stop, "wait", lambda t: waited.append(t) or False)
    m.request("f")
    m.last_call = -1000
    m._cycle()
    assert waited == [15.0], "the loop sleeps until retry_at rather than inside _mutate"
    assert m.mind.chat_requests == 2


def test_close_interrupts_a_backoff_wait(mutagen, clock):
    m = mutagen(FakeMind(replies=[http_error(500)]))
    m.last_call = -1000
    m.request("f")
    m._cycle()
    m.close()
    m.request("f")
    m.last_call = -1000
    assert m._cycle() is True
    assert m.mind.chat_requests == 1


def test_waits_are_printed_for_humans():
    assert [_fmt_wait(s) for s in (15, 120, 600, 3600, 5400)] == ["15s", "2m00s", "10m00s", "1h00m", "1h30m"]
