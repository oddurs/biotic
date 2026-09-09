"""The culture: dish + strains + mutagen + the observer's interventions.

This is the thing you run. It owns the vessel/ directory.
"""

from __future__ import annotations

import json
import random
import shutil
import threading
import time
from collections import deque

from . import config, curve, prompts
from .dish import Cell, Dish
from .membrane import admit_isolated
from .mind import Dormant, Mind, MindError
from .mutagen import Mutagen
from .strains import Registry

FALLBACK_GENESIS = """\
def live(me):
    free = [d for d in range(8) if not me.crowd[d]]
    if me.energy > 1.0 and free:
        return "divide"
    if me.here > 0.04:
        return "eat"
    if free:
        best = max(free, key=lambda d: me.around[d])
        if me.around[best] > me.here + 0.02:
            return ("move", best)
    return "rest"
"""


class Culture:
    def __init__(self, seed: str, dish: Dish, registry: Registry, mind: Mind):
        self.seed = seed
        self.dish = dish
        self.registry = registry
        self.mind = mind
        self.events: deque[dict] = deque(maxlen=200)
        self.rng = random.Random(f"{seed}::culture")
        self.started = time.time()
        self.last_phase = None
        self._candidate = None
        self._candidate_for = 0
        self.mutation_rate = config.MUTATION_RATE
        self.lock = threading.Lock()
        self._curve_fields: list[str] | None = None  # header of curve.csv, reconciled on the first row
        self._curve_broken = False  # the last row could not be written; said once, retried every row
        self.mutagen = Mutagen(mind, seed, self.log)
        for sid, s in registry.strains.items():
            if sid in dish.genomes:
                self.mutagen.know(sid, s.name, s.source)
        dish.on_divide = self._on_divide
        config.INBOX.mkdir(parents=True, exist_ok=True)
        self._load_recent_events()

    # --- creation / persistence --------------------------------------------
    @classmethod
    def germinate(cls, seed: str, mind: Mind, fresh: bool = False) -> Culture:
        if config.DISH_FILE.exists() and not fresh:
            raise FileExistsError("a culture already exists in vessel/ — `biotic sterilize` first, or use --fresh")
        sterilize()
        config.VESSEL.mkdir(exist_ok=True)
        config.SEED_FILE.write_text(seed.strip() + "\n")
        w, h = _fit_dish()
        dish = Dish(seed, w, h)
        reg = Registry(seed)
        cult = cls(seed, dish, reg, mind)
        name, note, src = cult._genesis()
        s = reg.new(src, None, 0, name, note)
        dish.register(s.id, src)
        n = dish.inoculate(s.id)
        cult.mutagen.know(s.id, s.name, s.source)
        config.GENESIS.write_text(src)
        cult.log(
            "genesis", f"inoculated {n} cells of {s.name} — “{note}”" if note else f"inoculated {n} cells of {s.name}"
        )
        cult.save()
        return cult

    def _genesis(self) -> tuple[str, str, str]:
        default = ("founder", "eats where it stands, divides when full, drifts uphill", FALLBACK_GENESIS)
        if not self.mind.awake:
            self.log("mind", "no mind available — founding cell is the built-in default")
            return default
        failures: list[str] = []
        for attempt in range(4):
            try:
                reply = self.mind.think(
                    prompts.GENESIS_SYSTEM, prompts.genesis_user(self.seed, failures), temperature=0.9
                )
            except (Dormant, MindError) as e:
                self.log("mind", f"genesis call failed ({e})")
                continue
            name, note, src = prompts.parse_reply(reply)
            v = admit_isolated(src)
            if not v:
                failures.append(f"rejected by the membrane: {v.reasons[0]}")
                self.log("nonviable", f"founding cell attempt {attempt + 1} nonviable — {v.reasons[0]}")
                continue
            peak, final, ticks = trial(self.seed, src)
            if peak >= 3 * config.INOCULUM and final > 0:
                return name or "founder", note, src
            failures.append(
                f"peak population {peak} from {config.INOCULUM} cells over {ticks} ticks, {final} alive at the end"
                + (" — it never divided" if peak <= config.INOCULUM else "")
            )
            self.log(
                "nonviable",
                f"founding cell attempt {attempt + 1} ({name}) did not take in the trial dish — {failures[-1]}",
            )
        self.log("mind", "mind could not write a founder that grows; using the built-in default")
        return default

    @classmethod
    def load(cls, mind: Mind | None = None) -> Culture:
        if not config.DISH_FILE.exists():
            raise FileNotFoundError('nothing in the dish — `biotic seed "<word>"` first')
        seed = config.SEED_FILE.read_text().strip()
        dish = Dish.from_dict(json.loads(config.DISH_FILE.read_text()))
        reg = Registry.load(seed)
        return cls(seed, dish, reg, mind or Mind())

    def save(self) -> None:
        with self.lock:
            tmp = config.DISH_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.dish.to_dict()))
            tmp.replace(config.DISH_FILE)
            self.registry.save()

    # --- events -------------------------------------------------------------
    def log(self, kind: str, msg: str, **data) -> None:
        ev = {"t": time.time(), "tick": self.dish.tick, "kind": kind, "msg": msg, **data}
        self.events.append(ev)
        with open(config.EVENTS, "a") as f:
            f.write(json.dumps(ev) + "\n")

    def _load_recent_events(self) -> None:
        if not config.EVENTS.exists():
            return
        lines = config.EVENTS.read_text().splitlines()[-60:]
        for line in lines:
            try:
                self.events.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    # --- mutation hook ------------------------------------------------------
    def _on_divide(self, cell: Cell):
        rate = self.mutation_rate * (self.mutagen.boost if self.dish.tick < self.mutagen.boost_until else 1.0)
        if self.rng.random() >= rate:
            return None
        got = self.mutagen.take(cell.strain)
        if not got:
            self.mutagen.request(cell.strain)
            return None
        name, note, src = got
        s = self.registry.new(src, cell.strain, self.dish.tick, name, note)
        self.mutagen.know(s.id, s.name, s.source)
        parent = self.registry.strains.get(cell.strain)
        pname = parent.name if parent else cell.strain
        self.log(
            "arose",
            f"{s.name} arose from {pname} — “{note}”" if note else f"{s.name} arose from {pname}",
            strain=s.id,
            parent=cell.strain,
        )
        return s.id, src

    # --- interventions ------------------------------------------------------
    def whisper(self, text: str) -> None:
        with open(config.WHISPERS, "a") as f:
            f.write(f"- {text.strip()}\n")
        self.log("whisper", text.strip())

    def whispers(self) -> list[str]:
        if not config.WHISPERS.exists():
            return []
        return [ln[2:].strip() for ln in config.WHISPERS.read_text().splitlines() if ln.startswith("- ")]

    def drop(self, what: str, at: tuple[int, int] | None = None, r: float | None = None) -> str:
        d = self.dish
        if at is None:
            # somewhere on the agar, biased toward the middle
            cx, cy = d.center()
            at = (int(cx + self.rng.gauss(0, d.w / 5)), int(cy + self.rng.gauss(0, d.h / 5)))
            at = (max(0, min(d.w - 1, at[0])), max(0, min(d.h - 1, at[1])))
        x, y = at
        if what == "nutrient":
            d.feed_region(x, y, r or 5.0)
            msg = f"a drop of nutrient at ({x},{y})"
        elif what == "antibiotic":
            n = d.kill_region(x, y, r or 6.0)
            msg = f"antibiotic disc at ({x},{y}) — {n} cells killed"
        elif what == "mutagen":
            self.mutagen.boost = 6.0
            self.mutagen.boost_until = d.tick + 300
            self.mutagen.wake.set()
            msg = "mutagen added — mutation rate ×6 for 300 ticks"
        else:
            raise ValueError(f"unknown drop: {what}")
        self.log("drop", msg, what=what, at=list(at))
        return msg

    def _inbox(self) -> None:
        for p in sorted(config.INBOX.glob("*.json")):
            try:
                req = json.loads(p.read_text())
            except json.JSONDecodeError:
                p.unlink(missing_ok=True)
                continue
            p.unlink(missing_ok=True)
            try:
                if "whisper" in req:
                    self.whisper(req["whisper"])
                elif "drop" in req:
                    at = tuple(req["at"]) if req.get("at") else None
                    self.drop(req["drop"], at, req.get("r"))
            except Exception as e:  # noqa: BLE001
                self.log("mind", f"bad intervention: {e}")

    # --- the loop -----------------------------------------------------------
    def step(self) -> None:
        d = self.dish
        with self.lock:
            d.step()
        census = d.census()
        for s in self.registry.update(census, d.tick):
            self.mutagen.forget(s.id)
            lived = d.tick - s.born
            self.log("extinct", f"{s.name} went extinct after {lived} ticks (peak {s.peak})", strain=s.id)
        raw = d.phase()
        if raw == self._candidate:
            self._candidate_for += 1
        else:
            self._candidate, self._candidate_for = raw, 1
        if self._candidate_for >= 25 and raw != self.last_phase:
            if self.last_phase is not None:
                self.log("phase", f"culture entered {raw} phase")
            self.last_phase = raw
        phase = self.last_phase or raw
        if d.tick % 3 == 0:
            self.mutagen.context = {
                "tick": d.tick,
                "phase": phase,
                "census": census,
                "nutrient": d.nutrient_mean(),
                "whispers": self.whispers(),
            }
            self._inbox()
        if d.tick % curve.CADENCE == 0:
            self._curve(census, phase)
        if d.tick % 150 == 0:
            self.save()

    def metrics(self, census: dict[str, int] | None = None, phase: str | None = None) -> dict:
        """One row of the growth curve: what the dish knows about itself, plus lineage and
        turnover from the registry and the state of the mutagen's supply. Reads only."""
        d = self.dish
        if census is None:
            census = d.census()
        row = d.metrics(census)
        row["phase"] = phase or self.last_phase or d.phase()
        strains = self.registry.strains
        n = row["population"]
        generations = sum(k * strains[s].generation for s, k in census.items() if s in strains)
        row["mean_gen"] = generations / n if n else 0.0
        row["arisen"] = len(strains)
        row["extinct"] = sum(1 for s in strains.values() if s.extinct_at is not None)
        row["mutations_ready"] = self.mutagen.ready()
        row["mutations_taken"] = sum(1 for s in strains.values() if s.parent is not None)
        return row

    def _curve(self, census: dict, phase: str) -> None:
        row = self.metrics(census, phase)
        try:
            if self._curve_fields is None:
                self._curve_fields, added = curve.reconcile(config.CURVE)
                if added:
                    self.log("curve", f"growth curve widened: {len(added)} columns added ({', '.join(added)})")
            curve.append(config.CURVE, self._curve_fields, row)
        except curve.ERRORS as e:
            # a curve.csv the culture cannot read or write must not stop the dish: say so once,
            # keep trying every row (reconcile again if it never succeeded), and say when it works
            if not self._curve_broken:
                self.log("curve", f"growth curve not written from tick {row['tick']}: {e}")
            self._curve_broken = True
            return
        if self._curve_broken:
            self._curve_broken = False
            self.log("curve", f"growth curve resumed at tick {row['tick']}")

    def run(
        self, ticks: int | None = None, stop: threading.Event | None = None, tick_seconds: float = config.TICK_SECONDS
    ) -> None:
        self.mutagen.start()
        n = 0
        try:
            while not (stop and stop.is_set()):
                t0 = time.time()
                self.step()
                n += 1
                if ticks is not None and n >= ticks:
                    break
                dt = tick_seconds - (time.time() - t0)
                if dt > 0:
                    if stop:
                        stop.wait(dt)
                    else:
                        time.sleep(dt)
        finally:
            self.mutagen.close()
            self.save()

    # --- for observers ------------------------------------------------------
    def snapshot(self) -> dict:
        d = self.dish
        census = d.census()
        metrics = self.metrics(census)
        return {
            "seed": self.seed,
            "tick": d.tick,
            "phase": self.last_phase or d.phase(),
            "population": len(census) and sum(census.values()),
            "census": census,
            "tiles": d.tiles,
            "nutrient": metrics["nutrient"],
            "births": d.births,
            "deaths": dict(d.deaths),
            "history": list(d.history),
            "strains_total": len(self.registry.strains),
            "generation": max((s.generation for s in self.registry.strains.values()), default=0),
            "metrics": metrics,
            "mutagen": {
                "state": self.mutagen.state,
                "ready": self.mutagen.ready(),
                "pending": self.mutagen.pending(),
                "produced": self.mutagen.produced,
                "nonviable": self.mutagen.nonviable,
                "boosted": d.tick < self.mutagen.boost_until,
            },
            "mind": {
                "model": self.mind.model,
                "calls": self.mind.calls,
                "awake": self.mind.awake,
                "tokens": self.mind.prompt_tokens + self.mind.completion_tokens,
                "latency": self.mind.last_latency,
                "error": self.mind.last_error,
            },
            "uptime": time.time() - self.started,
        }


