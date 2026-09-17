"""The mutagen: what asks the mind for daughter genomes, on one of two clocks.

On the wall clock (`biotic live`) it is a background thread. The dish never blocks
on it: divisions that roll a mutation take a prepared genome from the pool if one
exists, otherwise they queue a request and divide faithfully, and the thread calls
the mind at most once every `MUTAGEN_INTERVAL` seconds. Throughput of novelty is
bounded by the mind, not the dish, and a division's outcome depends on when the
reply landed.

On the tick clock (`biotic run`) there is no thread, no pool and no queue. The dish
calls the mind itself, from the division that rolled the mutation, at most once every
`MUTAGEN_EVERY_TICKS` ticks, and waits for the reply; the daughter is born in that
division. The supply of variants is then a function of ticks and budget, and with a
deterministic mind the whole trajectory reproduces on any machine at any `--tick`.
docs/experiments.md says when to use which.

A failing mind is retried on a doubling schedule (15 s, 30 s, … 10 min on the wall
clock; 2, 4, … 50 intervals in ticks on the tick clock), reset by the next success;
a `Retry-After` from the endpoint stretches it, and on the tick clock is a floor on
the wall clock during which no attempt is made. While the schedule says wait, no
strain is picked and requests stay queued. A spent budget puts the mutagen in the
`exhausted` state, logged once, and the culture grows on without variation.
"""

from __future__ import annotations

import contextlib
import math
import threading
import time
from collections import deque
from collections.abc import Callable

from . import config, prompts
from .membrane import admit_isolated
from .mind import Dormant, Exhausted, Mind, MindError, backoff, fmt_budget


def _split(key) -> tuple[str, str | None]:
    """A pool/request key as (recipient, donor): a bare strain id is an ordinary mutation,
    (recipient, donor) tuple is a splice (docs/hgt.md)."""
    return key if isinstance(key, tuple) else (key, None)


