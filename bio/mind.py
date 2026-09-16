"""The mind: a thin client for any OpenAI-compatible chat endpoint.

Used as a mutagen and as an observer. The dish never waits on it.

Every call is priced and counted against a per-dish budget. The price comes
from the endpoint's own figure when it reports one (`usage.cost`), else from
its price list, fetched once from `/models` after the first reply and cached
in `vessel/prices.json`, else it is zero (a local endpoint). When the budget
is spent, `think` raises `Exhausted` before any request is made.
"""

from __future__ import annotations

import http.client
import json
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from email.utils import parsedate_to_datetime

from . import config


class Dormant(Exception):
    """No key, no model, no mind."""


class MindError(Exception):
    def __init__(self, msg: str, *, status: int | None = None, retry_after: float | None = None):
        super().__init__(msg)
        self.status = status  # HTTP status, when the endpoint answered at all
        self.retry_after = retry_after  # seconds the endpoint asked us to wait, when it said


class Exhausted(MindError):
    """The dish's budget is spent. No request is made."""


def backoff(failures: int, base: float | None = None, cap: float | None = None) -> float:
    """Seconds to wait after the n-th consecutive failure: base, 2·base, 4·base … capped; 0 for none."""
    if failures <= 0:
        return 0.0
    base = config.MUTAGEN_BACKOFF if base is None else base
    cap = config.MUTAGEN_BACKOFF_MAX if cap is None else cap
    # the exponent is clamped: base · 2^60 is past any cap, and a week of consecutive failures
    # must not build a power of two too large to be a float
    return float(min(cap, base * 2.0 ** min(failures - 1, 60)))


def parse_budget(x: float | None) -> float:
    """A budget as the mind keeps it: None is no cap; negatives clamp to nothing at all."""
    if x is None:
        return math.inf
    return max(0.0, float(x))


def fmt_usd(x: float) -> str:
    return f"${x:.3f}"


def fmt_cap(budget: float) -> str:
    if math.isinf(budget):
        return "uncapped"
    if abs(budget - round(budget, 2)) < 1e-9:
        return f"${budget:.2f}"
    return f"${budget:.3f}"


def fmt_budget(spent: float, budget: float) -> str:
    """'$0.043 / $2.00'; '$0.043 / uncapped' when there is no cap."""
    return f"{fmt_usd(spent)} / {fmt_cap(budget)}"


def _retry_after(headers) -> float | None:
    """Seconds from a Retry-After header: an integer, or an HTTP date; None if absent or unreadable."""
    v = headers.get("Retry-After") if headers is not None else None
    if not v:
        return None
    v = str(v).strip()
    try:
        return max(0.0, float(v))
    except ValueError:
        pass
    try:
        return max(0.0, parsedate_to_datetime(v).timestamp() - time.time())
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def _silent(kind: str, msg: str, **data) -> None:
    """Where a mind's events go until a culture installs its log."""


def _int(x) -> int:
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return 0


def _usd(x) -> float:
    try:
        return max(0.0, float(x or 0.0))
    except (TypeError, ValueError):
        return 0.0