def sterilize() -> None:
    """Autoclave: wipe the vessel and the soma."""
    if config.VESSEL.exists():
        shutil.rmtree(config.VESSEL)
    config.VESSEL.mkdir()
    (config.VESSEL / "inbox").mkdir()
    if config.SOMA.exists():
        for p in config.SOMA.glob("*.py"):
            if p.name != "__init__.py":
                p.unlink()
    for p in config.SOMA.glob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)


def _fit_dish() -> tuple[int, int]:
    """Size the dish to the bench it was poured on (the current terminal)."""
    import shutil as _sh

    cols, rows = _sh.get_terminal_size((120, 40))
    w = int(config.env("BIOTIC_WIDTH") or max(40, min(96, cols - 52)))
    h = int(config.env("BIOTIC_HEIGHT") or max(18, min(44, rows - 15)))
    return w, h


def trial(seed: str, source: str, ticks: int = 500) -> tuple[int, int, int]:
    """Inoculate a small private dish and see whether the strain takes.
    Returns (peak population, final population, ticks)."""
    d = Dish(f"{seed}::trial", 40, 20)
    d.register("t", source)
    d.inoculate("t")
    peak = 0
    for _ in range(ticks):
        d.step()
        peak = max(peak, len(d.cells))
        if not d.cells:
            break
    return peak, len(d.cells), d.tick
