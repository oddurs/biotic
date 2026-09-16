"""The mutagen: a background thread that asks the mind for daughter genomes.

The dish never blocks on it. Divisions that roll a mutation take a prepared
genome from the pool if one exists, otherwise they queue a request and
divide faithfully. Throughput of novelty is bounded by the mind, not the dish.

A failing mind is retried on a doubling schedule (15 s, 30 s, … 10 min), reset
by the next success; a `Retry-After` from the endpoint stretches it. While the
schedule says wait, no strain is picked and requests stay queued. A spent
budget puts the mutagen in the `exhausted` state, logged once, and the culture
grows on without variation.
"""

from __future__ import annotations

import contextlib
import threading
import time
from collections import deque
from collections.abc import Callable

from . import config, prompts
from .membrane import admit_isolated
from .mind import Dormant, Exhausted, Mind, MindError, backoff, fmt_budget


class Mutagen(threading.Thread):
    def __init__(self, mind: Mind, seed: str, log: Callable[..., None]):
        super().__init__(daemon=True, name="mutagen")
        self.mind = mind
        self.seed = seed
        self.log = log
        self.clock: Callable[[], float] = time.time  # the wall clock; tests, and later a tick clock, replace it
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.requests: dict[str, float] = {}  # strain -> time requested
        self.pool: dict[str, deque] = {}  # strain -> ready daughters
        self.rejections: deque[str] = deque(maxlen=6)
        self.context: dict = {}  # snapshot of the dish, set by the culture
        self.genomes: dict[str, tuple[str, str]] = {}  # strain -> (name, source)
        self.state = "dormant" if not mind.awake else ("exhausted" if mind.exhausted else "idle")
        self.produced = 0
        self.nonviable = 0
        self.boost = 1.0
        self.boost_until = 0
        self.last_call = 0.0
        self.failures = 0  # consecutive failed calls
        self.retry_at = 0.0  # clock time before which no strain is picked

    # --- called from the dish thread ---------------------------------------
    def request(self, strain: str) -> None:
        with self.lock:
            self.requests.setdefault(strain, self.clock())
        self.wake.set()

    def take(self, strain: str):
        with self.lock:
            q = self.pool.get(strain)
            if q:
                return q.popleft()
        return None

    def ready(self) -> int:
        with self.lock:
            return sum(len(q) for q in self.pool.values())

    def pending(self) -> int:
        with self.lock:
            return len(self.requests)

    def know(self, strain: str, name: str, source: str) -> None:
        with self.lock:
            self.genomes[strain] = (name, source)

    def forget(self, strain: str) -> None:
        with self.lock:
            self.genomes.pop(strain, None)
            self.pool.pop(strain, None)
            self.requests.pop(strain, None)

    # --- the thread ---------------------------------------------------------
    def run(self) -> None:
        if not self.mind.awake:
            self.log("mind", "mutagen dormant — no API key; the culture will grow but never vary")
            return
        while not self.stop.is_set():
            self.wake.wait(timeout=2.0)
            self.wake.clear()
            if self._turn():
                return

    def _turn(self) -> bool:
        """One turn of the loop, and the thread's last line of defence. Returns True when told to stop."""
        try:
            return self._cycle()
        except Exception as e:  # noqa: BLE001 — a fault in the fault handling itself must not end the thread
            self._last_resort(e)
            return False

    def _cycle(self) -> bool:
        """One pass of the loop. Returns True when told to stop."""
        if not self.mind.awake:
            self.state = "dormant"  # a keyless mind with a zero budget is dormant, not exhausted
            return False
        if self.mind.exhausted:
            self._exhaust()
            return False
        if self.state == "exhausted":  # the budget was raised since
            self.state = "idle"
        if self.clock() < self.retry_at:
            return False  # backing off: nothing is picked; run()'s two-second wake bounds the poll
        strain = self._pick()
        if strain is None:
            return False
        # respect the minimum interval between calls
        gap = config.MUTAGEN_INTERVAL / max(self.boost, 1.0) - (self.clock() - self.last_call)
        if gap > 0 and self.stop.wait(gap):
            return True
        try:
            self._mutate(strain)
        except Exception as e:  # noqa: BLE001 — the thread must outlive any single fault
            self._fail(f"mutagen fault: {type(e).__name__}: {e}")
        return False

    def _pick(self):
        with self.lock:
            live = [s for s in self.requests if s in self.genomes]
            for s in list(self.requests):
                if s not in self.genomes:
                    del self.requests[s]
            if live:
                strain = min(live, key=self.requests.get)  # oldest request
                del self.requests[strain]
                return strain
            # spontaneous mutation: keep the pool warm for the dominant strain
            census = self.context.get("census") or {}
            if census and self.clock() - self.last_call > config.MUTAGEN_INTERVAL * 5:
                top = max(census, key=census.get)
                if top in self.genomes and len(self.pool.get(top, ())) < 2:
                    return top
        return None

    def _mutate(self, strain: str) -> None:
        with self.lock:
            got = self.genomes.get(strain)
            ctx = dict(self.context)
            rejections = list(self.rejections)
        if got is None:
            return  # went extinct while we waited
        name, source = got
        census = ctx.get("census") or {}
        pop = max(1, sum(census.values()))
        user = prompts.mutagen_user(
            seed=self.seed,
            source=source,
            strain_name=name,
            tick=ctx.get("tick", 0),
            phase=ctx.get("phase", "?"),
            population=pop,
            share=census.get(strain, 0) / pop,
            nutrient=ctx.get("nutrient", 0.0),
            strains=len(census),
            whispers=ctx.get("whispers", []),
            rejections=rejections,
        )
        self.state = "thinking"
        self.last_call = self.clock()
        try:
            reply = self.mind.think(prompts.MUTAGEN_SYSTEM, user)
        except Dormant:
            self.state = "dormant"
            return
        except Exhausted:
            self._exhaust()
            return
        except MindError as e:
            self._fail(f"mutagen call failed: {e}", status=e.status, retry_after=e.retry_after)
            return
        self.failures = 0
        self.retry_at = 0.0
        if self.mind.exhausted:
            self._exhaust()  # this call was paid for; its daughter still counts
        else:
            self.state = "idle"
        dname, note, src = prompts.parse_reply(reply)
        if src.strip() == source.strip():
            self.nonviable += 1
            self.log("nonviable", f"mutation of {name} was silent (identical genome)")
            return
        verdict = admit_isolated(src)
        if not verdict:
            self.nonviable += 1
            reason = verdict.reasons[0]
            with self.lock:
                self.rejections.append(reason)
            self.log("nonviable", f"mutation of {name} nonviable — {reason}")
            return
        with self.lock:
            self.pool.setdefault(strain, deque(maxlen=3)).append((dname, note, src))
        self.produced += 1
        self.log("prepared", f"a variant of {name} is ready — “{note}”" if note else f"a variant of {name} is ready")

    def _fail(self, msg: str, *, status: int | None = None, retry_after: float | None = None) -> None:
        """Record a failed call and schedule the next attempt."""
        self.failures += 1
        wait = backoff(self.failures)
        if retry_after:
            wait = max(wait, min(retry_after, config.RETRY_AFTER_MAX))
        self.retry_at = self.clock() + wait
        self.state = "error"
        self.log(
            "mind",
            f"{msg} — next attempt in {fmt_wait(wait)}",
            status=status,
            retry_in=wait,
            failures=self.failures,
            latency=self.mind.last_latency,
        )

    def _last_resort(self, e: BaseException) -> None:
        """A fault that escaped `_cycle`'s own handling — one in `_fail` or `_exhaust` themselves —
        is backed off by the cap and said, instead of ending the thread with a traceback on a
        stderr the eyepiece has taken over. When the log is what is broken, it goes unsaid."""
        self.failures += 1
        self.retry_at = self.clock() + config.MUTAGEN_BACKOFF_MAX
        self.state = "error"
        with contextlib.suppress(Exception):  # nowhere left to say it
            self.log(
                "mind",
                f"mutagen fault: {type(e).__name__}: {e} — next attempt in {fmt_wait(config.MUTAGEN_BACKOFF_MAX)}",
                retry_in=config.MUTAGEN_BACKOFF_MAX,
                failures=self.failures,
            )

    def _exhaust(self) -> None:
        if self.state == "exhausted":
            return
        self.state = "exhausted"
        spent, budget = self.mind.spent_usd, self.mind.budget_usd
        self.log("mind", exhausted_msg(spent, budget), spent_usd=spent, budget_usd=budget)

    def close(self) -> None:
        self.stop.set()
        self.wake.set()


def exhausted_msg(spent: float, budget: float, why: str | None = None) -> str:
    """The one exhaustion message, wherever it is said from: 'mutagen exhausted at $2.003 / $2.00 —
    the culture grows on without variation', with the reason before the consequence when the
    budget did not run out in the ordinary way."""
    tail = "the culture grows on without variation"
    return f"mutagen exhausted at {fmt_budget(spent, budget)} — " + (f"{why}; {tail}" if why else tail)


def fmt_wait(seconds: float) -> str:
    """A wait as a person reads it: '15s', '2m00s', '1h00m'."""
    s = int(round(seconds))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"
