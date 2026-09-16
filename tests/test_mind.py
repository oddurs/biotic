"""The mind prices every call, keeps a ledger, and refuses to call once the budget is spent."""

from __future__ import annotations

import http.client
import json
import urllib.error
from email.utils import formatdate
from types import SimpleNamespace

import pytest

import bio.mind
from bio import config
from bio.mind import Exhausted, MindError, backoff, fmt_budget, fmt_usd

from .conftest import FakeMind, http_error


def _events(m: FakeMind, kind: str) -> list[dict]:
    return [ev for ev in m.events if ev["kind"] == kind]


def test_prices_are_fetched_after_the_first_reply_and_cached():
    m = FakeMind()
    assert not config.PRICES_FILE.exists()
    m.think("s", "u")
    assert m.models_requests == 1
    assert m.priced is True
    assert m.price == {"prompt": 5e-6, "completion": 5e-6, "request": 0.0}
    cache = json.loads(config.PRICES_FILE.read_text())
    assert cache["base"] == m.base
    assert cache["fetched_at"] > 0
    assert cache["prices"]["test/model"] == {"prompt": 5e-6, "completion": 5e-6, "request": 0.0}
    assert any("price list cached" in ev["msg"] for ev in _events(m, "mind"))

    second = FakeMind()
    second.think("s", "u")
    assert second.models_requests == 0, "the second process reads the cache instead of asking again"
    assert second.price == m.price
    assert second.spent_usd == pytest.approx(0.01)
    assert any("price list read from prices.json" in ev["msg"] for ev in _events(second, "mind"))


def test_dead_endpoint_never_asks_for_prices():
    m = FakeMind(replies=[http_error(503)])
    for _ in range(3):
        with pytest.raises(MindError):
            m.think("s", "u")
    assert m.models_requests == 0
    assert not config.PRICES_FILE.exists()
    assert m.spent_usd == 0.0
    assert m.calls == 0
    assert m.chat_requests == 3


def test_a_failed_price_fetch_is_asked_again_only_after_the_backoff_cap(monkeypatch):
    clk = SimpleNamespace(now=1_700_000_000.0)
    monkeypatch.setattr(bio.mind, "time", SimpleNamespace(time=lambda: clk.now))

    class NoModels(FakeMind):
        def _request(self, path, body=None, timeout=120):
            if path == "/models":
                self.models_requests += 1
                raise http_error(500)
            return super()._request(path, body, timeout)

    m = NoModels()
    m.think("s", "u")
    assert m.models_requests == 1
    assert (m.priced, m.price) == (None, None), "the question stays open"
    assert (m.calls, m.spent_usd) == (1, 0.0)
    assert _events(m, "call")[-1]["cost_source"] == "none"
    warned = _events(m, "mind")
    assert len(warned) == 1 and warned[0]["msg"].startswith("could not fetch prices from mind.invalid: HTTP 500")

    m.think("s", "u")
    assert m.models_requests == 1, "not asked again inside the cap"
    clk.now += config.MUTAGEN_BACKOFF_MAX
    m.think("s", "u")
    assert m.models_requests == 2
    assert len(_events(m, "mind")) == 1, "the warning is given once per process"
    assert not config.PRICES_FILE.exists()


def test_spent_grows_with_each_call():
    m = FakeMind()
    for _ in range(3):
        m.think("s", "u")
    assert m.calls == 3
    assert m.spent_usd == pytest.approx(0.03)
    assert m.last_usd == pytest.approx(0.01)
    assert (m.prompt_tokens, m.completion_tokens) == (3000, 3000)
    calls = _events(m, "call")
    assert len(calls) == 3
    assert [ev["spent_usd"] for ev in calls] == pytest.approx([0.01, 0.02, 0.03])
    assert [ev["calls"] for ev in calls] == [1, 2, 3]
    for ev in calls:
        assert ev["usd"] == pytest.approx(0.01)
        assert ev["model"] == "test/model"
        assert (ev["prompt_tokens"], ev["completion_tokens"]) == (1000, 1000)
        assert ev["cost_source"] == "table"
        assert ev["latency"] >= 0
        assert "2000 tok" in ev["msg"] and "$0.010" in ev["msg"]