class Mind:
    def __init__(self, model: str | None = None, budget_usd: float | None = None):
        self.model = model or config.MODEL
        self.key = config.API_KEY
        self.base = (config.BASE_URL or "").rstrip("/")
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.last_latency = 0.0
        self.last_error: str | None = None
        # the ledger
        self.budget_usd = config.BUDGET_USD if budget_usd is None else parse_budget(budget_usd)
        self.spent_usd = 0.0
        self.last_usd = 0.0
        self.price: dict | None = None  # this model's {"prompt", "completion", "request"}: USD per token / per call
        self.priced: bool | None = None  # True: the endpoint publishes prices; False: none (free); None: not settled
        self.log: Callable[..., None] = _silent  # the culture installs its own; signature log(kind, msg, **data)
        self._lock = threading.Lock()  # guards the counters; never held across a request
        self._price_lock = threading.Lock()  # one price fetch at a time; never held together with _lock
        self._prices_failed_at = -math.inf  # when /models last failed; not asked again for MUTAGEN_BACKOFF_MAX
        self._price_warned = False

    @property
    def awake(self) -> bool:
        # Local endpoints don't need a key.
        return bool(self.key) or "localhost" in self.base or "127.0.0.1" in self.base

    @property
    def exhausted(self) -> bool:
        return self.spent_usd >= self.budget_usd

    @property
    def host(self) -> str:
        return urllib.parse.urlsplit(self.base).netloc or self.base

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.key:
            h["Authorization"] = f"Bearer {self.key}"
        if "openrouter" in self.base:
            h["HTTP-Referer"] = "https://github.com/oddurs/biotic"
            h["X-Title"] = "biotic"
        return h

    def _request(self, path: str, body: dict | None = None, timeout: float = 120) -> dict:
        """The one seam to the network: POST `body` to `path` (GET when there is none), return the JSON."""
        req = urllib.request.Request(
            self.base + path,
            data=None if body is None else json.dumps(body).encode(),
            headers=self._headers(),
            method="GET" if body is None else "POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())

    def think(
        self,
        system: str,
        user: str,
        *,
        temperature: float | None = None,
        max_tokens: int = 1400,
        timeout: float = 120,
        role: str = "mutagen",
    ) -> str:
        """One call. `role` names who is asking — genesis, mutagen, naturalist, probe — and rides on
        the `call` event, so an observer's spend can be told from the mutagen's in the log."""
        if not self.awake:
            raise Dormant("no OPENROUTER_API_KEY (put it in .env)")
        if self.exhausted:
            raise Exhausted(f"budget spent: {fmt_budget(self.spent_usd, self.budget_usd)}")
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": config.MUTAGEN_TEMP if temperature is None else temperature,
            "max_tokens": max_tokens,
        }
        t0 = time.time()
        try:
            data = self._request("/chat/completions", body, timeout)
        except urllib.error.HTTPError as e:
            self.last_latency = time.time() - t0
            self.last_error = f"HTTP {e.code}: {_detail(e)}"
            raise MindError(self.last_error, status=e.code, retry_after=_retry_after(e.headers)) from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, http.client.HTTPException) as e:
            # HTTPException is not an OSError: a reply cut short (IncompleteRead) or a malformed status
            # line would otherwise escape as itself, past the mutagen's backoff and out of genesis
            self.last_latency = time.time() - t0
            self.last_error = f"{type(e).__name__}: {e}"
            raise MindError(self.last_error) from None
        latency = self.last_latency = time.time() - t0
        if not isinstance(data, dict):
            data = {"odd": data}
        usage = data.get("usage") or {}
        if not isinstance(usage, dict):
            usage = {}
        pt, ct = _int(usage.get("prompt_tokens")), _int(usage.get("completion_tokens"))
        # the endpoint answered, so the call is paid for whatever the reply looks like: account for it first
        self._ensure_prices()
        with self._lock:
            self.calls += 1
            self.prompt_tokens += pt
            self.completion_tokens += ct
            usd, source = self._cost(usage, pt, ct)
            self.last_usd = usd
            self.spent_usd += usd
            spent, calls = self.spent_usd, self.calls
        self.log(
            "call",
            f"{self.model.split('/')[-1]} · {pt + ct} tok · {fmt_usd(usd)} · {latency:.1f}s",
            model=self.model,
            prompt_tokens=pt,
            completion_tokens=ct,
            usd=usd,
            spent_usd=spent,
            calls=calls,
            latency=latency,
            cost_source=source,
            role=role,
        )
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            self.last_error = f"odd reply: {json.dumps(data)[:300]}"
            raise MindError(self.last_error) from None
        self.last_error = None
        return text

    # --- the ledger ----------------------------------------------------------
    def _cost(self, usage: dict, pt: int, ct: int) -> tuple[float, str]:
        """Dollars for one call and where the figure came from: endpoint, table, or none."""
        c = usage.get("cost")
        if c is not None:
            try:
                return max(0.0, float(c)), "endpoint"
            except (TypeError, ValueError):
                pass
        if self.price:
            p = self.price
            return pt * p.get("prompt", 0.0) + ct * p.get("completion", 0.0) + p.get("request", 0.0), "table"
        return 0.0, "none"

    def _ensure_prices(self) -> None:
        """Learn this model's price once: from vessel/prices.json, else from the endpoint.

        Called after a successful reply and never before the first request, so a dead
        endpoint is never asked for its price list. A fetch that fails with no cache to
        fall back on leaves the question open for a later reply, but is not asked again
        for MUTAGEN_BACKOFF_MAX seconds; with a cache, the cache stands.
        """
        if self.priced is not None:
            return
        with self._price_lock:
            if self.priced is not None:
                return
            prices = self._read_prices()
            fetched = False
            if prices is None or (prices and self.model not in prices):
                if time.time() - self._prices_failed_at < config.MUTAGEN_BACKOFF_MAX:
                    if prices is None:
                        return  # asked lately and got nothing; not again yet
                else:
                    try:
                        prices = self._fetch_prices()
                        fetched = True
                    except Exception as e:  # noqa: BLE001 — the price list is a convenience; the call already happened
                        self._prices_failed_at = time.time()
                        if not self._price_warned:
                            self._price_warned = True
                            why = (
                                f"HTTP {e.code}"
                                if isinstance(e, urllib.error.HTTPError)
                                else f"{type(e).__name__}: {e}"
                            )
                            self.log(
                                "mind",
                                f"could not fetch prices from {self.host}: {why} — "
                                "spend is counted only when the endpoint reports it",
                            )
                        if prices is None:
                            return
            self.price = prices.get(self.model) if prices else None
            self.priced = bool(prices)
            origin = (
                f"price list cached from {self.host}" if fetched else f"price list read from {config.PRICES_FILE.name}"
            )
            if self.price:
                p, c = self.price.get("prompt", 0.0) * 1e6, self.price.get("completion", 0.0) * 1e6
                self.log("mind", f"{origin} — {self.model} at ${p:.2f}/${c:.2f} per M tokens")
            elif self.priced:
                self.log(
                    "mind",
                    f"no price for {self.model} at {self.host} — spend is counted only when the endpoint reports it",
                )
            else:
                self.log("mind", f"{self.host} publishes no prices — the mind is free here; spend stays at $0.000")

    def _read_prices(self) -> dict | None:
        """The cached table for this endpoint, or None when there is none worth using."""
        try:
            if not config.PRICES_FILE.exists():
                return None
            d = json.loads(config.PRICES_FILE.read_text())
            if d.get("base") != self.base or not isinstance(d.get("prices"), dict):
                return None
            return d["prices"]
        except (OSError, ValueError, AttributeError):
            return None

    def _fetch_prices(self) -> dict:
        """GET /models, keep {id: {prompt, completion, request}} in USD per token / per call, write the cache."""
        data = self._request("/models", timeout=15)
        rows = data.get("data") if isinstance(data, dict) else data
        prices: dict[str, dict[str, float]] = {}
        for row in rows or []:
            if not isinstance(row, dict) or not row.get("id") or not isinstance(row.get("pricing"), dict):
                continue
            pr = row["pricing"]
            try:
                prices[row["id"]] = {k: max(0.0, float(pr.get(k) or 0)) for k in ("prompt", "completion", "request")}
            except (TypeError, ValueError):
                continue
        config.PRICES_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = config.PRICES_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"fetched_at": time.time(), "base": self.base, "prices": prices}))
        tmp.replace(config.PRICES_FILE)
        return prices

    def ledger(self) -> dict:
        """What the dish remembers about its spend. `budget_usd` is null when there is no cap."""
        return {
            "model": self.model,
            "budget_usd": None if math.isinf(self.budget_usd) else self.budget_usd,
            "spent_usd": self.spent_usd,
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
        }

    def restore(self, d: dict) -> None:
        """Take up a ledger saved with a dish. The model is never restored: it is the observer's choice."""
        self.spent_usd = _usd(d.get("spent_usd"))
        self.calls = _int(d.get("calls"))
        self.prompt_tokens = _int(d.get("prompt_tokens"))
        self.completion_tokens = _int(d.get("completion_tokens"))
        if "budget_usd" in d:
            self.budget_usd = parse_budget(d["budget_usd"])

    def reconcile(self, ev: dict) -> None:
        """Take the running totals from the last `call` event when they are ahead of the ledger:
        a process killed between saves left its calls in the log but not in dish.json."""
        self.spent_usd = max(self.spent_usd, _usd(ev.get("spent_usd")))
        self.calls = max(self.calls, _int(ev.get("calls")))

    def models(self) -> list[dict]:
        data = self._request("/models", timeout=30)
        if isinstance(data, dict):
            return data.get("data") or []
        return data if isinstance(data, list) else []


def _detail(e: urllib.error.HTTPError) -> str:
    try:
        return e.read().decode(errors="replace")[:400]
    except (AttributeError, OSError, ValueError):
        return str(e.reason)[:400]
