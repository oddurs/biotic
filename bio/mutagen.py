"""The mutagen: a background thread that asks the mind for daughter genomes.

The dish never blocks on it. Divisions that roll a mutation take a prepared
genome from the pool if one exists, otherwise they queue a request and
divide faithfully. Throughput of novelty is bounded by the mind, not the dish.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable

from . import config, prompts
from .membrane import admit_isolated
from .mind import Dormant, Mind, MindError


class Mutagen(threading.Thread):
    def __init__(self, mind: Mind, seed: str, log: Callable[..., None]):
        super().__init__(daemon=True, name="mutagen")
        self.mind = mind
        self.seed = seed
        self.log = log
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.requests: dict[str, float] = {}  # strain -> time requested
        self.pool: dict[str, deque] = {}  # strain -> ready daughters
        self.rejections: deque[str] = deque(maxlen=6)
        self.context: dict = {}  # snapshot of the dish, set by the culture
        self.genomes: dict[str, tuple[str, str]] = {}  # strain -> (name, source)
        self.state = "dormant" if not mind.awake else "idle"
        self.produced = 0
        self.nonviable = 0
        self.boost = 1.0
        self.boost_until = 0
        self.last_call = 0.0

    # --- called from the dish thread ---------------------------------------
    def request(self, strain: str) -> None:
        with self.lock:
            self.requests.setdefault(strain, time.time())
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
            strain = self._pick()
            if strain is None:
                continue
            # respect the minimum interval between calls
            gap = config.MUTAGEN_INTERVAL / max(self.boost, 1.0) - (time.time() - self.last_call)
            if gap > 0 and self.stop.wait(gap):
                return
            self._mutate(strain)

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
            if census and time.time() - self.last_call > config.MUTAGEN_INTERVAL * 5:
                top = max(census, key=census.get)
                if top in self.genomes and len(self.pool.get(top, ())) < 2:
                    return top
        return None

    def _mutate(self, strain: str) -> None:
        with self.lock:
            name, source = self.genomes[strain]
            ctx = dict(self.context)
            rejections = list(self.rejections)
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
        self.last_call = time.time()
        try:
            reply = self.mind.think(prompts.MUTAGEN_SYSTEM, user)
        except Dormant:
            self.state = "dormant"
            return
        except MindError as e:
            self.state = "error"
            self.log("mind", f"mutagen call failed: {e}")
            self.stop.wait(15)
            return
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

    def close(self) -> None:
        self.stop.set()
        self.wake.set()