def test_the_call_event_carries_the_role_and_a_role_less_call_is_unattributed():
    """`role` rides on every `call` event so per-role spend can be summed apart. Each caller states
    it; the default is a neutral "unknown", not "mutagen", so a call site that forgets `role=` is
    counted as unattributed and never silently added to the mutagen's spend."""
    m = FakeMind()
    m.think("s", "u", role="naturalist")
    m.think("s", "u")  # no role: the caller forgot to say
    roles = [ev["role"] for ev in _events(m, "call")]
    assert roles == ["naturalist", "unknown"]


def test_endpoint_reported_cost_wins():
    m = FakeMind(cost=0.003)
    m.think("s", "u")
    assert m.spent_usd == pytest.approx(0.003)
    assert m.events[-1]["cost_source"] == "endpoint"

    garbage = FakeMind(cost="garbage")
    garbage.think("s", "u")
    assert garbage.spent_usd == pytest.approx(0.01), "an unreadable figure falls back to the table"
    assert garbage.events[-1]["cost_source"] == "table"

    negative = FakeMind(cost=-1)
    negative.think("s", "u")
    assert negative.spent_usd == 0.0, "an endpoint cannot pay the dish"


def test_unpriced_endpoint_spends_nothing():
    m = FakeMind(models=[{"id": "local"}], budget_usd=0.01)
    m.think("s", "u")
    m.think("s", "u")
    assert m.priced is False
    assert m.price is None
    assert m.spent_usd == 0.0
    assert not m.exhausted
    assert m.models_requests == 1
    free = _events(m, "mind")
    assert len(free) == 1 and "free" in free[0]["msg"]
    assert all(ev["cost_source"] == "none" for ev in _events(m, "call"))

    second = FakeMind(models=[{"id": "local"}])
    second.think("s", "u")
    assert second.models_requests == 0, "an empty cached table means an unpriced endpoint: no refetch"
    assert second.priced is False


def test_priced_endpoint_without_this_model_counts_only_reported_cost():
    m = FakeMind(models=[{"id": "other/model", "pricing": {"prompt": "0.001", "completion": "0.001"}}])
    m.think("s", "u")
    assert m.priced is True
    assert m.price is None
    assert m.spent_usd == 0.0
    assert m.models_requests == 1
    assert any("no price for test/model" in ev["msg"] for ev in _events(m, "mind"))
    m.think("s", "u")
    assert m.models_requests == 1, "the answer is settled for the life of the process"


def test_budget_gates_before_the_request():
    m = FakeMind(budget_usd=0.01)
    m.think("s", "u")
    assert m.exhausted
    with pytest.raises(Exhausted, match=r"budget spent: \$0\.010 / \$0\.01") as info:
        m.think("s", "u")
    assert isinstance(info.value, MindError)
    assert m.chat_requests == 1
    assert m.calls == 1

    nothing = FakeMind(budget_usd=0)
    with pytest.raises(Exhausted):
        nothing.think("s", "u")
    assert nothing.chat_requests == 0

    uncapped = FakeMind(budget_usd=float("inf"), usage=(10**6, 10**6))
    for _ in range(5):
        uncapped.think("s", "u")
    assert uncapped.spent_usd == pytest.approx(50.0)
    assert not uncapped.exhausted

    assert FakeMind(budget_usd=-3).budget_usd == 0.0