class Mutagen(threading.Thread):
    def __init__(self, mind: Mind, seed: str, log: Callable[..., None]):
        super().__init__(daemon=True, name="mutagen")
        self.mind = mind
        self.seed = seed
        self.log = log
        self.clock: Callable[[], float] = time.time  # the wall clock; clock_ticks() puts the dish clock here
        self.every_ticks: int | None = None  # None: the wall clock; an int: the tick clock, ticks between calls
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stop = threading.Event()
        # keys are a bare strain (an ordinary mutation) or a (recipient, donor) tuple (a splice)
        self.requests: dict[str | tuple[str, str], float] = {}  # key -> time requested
        self.pool: dict[str | tuple[str, str], deque] = {}  # key -> ready daughters
        self.splice_at: dict[tuple[str, str], int] = {}  # splice key -> the tick it was last requested/prepared
        self.rejections: deque[str] = deque(maxlen=6)
        self.context: dict = {}  # snapshot of the dish, set by the culture
        self.genomes: dict[str, tuple[str, str]] = {}  # strain -> (name, source)
        self.state = "dormant" if not mind.awake else ("exhausted" if mind.exhausted else "idle")
        self.attempted = 0  # calls made, whatever the outcome; Dormant and Exhausted are raised before any request
        self.viable = 0  # daughters that passed the membrane: into the pool (wall) or born at once (tick)
        self.nonviable = 0
        self.boost = 1.0
        self.boost_until = 0
        self.last_call = 0.0
        self.failures = 0  # consecutive failed calls
        self.retry_at = 0.0  # clock time before which no strain is picked
        self.retry_wall_at = 0.0  # tick clock only: a Retry-After floor on time.time(); 0.0 when none

    # --- the clock ------------------------------------------------------------
    def clock_ticks(
        self, every: int, clock: Callable[[], float], *, last_call: float = -math.inf, retry_at: float = 0.0
    ) -> None:
        """Run on the dish clock: `clock` returns dish.tick; the interval and the backoff are counted
        in ticks; the thread makes no calls (run() returns at once); every call is mutate_now() from
        the dish thread. `last_call` and `retry_at` are the schedule a resumed dish remembers; the
        defaults open the slot at once. Call once, before run()."""
        self.every_ticks = max(1, int(every))
        self.clock = clock
        self.last_call = last_call
        self.retry_at = retry_at

    @property
    def ticked(self) -> bool:
        return self.every_ticks is not None

    def interval(self) -> float:
        """The least time between calls, in the clock's unit; a running boost divides it."""
        return (self.every_ticks if self.ticked else config.MUTAGEN_INTERVAL) / max(self.boost, 1.0)

    def backoff_for(self, failures: int) -> float:
        """The wait after the n-th consecutive failure, in the clock's unit."""
        if self.ticked:
            e = self.every_ticks
            return backoff(
                failures, base=config.MUTAGEN_BACKOFF_INTERVALS * e, cap=config.MUTAGEN_BACKOFF_INTERVALS_MAX * e
            )
        return backoff(failures)

    def wait_text(self, wait: float) -> str:
        return f"{int(wait)} ticks" if self.ticked else fmt_wait(wait)

    # --- called from the dish thread ---------------------------------------
    def request(self, strain: str, *, donor: str | None = None) -> None:
        key = strain if donor is None else (strain, donor)
        with self.lock:
            self.requests.setdefault(key, self.clock())
            if donor is not None:
                self.splice_at.setdefault(key, self.context.get("tick", 0))
        self.wake.set()

    def take(self, strain: str, *, donor: str | None = None):
        with self.lock:
            self._expire()
            key = strain if donor is None else (strain, donor)
            q = self.pool.get(key)
            if q:
                return q.popleft()
        return None

    def mutate_now(self, strain: str, *, donor: str | None = None) -> tuple[str, str, str] | None:
        """Tick clock, dish thread. One synchronous call for `strain` if the slot is open — the mind
        awake and not exhausted, no backoff or Retry-After pending, at least interval() ticks since
        the last call. Returns the admitted daughter (name, note, source) to be born in this
        division, or None: the division is faithful. `donor`, when set, is a neighbour's strain to
        splice a gene from — `_ask` builds the HGT prompt instead of the mutation prompt (docs/hgt.md).
        Main thread only, outside a Budget block (Dish._apply calls on_divide after the block closes).
        Every fault
        after the gate is a `mutagen fault` event and None, never an exception into the dish."""
        if not self._open(self.clock()):
            return None
        try:
            got = self._ask(strain, donor)
            return None if got is None else self._judge(strain, *got)
        except Exception as e:  # noqa: BLE001 — a fault in the apparatus must not lyse the dividing cell
            self._fail(f"mutagen fault: {type(e).__name__}: {e}")
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
            # drop every key where `strain` is the recipient (the bare key too, via _split) or the
            # donor, so a strain that goes extinct leaves no orphan splice pending or prepared
            for store in (self.requests, self.pool, self.splice_at):
                for key in list(store):
                    rec, donor = _split(key)
                    if rec == strain or donor == strain:
                        del store[key]

    def reset(self, genomes: dict[str, tuple[str, str]]) -> None:
        """The dish was replaced: these are the living genomes now. Prepared daughters and
        pending requests belonged to the old dish and are dropped. The thread may be between
        _pick and _mutate, waiting out the interval with a strain that is no longer here;
        _mutate looks the strain up again and does nothing when it is gone. A call to the mind
        that is already in flight may still append one daughter afterwards; _pick only serves
        strains in `genomes`, so an orphan entry in the pool is inert."""
        with self.lock:
            self.genomes = dict(genomes)
            self.pool.clear()
            self.requests.clear()
            self.splice_at.clear()

    # --- the thread ---------------------------------------------------------
    def run(self) -> None:
        if not self.mind.awake:
            self.log("mind", "mutagen dormant — no API key; the culture will grow but never vary")
            return
        if self.ticked:
            return  # the dish makes the calls itself, from its own thread
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
        gap = self.interval() - (self.clock() - self.last_call)
        if gap > 0 and self.stop.wait(gap):
            return True
        try:
            self._mutate(strain)
        except Exception as e:  # noqa: BLE001 — the thread must outlive any single fault
            self._fail(f"mutagen fault: {type(e).__name__}: {e}")
        return False

    def _open(self, now: float) -> bool:
        """The gate a blocking call passes through: the same conditions _cycle checks in turn."""
        if not self.mind.awake:
            self.state = "dormant"
            return False
        if self.mind.exhausted:
            self._exhaust()
            return False
        if self.state == "exhausted":  # the budget was raised since
            self.state = "idle"
        if now < self.retry_at:
            return False
        if self.retry_wall_at and time.time() < self.retry_wall_at:
            return False  # the endpoint named a wait; the one wall-clock input on the tick path
        return now - self.last_call >= self.interval()

    def _expire(self) -> None:
        """Drop prepared or pending splices whose (recipient, donor) pair has not touched again
        within HGT_EXPIRY_TICKS — real conjugation needs contact (docs/hgt.md). Wall clock only,
        and approximate: `context["tick"]` refreshes about every three ticks, so the cutoff is
        good to within a few ticks. Must be called with self.lock held (take and _pick do)."""
        if not self.splice_at:
            return
        now = self.context.get("tick", 0)
        for key in list(self.splice_at):
            if now - self.splice_at.get(key, now) > config.HGT_EXPIRY_TICKS:
                self.requests.pop(key, None)
                self.pool.pop(key, None)
                del self.splice_at[key]

    def _pick(self):
        with self.lock:
            self._expire()
            live = []
            for key in list(self.requests):
                rec, donor = _split(key)
                if rec in self.genomes and (donor is None or donor in self.genomes):
                    live.append(key)
                else:  # the recipient or the donor went extinct while the request waited
                    del self.requests[key]
                    self.splice_at.pop(key, None)
            if live:
                key = min(live, key=self.requests.get)  # oldest request
                del self.requests[key]
                return key
            # spontaneous mutation: keep the pool warm for the dominant strain (never a splice)
            census = self.context.get("census") or {}
            if census and self.clock() - self.last_call > config.MUTAGEN_INTERVAL * 5:
                top = max(census, key=census.get)
                if top in self.genomes and len(self.pool.get(top, ())) < 2:
                    return top
        return None

    def _mutate(self, key) -> None:
        """Wall clock, the thread: one call for `key` (a bare strain, or a (recipient, donor)
        splice); an admitted daughter goes into the pool under the same key."""
        rec, donor = _split(key)
        got = self._ask(rec, donor)
        if got is None:
            return
        daughter = self._judge(rec, *got)
        if daughter is None:
            return
        with self.lock:
            self.pool.setdefault(key, deque(maxlen=3)).append(daughter)
            if donor is not None:
                self.splice_at[key] = self.context.get("tick", 0)  # the pair touched: reset the clock
        name, note = got[0], daughter[1]
        if donor is not None:
            msg = f"a splice of {rec} × {donor} is ready"
        else:
            msg = f"a variant of {name} is ready"
        self.log("prepared", f"{msg} — “{note}”" if note else msg)

    def _ask(self, strain: str, donor: str | None = None) -> tuple[str, str, str, str, str] | None:
        """One call to the mind for `strain`: the prompt, the request, the outcome. Returns the
        recipient's (name, source) and the reply's (name, note, source) as one tuple, what _judge
        takes, or None when nothing came of it — the strain is gone, the mind is dormant or
        exhausted, or the call failed and the backoff is set. When `donor` is set and its genome is
        known, the splice prompt (prompts.hgt_*) is used instead of the mutation prompt; when the
        donor left `genomes` between request and preparation, this falls through to the ordinary
        mutation prompt (docs/hgt.md). Either way name/source are the recipient's, so _judge's
        silent-identical check compares the reply against the recipient."""
        with self.lock:
            got = self.genomes.get(strain)
            dg = self.genomes.get(donor) if donor is not None else None
            ctx = dict(self.context)
            rejections = list(self.rejections)
        if got is None:
            return None  # went extinct while we waited
        name, source = got
        census = ctx.get("census") or {}
        pop = max(1, sum(census.values()))
        if dg is not None:
            dname, dsource = dg
            user = prompts.hgt_user(
                seed=self.seed,
                recipient_source=source,
                recipient_name=name,
                donor_source=dsource,
                donor_name=dname,
                tick=ctx.get("tick", 0),
                phase=ctx.get("phase", "?"),
                population=pop,
                share=census.get(strain, 0) / pop,
                nutrient=ctx.get("nutrient", 0.0),
                strains=len(census),
                whispers=ctx.get("whispers", []),
                rejections=rejections,
            )
            system = prompts.hgt_system(ctx.get("features"))  # the splice prompt, plus any feature clauses
        else:
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
            system = prompts.mutagen_system(ctx.get("features"))  # documents whatever features the dish has on
        self.state = "thinking"
        self.last_call = self.clock()
        try:
            reply = self.mind.think(system, user, role="mutagen")
        except Dormant:
            self.state = "dormant"
            return None
        except Exhausted:
            self._exhaust()
            return None
        except MindError as e:
            self.attempted += 1
            self._fail(f"mutagen call failed: {e}", status=e.status, retry_after=e.retry_after)
            return None
        self.attempted += 1
        self.failures = 0
        self.retry_at = 0.0
        self.retry_wall_at = 0.0
        if self.mind.exhausted:
            self._exhaust()  # this call was paid for; its daughter still counts
        else:
            self.state = "idle"
        dname, note, src = prompts.parse_reply(reply)
        return name, source, dname, note, src

    def _judge(
        self, strain: str, name: str, source: str, dname: str, note: str, src: str
    ) -> tuple[str, str, str] | None:
        """The membrane's verdict on a reply to a mutation of `name`. Returns the daughter
        (name, note, source) when it may live; None, counted nonviable and logged, when it is
        silent or refused."""
        if src.strip() == source.strip():
            self.nonviable += 1
            self.log("nonviable", f"mutation of {name} was silent (identical genome)")
            return None
        verdict = admit_isolated(src)
        if not verdict:
            self.nonviable += 1
            reason = verdict.reasons[0]
            with self.lock:
                self.rejections.append(reason)
            self.log("nonviable", f"mutation of {name} nonviable — {reason}")
            return None
        self.viable += 1
        return dname, note, src

    def _fail(self, msg: str, *, status: int | None = None, retry_after: float | None = None) -> None:
        """Record a failed call and schedule the next attempt."""
        self.failures += 1
        wait = self.backoff_for(self.failures)
        floor = ""
        if retry_after:
            asked = min(retry_after, config.RETRY_AFTER_MAX)
            if self.ticked:
                self.retry_wall_at = time.time() + asked
                floor = f" (Retry-After {fmt_wait(asked)})"
            else:
                wait = max(wait, asked)
        self.retry_at = self.clock() + wait
        self.state = "error"
        self.log(
            "mind",
            f"{msg} — next attempt in {self.wait_text(wait)}{floor}",
            status=status,
            retry_in=wait,
            unit="ticks" if self.ticked else "s",
            failures=self.failures,
            latency=self.mind.last_latency,
        )

    def _last_resort(self, e: BaseException) -> None:
        """A fault that escaped `_cycle`'s own handling — one in `_fail` or `_exhaust` themselves —
        is backed off by the cap and said, instead of ending the thread with a traceback on a
        stderr the eyepiece has taken over. When the log is what is broken, it goes unsaid."""
        self.failures += 1
        wait = self.backoff_for(10**6)  # the cap, in the clock's unit
        self.retry_at = self.clock() + wait
        self.state = "error"
        with contextlib.suppress(Exception):  # nowhere left to say it
            self.log(
                "mind",
                f"mutagen fault: {type(e).__name__}: {e} — next attempt in {self.wait_text(wait)}",
                retry_in=wait,
                unit="ticks" if self.ticked else "s",
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
