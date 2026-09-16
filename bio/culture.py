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
from .membrane import admit_isolated, inspect
from .mind import Dormant, Exhausted, Mind, MindError, fmt_usd, parse_budget
from .mutagen import Mutagen, exhausted_msg
from .strains import Registry

# Bookkeeping events: every one is in events.jsonl, but none is kept among the recent events
# the eyepiece shows, where one per call would crowd out what happened in the dish.
HIDDEN = {"call", "prepared"}

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
        mind.log = self.log  # every call the dish pays for is an event in its log
        self.events: deque[dict] = deque(maxlen=200)  # the recent visible events, for the eyepiece
        self._unsaid: list[tuple[str, str, dict]] = []  # what load() found out; run() logs it
        self.rng = random.Random(f"{seed}::culture")
        self.started = time.time()
        self.last_phase = None
        self._candidate = None
        self._candidate_for = 0
        self.mutation_rate = config.MUTATION_RATE
        self.lock = threading.Lock()
        self._curve_fields: list[str] | None = None  # header of curve.csv, reconciled on the first row
        self._curve_broken = False  # the last row could not be written; said once, retried every row
        self._save_broken = False  # the last dish.json could not be written; said once, retried every save
        self.mutagen = Mutagen(mind, seed, self.log)
        for sid, s in registry.strains.items():
            if sid in dish.genomes:
                self.mutagen.know(sid, s.name, s.source)
        dish.on_divide = self._on_divide
        config.INBOX.mkdir(parents=True, exist_ok=True)
        self._load_recent_events()

    # --- creation / persistence --------------------------------------------
    @classmethod
    def germinate(cls, seed: str, mind: Mind, fresh: bool = False, budget: float | None = None) -> Culture:
        if config.DISH_FILE.exists() and not fresh:
            raise FileExistsError("a culture already exists in vessel/ — `biotic sterilize` first, or use --fresh")
        if budget is not None:
            mind.budget_usd = parse_budget(budget)
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
        if mind.awake and mind.exhausted:
            # The budget went at the founding — there was none, or the founding calls spent it —
            # so the mutagen never has a call to make. Said here, once, or the dish would run for
            # a week without variation and the log would never say why: load() builds the mutagen
            # exhausted from the saved ledger, and neither it nor run() says it again.
            why = "nothing to spend" if mind.calls == 0 else "spent by the founding calls"
            cult.mutagen.state = "exhausted"
            cult.log(
                "mind",
                exhausted_msg(mind.spent_usd, mind.budget_usd, why),
                spent_usd=mind.spent_usd,
                budget_usd=mind.budget_usd,
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
            except Exhausted as e:
                # nothing left to try with: not a founder that would not grow, so not that message
                self.log("mind", f"genesis stopped ({e}) — founding cell is the built-in default")
                return default
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
    def load(cls, mind: Mind | None = None, budget: float | None = None) -> Culture:
        """Take up the dish in vessel/. The budget is the flag's if given, else what the dish
        remembers, else what the mind was constructed with (BIOTIC_BUDGET_USD). The spend is
        what the dish remembers, or the last `call` event in the log if that is further on:
        a process killed between saves left its calls there and nowhere else.

        Nothing is written: `biotic status` loads too, while another process may be running
        the dish. What there is to say about the ledger waits in `_unsaid` for `run()`, the
        process that will save the dish."""
        if not config.DISH_FILE.exists():
            raise FileNotFoundError('nothing in the dish — `biotic seed "<word>"` first')
        seed = config.SEED_FILE.read_text().strip()
        blob = json.loads(config.DISH_FILE.read_text())
        dish = Dish.from_dict(blob)
        reg = Registry.load(seed)
        m = mind or Mind()
        if isinstance(blob.get("mind"), dict):
            m.restore(blob["mind"])
        saved = m.spent_usd
        last = _last_call(config.EVENTS)
        if last is not None:
            m.reconcile(last)
        was = m.exhausted  # as restored: an exhaustion the process that spent the money already logged
        if budget is not None:
            m.budget_usd = parse_budget(budget)
        cult = cls(seed, dish, reg, m)
        st = (blob.get("culture") or {}).get("rng")  # absent from a dish.json written before it was saved
        if st:
            try:
                cult.rng.setstate((st[0], tuple(st[1]), st[2]))
            except (TypeError, ValueError, IndexError):
                pass
        if m.spent_usd > saved:
            msg = f"ledger caught up from the log — {fmt_usd(saved)} saved, {fmt_usd(m.spent_usd)} spent"
            cult._unsaid.append(("mind", msg, {}))
        if m.awake and m.exhausted and not was:
            msg = exhausted_msg(m.spent_usd, m.budget_usd, "the budget was lowered below the spend")
            cult._unsaid.append(("mind", msg, {"spent_usd": m.spent_usd, "budget_usd": m.budget_usd}))
        return cult

    def save(self) -> None:
        """Write dish.json and strains.json, atomically.

        The blob is the dish's, plus the culture's own generator, which rolls the mutations, so
        a resumed culture rolls them at the divisions the running one would have. A save that
        fails must not stop the dish: it is logged once as a `freezer` event, every later save
        is tried again, and another event says when writing works.
        """
        try:
            with self.lock:
                blob = self.dish.to_dict()
                blob["culture"] = {"rng": self.rng.getstate()}
                blob["mind"] = self.mind.ledger()
                tmp = config.DISH_FILE.with_suffix(".tmp")
                tmp.write_text(json.dumps(blob))
                tmp.replace(config.DISH_FILE)
                self.registry.save()
        except (TypeError, ValueError, OSError) as e:
            if not self._save_broken:
                self.log("freezer", f"dish.json not written from tick {self.dish.tick}: {e}; the culture runs on")
            self._save_broken = True
            return
        if self._save_broken:
            self._save_broken = False
            self.log("freezer", f"dish.json written again at tick {self.dish.tick}")

    # --- events -------------------------------------------------------------
    def log(self, kind: str, msg: str, **data) -> None:
        ev = {"t": time.time(), "tick": self.dish.tick, "kind": kind, "msg": msg, **data}
        if kind not in HIDDEN:
            self.events.append(ev)
        with open(config.EVENTS, "a") as f:
            f.write(json.dumps(ev) + "\n")

    def _load_recent_events(self) -> None:
        """The last 60 visible events, from the tail of the log, so a resumed dish's incubator log
        picks up where it left off; the bookkeeping between them is skipped, not counted."""
        if not config.EVENTS.exists():
            return
        recent: list[dict] = []
        for line in reversed(_tail(config.EVENTS)[0]):
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(ev, dict) and ev.get("kind") not in HIDDEN:
                recent.append(ev)
                if len(recent) == 60:
                    break
        self.events.extend(reversed(recent))

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
    def _screen(self) -> None:
        """Hold every strain in the dish against the current membrane before any of it runs.

        A dish thawed from `dish.json` carries genomes admitted under whatever rules held when
        they arose, and the static rules are what a release changes. A strain the gate now
        refuses does not get to run: its cells lyse, its genome leaves the dish, and one
        `nonviable` event names the reason; the registry marks it extinct on the next tick, as
        for any other death. Called from run(), not load(), so that `biotic status` does not
        rewrite the culture it reads.
        """
        d = self.dish
        for sid in list(d.genomes):
            v = inspect(d.genomes[sid])
            if v:
                continue
            with self.lock:
                n = d.lyse(sid)
            self.mutagen.forget(sid)
            s = self.registry.strains.get(sid)
            self.log(
                "nonviable",
                f"{s.name if s else sid} no longer passes the membrane — {v.reasons[0]}; {n} cells lysed",
                strain=sid,
            )

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
        for kind, msg, data in self._unsaid:  # what load() found out, said by the process that runs the dish
            self.log(kind, msg, **data)
        self._unsaid.clear()
        self._screen()
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
                "failures": self.mutagen.failures,
                "retry_in": max(0.0, self.mutagen.retry_at - self.mutagen.clock()),
            },
            "mind": {
                "model": self.mind.model,
                "calls": self.mind.calls,
                "awake": self.mind.awake,
                "tokens": self.mind.prompt_tokens + self.mind.completion_tokens,
                "latency": self.mind.last_latency,
                "error": self.mind.last_error,
                "spent_usd": self.mind.spent_usd,
                "budget_usd": self.mind.budget_usd,
                "exhausted": self.mind.exhausted,
            },
            "uptime": time.time() - self.started,
        }


def _tail(path, size: int = 64 * 1024) -> tuple[list[str], bool]:
    """The last `size` bytes of a file as lines, and whether that was the whole file. The log is
    the one thing in the vessel that grows without bound, and every load reads it: a week is
    tens of megabytes, of which the end is what matters. When the read is partial the first
    line is dropped, since the cut almost certainly fell inside it."""
    start = max(0, path.stat().st_size - size)
    with path.open("rb") as f:
        f.seek(start)
        lines = f.read().decode("utf-8", errors="replace").splitlines()
    if start:
        lines = lines[1:]
    return lines, start == 0


def _last_of_kind(lines: list[str], kind: str) -> dict | None:
    for line in reversed(lines):
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict) and ev.get("kind") == kind:
            return ev
    return None


def _last_call(path) -> dict | None:
    """The most recent `call` event in the log, or None. Its running totals are the truth about
    what the dish has spent when the process that made the calls never got to save. Found in
    the tail of the log; the whole of it is read only when the tail holds no call at all."""
    if not path.exists():
        return None
    lines, whole = _tail(path)
    ev = _last_of_kind(lines, "call")
    if ev is None and not whole:
        ev = _last_of_kind(path.read_text().splitlines(), "call")
    return ev


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