def test_http_errors_carry_status_and_retry_after(monkeypatch):
    clk = SimpleNamespace(now=1_700_000_000.0)
    monkeypatch.setattr(bio.mind, "time", SimpleNamespace(time=lambda: clk.now))

    class SlowMind(FakeMind):
        def _request(self, path, body=None, timeout=120):
            clk.now += 0.5
            return super()._request(path, body, timeout)

    m = SlowMind(
        replies=[
            http_error(429, "7"),
            http_error(429, formatdate(clk.now + 1.0 + 90, usegmt=True)),
            http_error(500),
            urllib.error.URLError("connection refused"),
            http.client.IncompleteRead(b""),
            "fine",
        ]
    )
    with pytest.raises(MindError) as e:
        m.think("s", "u")
    assert (e.value.status, e.value.retry_after) == (429, 7.0)
    assert str(e.value).startswith("HTTP 429")
    assert m.last_latency == 0.5
    assert m.last_error == str(e.value)

    with pytest.raises(MindError) as e:
        m.think("s", "u")
    assert e.value.status == 429
    assert e.value.retry_after == pytest.approx(90, abs=1)

    with pytest.raises(MindError) as e:
        m.think("s", "u")
    assert (e.value.status, e.value.retry_after) == (500, None)

    with pytest.raises(MindError) as e:
        m.think("s", "u")
    assert (e.value.status, e.value.retry_after) == (None, None)
    assert str(e.value).startswith("URLError")

    with pytest.raises(MindError) as e:  # a reply cut short: an HTTPException, which is not an OSError
        m.think("s", "u")
    assert (e.value.status, e.value.retry_after) == (None, None)
    assert str(e.value).startswith("IncompleteRead")
    assert m.last_error == str(e.value) and m.last_latency == 0.5

    assert m.think("s", "u") == "fine"
    assert m.last_latency == 0.5
    assert m.last_error is None
    assert m.events[-1]["latency"] == 0.5


def test_odd_reply_is_paid_for_and_then_rejected():
    class OddMind(FakeMind):
        def _request(self, path, body=None, timeout=120):
            d = super()._request(path, body, timeout)
            if path == "/chat/completions":
                d["choices"] = []
            return d

    m = OddMind()
    with pytest.raises(MindError, match="odd reply"):
        m.think("s", "u")
    assert m.calls == 1
    assert m.spent_usd == pytest.approx(0.01)


def test_backoff_schedule():
    assert [backoff(n) for n in range(9)] == [0, 15, 30, 60, 120, 240, 480, 600, 600]
    assert backoff(3, base=1.0, cap=3.0) == 3.0
    # a week of a dead endpoint is past the thousandth consecutive failure: still the cap, never an overflow
    assert backoff(1024) == backoff(1025) == backoff(10_000) == 600.0
    assert backoff(10_000, base=1.0, cap=float("inf")) == 2.0**60


def test_ledger_round_trip():
    m = FakeMind(budget_usd=0.5)
    m.think("s", "u")
    m.think("s", "u")
    led = m.ledger()
    assert led == {
        "model": "test/model",
        "budget_usd": 0.5,
        "spent_usd": pytest.approx(0.02),
        "calls": 2,
        "prompt_tokens": 2000,
        "completion_tokens": 2000,
    }
    json.dumps(led)

    fresh = FakeMind()
    fresh.restore(led)
    assert (fresh.spent_usd, fresh.calls, fresh.prompt_tokens, fresh.completion_tokens) == (
        pytest.approx(0.02),
        2,
        2000,
        2000,
    )
    assert fresh.budget_usd == 0.5
    assert fresh.model == "test/model"

    m.budget_usd = float("inf")
    assert m.ledger()["budget_usd"] is None
    fresh.restore(m.ledger())
    assert fresh.budget_usd == float("inf")

    fresh.budget_usd = 0.75
    fresh.restore({})
    assert fresh.budget_usd == 0.75
    assert fresh.spent_usd == 0.0


def test_reconcile_only_ever_moves_the_ledger_forward():
    m = FakeMind()
    m.restore({"spent_usd": 0.02, "calls": 2})
    m.reconcile({"kind": "call", "spent_usd": 0.01, "calls": 1})
    assert (m.spent_usd, m.calls) == (0.02, 2), "an older event never lowers the ledger"
    m.reconcile({"kind": "call", "spent_usd": 0.05, "calls": 5})
    assert (m.spent_usd, m.calls) == (0.05, 5)
    m.reconcile({"kind": "call", "msg": "no numbers"})
    assert (m.spent_usd, m.calls) == (0.05, 5)


def test_money_is_printed_the_same_everywhere():
    assert fmt_usd(0.0434) == "$0.043"
    assert fmt_budget(0.0434, 2.0) == "$0.043 / $2.00"
    assert fmt_budget(0.01, 0.01) == "$0.010 / $0.01"
    assert fmt_budget(0.0, 0.005) == "$0.000 / $0.005"
    assert fmt_budget(1.5, float("inf")) == "$1.500 / uncapped"
