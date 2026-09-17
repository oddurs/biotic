"""The culture: dish + strains + mutagen + the observer's interventions.

This is the thing you run. It owns the vessel/ directory.
"""

from __future__ import annotations

import fcntl
import json
import math
import os
import random
import shutil
import threading
import time
from collections import deque
from dataclasses import asdict
from pathlib import Path

from . import config, curve, freezer, prompts
from .dish import Cell, Dish, decode_memory, encode_memory
from .membrane import admit, admit_isolated, inspect, memory_fault
from .mind import Dormant, Exhausted, Mind, MindError, fmt_usd, parse_budget
from .mutagen import Mutagen, exhausted_msg, fmt_wait
from .naturalist import EVENTS_KEPT, NOTE_EVENTS, Naturalist, sketch
from .prompts import _n  # the pluralisation helper lives with the prompts that also use it
from .strains import Registry, check_record

# Bookkeeping events: every one is in events.jsonl, but none is kept among the recent events
# the eyepiece shows, where one per call would crowd out what happened in the dish.
HIDDEN = {"call", "prepared"}

# The mutagen's clocks: `wall` is the background thread the dish never waits on, `tick` is the
# dish calling the mind itself at most every MUTAGEN_EVERY_TICKS ticks. docs/experiments.md
CLOCKS = ("wall", "tick")

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
        self.saved_at: float | None = None  # wall time of the last dish.json write; None until saved/loaded
        self._resume: dict | None = None  # {"gap": seconds, "tick": resume_tick}; measured in load(), read by _packet()
        # The culture RNG carries the dish's flask salt too, so replicates roll their mutations at
        # different divisions; an empty flask keeps the exact key a lone culture has always used.
        self.flask = getattr(dish, "flask", "")
        base = f"{seed}::{self.flask}" if self.flask else seed
        self.rng = random.Random(f"{base}::culture")
        self.started = time.time()
        self.last_phase = None
        self._candidate = None
        self._candidate_for = 0
        self.mutation_rate = config.MUTATION_RATE
        self.clock = "wall"  # this process's mutagen clock; use_clock() sets it before run()
        self.clock_choice: str | None = None  # a --clock the dish remembers (dish.json); None: by command
        self.clock_used: str | None = None  # what the last run ran under, for `biotic status`
        self.every_ticks_used: int | None = None
        self.last_call_tick = -math.inf  # the tick schedule a resumed dish remembers; applied by use_clock("tick")
        self.retry_at_tick = 0.0
        self._interrupted = False  # ctrl-c arrived inside a blocking call; run() ends after this tick
        self.revivals: list[dict] = []  # how this dish came to be: one entry per revive, oldest first
        self.branch = 0  # the vessel's timeline: 0 until its first dish revive, one more at each; a curve coordinate
        self.watching: list[dict] = []  # revived strains still under observation
        self.lock = threading.Lock()
        self._curve_fields: list[str] | None = None  # header of curve.csv, reconciled on the first row
        self._curve_broken = False  # the last row could not be written; said once, retried every row
        self._save_broken = False  # the last dish.json could not be written; said once, retried every save
        self._freezer_broken = False  # the last unattended freeze failed; said once, retried at every cadence
        self.mutagen = Mutagen(mind, seed, self.log)
        self.naturalist = Naturalist(mind, seed, self.log)  # the observer; it reads packets, never the dish
        self.tick_seconds = config.TICK_SECONDS  # the pace run() was given; the naturalist is told it
        for sid, s in registry.strains.items():
            if sid in dish.genomes:
                self.mutagen.know(sid, s.name, s.source)
        dish.on_divide = self._on_divide
        config.INBOX.mkdir(parents=True, exist_ok=True)
        self._load_recent_events()

    # --- creation / persistence --------------------------------------------
    @classmethod
    def germinate(
        cls,
        seed: str,
        mind: Mind,
        fresh: bool = False,
        budget: float | None = None,
        thaw: Path | None = None,
        n: int | None = None,
        flask: str = "",
        founder: tuple[str, str, str] | None = None,
        size: tuple[int, int] | None = None,
    ) -> Culture:
        """Found a culture: autoclave the vessel (the freezer is kept), pour a dish, inoculate `n`
        cells (default config.INOCULUM) of the founder, save, and freeze tick 0 as `genesis`. The
        founder is what the mind writes from the seed, or the built-in default. With `thaw`, a
        strain sample, the founder is that strain instead, in a dish of the sample's seed and
        size — the same agar it was frozen from — and the strain is watched for
        config.REVIVE_WATCH ticks so the log can say whether it took. A thaw is a revive, so the
        dish that is there is frozen first as `pre-revive`; a sample that is refused — by the
        membrane, or for what it is missing — is refused before that, and nothing changes.

        For a replicate flask (docs/flasks.md), `flask` is the flask id, salted into the dish and
        culture RNGs so this replicate diverges from its siblings while sharing their agar; `size`
        fixes the dish geometry (so every replicate matches) rather than fitting it to the
        terminal; and `founder` is a `(name, note, source)` genome poured in directly, without the
        mind — the one ancestor every flask of a set is founded from."""
        if config.DISH_FILE.exists() and not fresh:
            raise FileExistsError("a culture already exists in vessel/ — `biotic sterilize` first, or use --fresh")
        pid = incubating()
        if pid is not None:
            raise RuntimeError(f"the incubator is running (pid {pid}) — stop it first")
        n = config.INOCULUM if n is None else int(n)
        if n < 1:
            raise ValueError(f"an inoculum is at least 1 cell, not {n}")
        if budget is not None:
            mind.budget_usd = parse_budget(budget)
        sample = None
        if thaw is not None:
            sample = _strain_sample(thaw)  # read, checked and passed through the membrane before anything changes
            if sample["seed"] != seed:
                raise ValueError(
                    f"the sample is from “{sample['seed']}”; a fresh dish for it has that seed, not “{seed}”"
                )
            if config.DISH_FILE.exists():
                cls.load(mind).freeze("pre-revive")
        sterilize()
        config.VESSEL.mkdir(exist_ok=True)
        config.SEED_FILE.write_text(seed.strip() + "\n")
        if flask:
            config.FLASK_FILE.write_text(flask + "\n")  # for the record; a lone dish never writes it
        w, h = (int(sample["w"]), int(sample["h"])) if sample else (size or _fit_dish())
        dish = Dish(seed, w, h, flask=flask)
        reg = Registry(seed)
        cult = cls(seed, dish, reg, mind)
        if sample is None and founder is not None:
            # a replicate flask: one ancestor for every flask of the set, poured in without the
            # mind (no network, no spend), so the flasks differ only by their RNG salt.
            name, note, src = founder
            s = reg.new(src, None, 0, name, note)
            memory = None
        elif sample is None:
            name, note, src = cult._genesis()
            s = reg.new(src, None, 0, name, note)
            memory = None
        else:
            s = reg.adopt(sample["strain"], 0)
            note = s.note
            memory = sample["memory"]
        dish.register(s.id, s.source)
        n = dish.inoculate(s.id, n, memory=memory)
        cult.mutagen.know(s.id, s.name, s.source)
        config.GENESIS.write_text(s.source)
        if sample is None:
            cult.log(
                "genesis",
                f"inoculated {n} cells of {s.name} — “{note}”" if note else f"inoculated {n} cells of {s.name}",
            )
        else:
            cult.watching.append({"strain": s.id, "since": 0, "until": config.REVIVE_WATCH})
            cult.log(
                "revived",
                f"revived {s.name} ({s.id}) into a fresh dish — {_n(n, 'cell')}",
                strain=s.id,
                into="fresh",
                n=n,
                at=None,
                sample=freezer.stem_of(Path(thaw)),
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
        cult._freeze_or_log("genesis")
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
                    prompts.GENESIS_SYSTEM, prompts.genesis_user(self.seed, failures), temperature=0.9, role="genesis"
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
        cult.restore_state(blob.get("culture") or {})  # absent from a dish.json written before it was saved
        saved_at = blob.get("saved_at")  # top-level persistence metadata, never in state_dict; older files have none
        cult.saved_at = saved_at
        if saved_at and dish.tick > 0:  # a germinated-but-never-run dish saves at tick 0; that is no resume
            gap = time.time() - saved_at
            logged = _last_gap(config.EVENTS)  # a gap already logged against this exact save
            already = logged is not None and logged.get("saved_at") == saved_at
            if gap >= config.INCUBATION_GAP and not already:  # threshold; also excludes clock-skew negatives
                # A process hard-killed between the resume drain and its first save leaves dish.json's
                # saved_at unchanged, so this gap would re-satisfy the threshold on the next load. The gap
                # is already in the log against this same saved_at, though, so — as with notes and the
                # ledger, which reconcile on reload — one absence is announced once.
                cult._resume = {"gap": gap, "tick": dish.tick}
                cult._unsaid.append(
                    (
                        "gap",
                        f"incubation resumed after {fmt_wait(gap)}",
                        {"seconds": gap, "saved_at": saved_at, "branch": cult.branch},
                    )
                )
        note = _last_note(config.EVENTS)  # a note the last save missed: in the log and the notebook, not dish.json
        if note is not None:
            cult.naturalist.reconcile(note)
        if m.spent_usd > saved:
            msg = f"ledger caught up from the log — {fmt_usd(saved)} saved, {fmt_usd(m.spent_usd)} spent"
            cult._unsaid.append(("mind", msg, {}))
        if m.awake and m.exhausted and not was:
            msg = exhausted_msg(m.spent_usd, m.budget_usd, "the budget was lowered below the spend")
            cult._unsaid.append(("mind", msg, {"spent_usd": m.spent_usd, "budget_usd": m.budget_usd}))
        return cult

    def save(self) -> None:
        """Write dish.json and strains.json, atomically.

        The blob is the dish's, plus the culture's own state (state_dict: the generator that rolls
        the mutations, the phase detector, the revival chain) and the mind's ledger, so a resumed
        culture rolls them at the divisions the running one would have. A save that
        fails must not stop the dish: it is logged once as a `freezer` event, every later save
        is tried again, and another event says when writing works.
        """
        now = time.time()  # the wall clock this write happens at; a resume measures its gap from here
        try:
            with self.lock:
                blob = self.dish.to_dict()
                blob["culture"] = self.state_dict()
                blob["mind"] = self.mind.ledger()
                blob["saved_at"] = now  # top-level persistence metadata, kept out of state_dict and freezer samples
                tmp = config.DISH_FILE.with_suffix(".tmp")
                tmp.write_text(json.dumps(blob))
                tmp.replace(config.DISH_FILE)
                self.registry.save()
        except (TypeError, ValueError, OSError) as e:
            if not self._save_broken:
                self.log("freezer", f"dish.json not written from tick {self.dish.tick}: {e}; the culture runs on")
            self._save_broken = True
            return
        self.saved_at = now  # only on a write that took; a broken save leaves the last good timestamp
        if self._save_broken:
            self._save_broken = False
            self.log("freezer", f"dish.json written again at tick {self.dish.tick}")

    def state_dict(self) -> dict:
        """The culture's own state — everything outside the dish and the registry that decides
        the next tick: the mutation-roll RNG, the phase detector, the mutagen boost — plus the
        revival chain, the branch, the watch list, the naturalist's baseline (the last note and
        what it measured), and the mutagen's clock, counters and tick schedule; nothing the dish
        depends on. Rides in dish.json and in every dish sample."""
        m = self.mutagen
        if m.ticked:  # the schedule as it stands; on the wall clock, what was loaded, carried forward unchanged
            self.last_call_tick, self.retry_at_tick = m.last_call, m.retry_at
        return {
            "rng": list(self.rng.getstate()),
            "last_phase": self.last_phase,
            "candidate": self._candidate,
            "candidate_for": self._candidate_for,
            "boost": m.boost,
            "boost_until": m.boost_until,
            "revivals": [dict(r) for r in self.revivals],
            "branch": self.branch,
            "watching": [dict(w) for w in self.watching],
            "naturalist": self.naturalist.baseline(),
            # the mutagen's clock: the --clock the dish remembers, and a record of the last run
            "clock": self.clock_choice,
            "clock_used": self.clock_used,
            "every_ticks_used": self.every_ticks_used,
            # the supply counters, coordinates of the timeline like `branch`; the tick schedule
            "attempted": m.attempted,
            "viable": m.viable,
            "nonviable": m.nonviable,
            "last_call_tick": self.last_call_tick if math.isfinite(self.last_call_tick) else None,
            "retry_at_tick": self.retry_at_tick,
        }

    def restore_state(self, d: dict) -> None:
        """The inverse of state_dict. Missing keys mean a fresh culture; a bad RNG state is
        ignored, as in Dish.from_dict. The tick schedule goes to the mutagen when the culture is
        already on the tick clock (a revive after use_clock); before that use_clock() applies it."""
        try:
            st = d["rng"]
            self.rng.setstate((st[0], tuple(st[1]), st[2]))
        except Exception:  # noqa: BLE001
            pass
        self.last_phase = d.get("last_phase")
        self._candidate = d.get("candidate")
        self._candidate_for = int(d.get("candidate_for") or 0)
        m = self.mutagen
        m.boost = float(d.get("boost") or 1.0)
        m.boost_until = int(d.get("boost_until") or 0)
        self.revivals = [dict(r) for r in d.get("revivals") or []]
        self.branch = int(d.get("branch") or 0)
        self.watching = [dict(w) for w in d.get("watching") or []]
        self.naturalist.restore(d.get("naturalist"))
        self.clock_choice = d.get("clock") if d.get("clock") in CLOCKS else None
        self.clock_used = d.get("clock_used") if d.get("clock_used") in CLOCKS else None
        every = d.get("every_ticks_used")
        self.every_ticks_used = int(every) if isinstance(every, int | float) and every >= 1 else None
        m.attempted = int(d.get("attempted") or 0)
        m.viable = int(d.get("viable") or 0)
        m.nonviable = int(d.get("nonviable") or 0)
        last = d.get("last_call_tick")
        self.last_call_tick = float(last) if isinstance(last, int | float) else -math.inf
        self.retry_at_tick = float(d.get("retry_at_tick") or 0.0)
        if m.ticked:
            m.last_call, m.retry_at = self.last_call_tick, self.retry_at_tick

    # --- the mutagen's clock -------------------------------------------------
    def use_clock(self, flag: str | None, command: str) -> str:
        """Choose the mutagen clock for this process: --clock, else BIOTIC_MUTAGEN_CLOCK, else the
        --clock the dish remembers, else by command (`live` on the wall clock, so the observer never
        waits on the network; anything else on the tick clock, so the supply of variants is a
        function of ticks and budget). A flag is remembered in dish.json and sticks, like --budget;
        the environment variable is per process and is not written into the dish. Raises ValueError
        on a value that is not wall or tick. Call once, before run()."""
        choice = flag or config.MUTAGEN_CLOCK or self.clock_choice
        if choice is not None and choice not in CLOCKS:
            raise ValueError(f"the mutagen clock is wall or tick, not {choice!r}")
        self.clock = choice or ("wall" if command == "live" else "tick")
        if flag:
            self.clock_choice = flag
        if self.clock == "tick":
            self.mutagen.clock_ticks(
                config.MUTAGEN_EVERY_TICKS,
                lambda: float(self.dish.tick),  # reads self.dish at call time: a revive swaps it
                last_call=self.last_call_tick,
                retry_at=self.retry_at_tick,
            )
        return self.clock

    def clock_line(self) -> str:
        """`tick, every 40 ticks` / `wall, at least 12 s between calls`: the words `biotic run`
        prints and the run-start event carries."""
        if self.clock == "tick":
            return clock_words("tick", self.mutagen.every_ticks)
        return f"wall, at least {config.MUTAGEN_INTERVAL:g} s between calls"

    # --- events -------------------------------------------------------------
    def log(self, kind: str, msg: str, **data) -> None:
        ev = {"t": time.time(), "tick": self.dish.tick, "kind": kind, "msg": msg, **data}
        if kind not in HIDDEN:
            self.events.append(ev)
        config.VESSEL.mkdir(parents=True, exist_ok=True)
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
        if self.clock == "tick":
            try:
                got = self.mutagen.mutate_now(cell.strain)
            except KeyboardInterrupt:
                self._interrupted = True  # this tick finishes cleanly; run() raises it after step()
                got = None
        else:
            got = self.mutagen.take(cell.strain)
            if not got:
                self.mutagen.request(cell.strain)
        if not got:
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

    def _inbox(self) -> bool:
        """Take the requests other processes left. Returns True if a revive replaced the dish,
        in which case the caller's view of it — its tick, its census — is stale."""
        replaced = False
        for p in sorted(config.INBOX.glob("*.json")):
            try:
                req = json.loads(p.read_text())
            except json.JSONDecodeError:
                p.unlink(missing_ok=True)
                continue
            p.unlink(missing_ok=True)
            try:
                pid = req.get("pid")
                if pid and int(pid) != os.getpid():
                    # queued for an incubator that has since stopped: a whisper or a drop keeps, a
                    # freeze or a revive was meant for that run and would fire unannounced here
                    what = next((k for k in ("freeze", "freeze_strain", "revive", "revive_strain") if k in req), "?")
                    self.log("mind", f"dropped a {what} request queued for another incubator (pid {pid})")
                    continue
                if "whisper" in req:
                    self.whisper(req["whisper"])
                elif "drop" in req:
                    at = tuple(req["at"]) if req.get("at") else None
                    self.drop(req["drop"], at, req.get("r"))
                elif "freeze" in req:
                    self.freeze(req["freeze"] or "manual")
                elif "freeze_strain" in req:
                    self.freeze_strain(req["freeze_strain"], req.get("label") or None)
                elif "revive" in req:
                    self.revive(freezer.resolve(str(req["revive"]), kind="dish"))
                    replaced = True
                elif "revive_strain" in req:
                    if (req.get("into") or "current") != "current":
                        raise ValueError(
                            "a fresh dish needs a stopped incubator — ctrl-c, then `biotic revive --strain`"
                        )
                    at = tuple(req["at"]) if req.get("at") else None
                    n = config.INOCULUM if req.get("n") is None else int(req["n"])
                    self.revive_strain(freezer.resolve(str(req["revive_strain"]), kind="strain"), n=n, at=at)
            except Exception as e:  # noqa: BLE001
                self.log("mind", f"bad intervention: {e}")
        return replaced

    # --- the freezer --------------------------------------------------------
    def freeze(self, label: str = "manual") -> Path:
        """Put the whole dish in the freezer: cells, agar, pheromone, RNGs, genomes, the strain
        registry and the culture's own state, as vessel/freezer/<tick>-<label>.json.gz.
        Never overwrites an earlier sample. Returns the path."""
        label = freezer.clean_label(label)
        with self.lock:
            d = self.dish
            census = d.census()
            doc = {
                "format": freezer.FORMAT,
                "kind": "dish",
                "biotic": freezer.version(),
                "seed": self.seed,
                "tick": d.tick,
                "label": label,
                "frozen_at": time.time(),
                "population": sum(census.values()),
                "strains_living": len(census),
                "strains_total": len(self.registry.strains),
                "revivals": [dict(r) for r in self.revivals],
                "dish": d.to_dict(),
                "culture": self.state_dict(),
                "strains": self.registry.to_dict(),
            }
        path = freezer.unique_path(config.FREEZER / (freezer.stem(doc["tick"], label) + ".json.gz"))
        freezer.write(doc, path)
        stem = freezer.stem_of(path)
        self.log(
            "frozen",
            f"frozen as {stem} ({_n(doc['population'], 'cell')}, {_n(doc['strains_living'], 'strain')})",
            sample=stem,
            label=label,
        )
        return path

    def _freeze_or_log(self, label: str) -> Path | None:
        """The culture's own freezes — genesis, and the cadence — must not stop the dish when the
        freezer cannot be written (permissions, a full disk, a file where the directory should
        be): say so once as a `freezer` event, try again at the next cadence, and say when it
        works again. A freeze a person asked for raises instead, so the CLI and the inbox can
        tell them."""
        try:
            path = self.freeze(label)
        except OSError as e:
            if not self._freezer_broken:
                self.log("freezer", f"sample not written at tick {self.dish.tick}: {e}")
            self._freezer_broken = True
            return None
        if self._freezer_broken:
            self._freezer_broken = False
            self.log("freezer", f"freezer resumed at tick {self.dish.tick}")
        return path

    def freeze_strain(self, sid: str, label: str | None = None) -> Path:
        """A strain sample: the genome, its lineage, and the memory of its most energetic living
        cell (none if the strain is extinct), as vessel/freezer/strain-<id>[-<label>].json. The
        memory is written as encode_memory writes it: tuples and non-string keys tagged, so it
        thaws exactly."""
        label = freezer.clean_label(label) if label else None
        s = self.registry.strains.get(sid)
        if s is None:
            raise KeyError(f"no strain {sid}")
        with self.lock:
            d = self.dish
            cells = [c for c in d.cells.values() if c.strain == sid]
            best = max(cells, key=lambda c: (c.energy, -c.y, -c.x), default=None)
            doc = {
                "format": freezer.FORMAT,
                "kind": "strain",
                "biotic": freezer.version(),
                "seed": self.seed,
                "w": d.w,
                "h": d.h,
                "tick": d.tick,
                "frozen_at": time.time(),
                "label": label,
                "strain": asdict(s),
                "lineage": [x.name for x in self.registry.lineage_of(sid)],
                "memory": encode_memory(best.memory) if best else {},
                "living": len(cells),
            }
        path = freezer.unique_path(config.FREEZER / (freezer.strain_stem(sid, label) + ".json"))
        freezer.write(doc, path)
        stem = freezer.stem_of(path)
        self.log("frozen", f"strain {s.name} ({s.id}) frozen as {stem}", sample=stem, strain=sid)
        return path

    def _swap(self, dish: Dish, registry: Registry, state: dict) -> None:
        """Replace the dish and registry in one motion, so the eyepiece never sees half of each.
        The naturalist keeps the vessel's baseline (the caller put it in `state`) and marks it
        with a seam: the next note compares nothing across the replacement."""
        with self.lock:
            self.dish, self.registry = dish, registry
            dish.on_divide = self._on_divide
            self.restore_state(state)
            self._resume = None  # a resume measured on the old branch must not reach the new one's first note
        self.mutagen.reset({sid: (s.name, s.source) for sid, s in registry.strains.items() if sid in dish.genomes})
        self.naturalist.reset()

    def _occupied(self) -> bool:
        """Whether there is a dish to protect: cells, ticks on the clock, or a dish.json in the
        vessel. Decides the seed rule and whether a revive freezes `pre-revive` first."""
        return bool(self.dish.cells) or self.dish.tick > 0 or config.DISH_FILE.exists()

    def revive(self, path: Path) -> None:
        """Replace the dish with a dish sample. Every genome in the sample passes the membrane's
        static gate again, before anything changes; the dish that is there is frozen as
        `pre-revive`; then the sample becomes the dish, the registry and the culture's own state,
        a `revived` event is logged at the revived tick, and the vessel is saved. No curve row is
        written for the revive; the rows that follow carry the vessel's next branch number, one
        more than the dish had, whatever the sample's own was, so (branch, tick) stays unique in
        curve.csv however far forward or back the revive went (docs/curve.md)."""
        path = Path(path)
        doc = freezer.read(path)
        stem = freezer.stem_of(path)
        if doc["kind"] != "dish":
            raise ValueError(f"{stem} is a strain sample — `biotic revive --strain {stem}`")
        for sid, src in doc["dish"]["genomes"].items():
            v = inspect(src)
            if not v:
                raise ValueError(f"genome of strain {sid} in {stem} fails the membrane: {v.reasons[0]}")
        occupied = self._occupied()
        if occupied and doc["seed"] != self.seed:
            # the agar is a function of the seed: a vessel that holds a dish keeps its seed
            raise ValueError(
                f"the sample is from “{doc['seed']}”; this vessel is “{self.seed}” — "
                "sterilize first (the freezer is kept), then revive"
            )
        # the sample is read in full before the dish is frozen, so a sample that cannot be read
        # (a hand edit that broke a record) refuses before anything changes
        dish = Dish.from_dict(doc["dish"])
        reg = Registry.from_dict(doc["seed"], doc["strains"])
        if occupied:
            self.freeze("pre-revive")
        old_tick = self.dish.tick
        state = dict(doc.get("culture") or {})
        state["revivals"] = list(state.get("revivals") or []) + [
            {"from": doc["tick"], "was": old_tick, "at": time.time(), "sample": stem}
        ]
        state["branch"] = self.branch + 1  # the vessel's count, not the sample's: monotone over curve.csv
        state["naturalist"] = self.naturalist.baseline()  # the notebook is the vessel's too, not the sample's
        # the mutagen's clock belongs to the vessel too: the flag it remembers and what the last run used
        state["clock"], state["clock_used"], state["every_ticks_used"] = (
            self.clock_choice,
            self.clock_used,
            self.every_ticks_used,
        )
        self.seed = self.mutagen.seed = self.naturalist.seed = doc["seed"]
        self._swap(dish, reg, state)
        config.VESSEL.mkdir(parents=True, exist_ok=True)
        config.SEED_FILE.write_text(self.seed + "\n")
        census = dish.census()
        where = f"the dish was at {old_tick}" if occupied else "into an empty vessel"
        self.log(
            "revived",
            f"revived from tick {doc['tick']} ({where}) — {_n(sum(census.values()), 'cell')}, {_n(len(census), 'strain')}",
            sample=stem,
            was=old_tick,
            branch=self.branch,
            **{"from": doc["tick"]},
        )
        self.save()

    def revive_strain(self, path: Path, n: int = config.INOCULUM, at: tuple[int, int] | None = None) -> None:
        """Inoculate a strain sample into the current dish as an invader: `n` cells on the free
        tiles nearest `at` (default: the centre; a point outside the dish is refused), each
        carrying the sampled memory; the dish's RNG is not touched. The genome passes the whole
        membrane again; the dish is frozen first as `pre-revive`; the strain is then watched for
        config.REVIVE_WATCH ticks and the log says whether it took. A fresh dish of the strain
        is germinate(thaw=path)."""
        path = Path(path)
        if n < 1:
            raise ValueError(f"an inoculum is at least 1 cell, not {n}")
        doc = _strain_sample(path)
        if not self._occupied():
            raise ValueError("nothing in the dish to revive into — leave out --into for a fresh dish")
        d = self.dish
        at = (int(at[0]), int(at[1])) if at else d.center()
        if not (0 <= at[0] < d.w and 0 <= at[1] < d.h):
            # inoculate(at=) takes the nearest free tiles, so a point off the dish would land on the rim
            raise ValueError(f"({at[0]},{at[1]}) is outside the dish ({d.w}×{d.h})")
        self.registry.check(doc["strain"])  # every refusal comes before the pre-revive freeze
        self.freeze("pre-revive")
        with self.lock:  # the eyepiece reads the registry under the lock too
            s = self.registry.adopt(doc["strain"], d.tick)
            d.register(s.id, s.source)  # before the first tick: a genome the dish does not know lyses its cells
            placed = d.inoculate(s.id, n, at=at, memory=doc["memory"])
        self.mutagen.know(s.id, s.name, s.source)
        self.watching.append({"strain": s.id, "since": d.tick, "until": d.tick + config.REVIVE_WATCH})
        self.log(
            "revived",
            f"revived {s.name} ({s.id}) into the dish at ({at[0]},{at[1]}) — {_n(placed, 'cell')}",
            strain=s.id,
            into="current",
            n=placed,
            at=list(at),
            sample=freezer.stem_of(path),
        )
        self.save()

    def _watch(self, census: dict) -> None:
        """Report on revived strains: extinct before the watch ends is `did not take`; alive at
        the end is `took`. Bookkeeping only — nothing here touches the dish."""
        keep = []
        for w in self.watching:
            sid = w["strain"]
            n = census.get(sid, 0)
            ticks = self.dish.tick - w["since"]
            s = self.registry.strains.get(sid)
            name = s.name if s else sid
            if n == 0:
                self.log(
                    "revived",
                    f"revived {name} did not take — extinct after {_n(ticks, 'tick')}",
                    strain=sid,
                    took=False,
                    cells=0,
                    ticks=ticks,
                )
            elif self.dish.tick >= w["until"]:
                self.log(
                    "revived",
                    f"revived {name} took — {_n(n, 'cell')} after {_n(ticks, 'tick')}",
                    strain=sid,
                    took=True,
                    cells=n,
                    ticks=ticks,
                )
            else:
                keep.append(w)
        self.watching = keep

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
        if self.mutagen.boost != 1.0 and d.tick >= self.mutagen.boost_until:
            self.mutagen.boost = 1.0  # the drop wore off: the call interval goes back with the rate
        census = d.census()
        for s in self.registry.update(census, d.tick):
            self.mutagen.forget(s.id)
            lived = d.tick - s.born
            self.log("extinct", f"{s.name} went extinct after {lived} ticks (peak {s.peak})", strain=s.id)
        if self.watching:
            self._watch(census)
        raw = d.phase()
        if raw == self._candidate:
            self._candidate_for += 1
        else:
            self._candidate, self._candidate_for = raw, 1
        if self._candidate_for >= 25 and raw != self.last_phase:
            if self.last_phase is not None:
                self.log("phase", f"culture entered {raw} phase", phase=raw)
            self.last_phase = raw
        phase = self.last_phase or raw
        if d.tick % 3 == 0:
            self._context(census, phase)
            if self._inbox():
                return  # the dish was replaced: the rest of this step would describe the old one
        if d.tick % curve.CADENCE == 0:
            self._curve(census, phase)
        if self.naturalist.due(d.tick):
            self.naturalist.observe(self._packet(census, phase))
        if d.tick % 150 == 0:
            self.save()
        if config.FREEZE_EVERY and d.tick % config.FREEZE_EVERY == 0:
            self._freeze_or_log("auto")

    def _context(self, census: dict, phase: str) -> None:
        """What the mutagen tells the mind about the dish: refreshed every third tick, and on the
        tick clock once before the first tick of a run."""
        d = self.dish
        self.mutagen.context = {
            "tick": d.tick,
            "phase": phase,
            "census": census,
            "nutrient": d.nutrient_mean(),
            "whispers": self.whispers(),
        }

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
        row["branch"] = self.branch
        row["mutations_attempted"] = self.mutagen.attempted
        row["mutations_viable"] = self.mutagen.viable
        return row

    def _packet(self, census: dict[str, int], phase: str) -> dict:
        """What the naturalist is shown, copied out of the dish on this thread so its own never
        reads it: the readings, the census with names, notes, generations and shares, the dish's
        own recent history (NOTE_EVENTS: no apparatus bookkeeping) and a coarse sketch. No genome
        goes in. Reads only, as `_curve` does."""
        d = self.dish
        total = sum(census.values()) or 1
        rows = []
        for sid, n in sorted(census.items(), key=lambda kv: (-kv[1], kv[0])):
            s = self.registry.strains.get(sid)
            rows.append(
                {
                    "id": sid,
                    "name": s.name if s else sid,
                    "note": s.note if s else "",
                    "generation": s.generation if s else 0,
                    "cells": n,
                    "share": n / total,
                }
            )
        events = [
            {"t": e["t"], "tick": e["tick"], "kind": e["kind"], "msg": e["msg"]}
            for e in list(self.events)  # one step: the mutagen appends from its own thread
            if e.get("kind") in NOTE_EVENTS
        ][-EVENTS_KEPT:]
        return {
            "seed": self.seed,
            "tick": d.tick,
            "t": time.time(),
            "branch": self.branch,
            "phase": phase,
            "tiles": d.tiles,
            "tick_seconds": self.tick_seconds,
            "metrics": self.metrics(census, phase),
            "census": rows,
            "events": events,
            "resume": self._resume,  # null, or the gap this run resumed after; the first note reports it
            "sketch": sketch(d, census, {r["id"]: r["name"] for r in rows}),
        }

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
        lock = _lock_incubator()
        for kind, msg, data in self._unsaid:  # what load() found out, said by the process that runs the dish
            self.log(kind, msg, **data)
        self._unsaid.clear()
        self._screen()
        self.tick_seconds = tick_seconds
        self.clock_used, self.every_ticks_used = self.clock, self.mutagen.every_ticks
        self.log("mind", f"mutagen clock: {self.clock_line()}", clock=self.clock, every_ticks=self.every_ticks_used)
        if self.clock == "tick":
            # a blocking call can come in the first tick after a resume: prompt it with the real census and
            # phase. Not on the wall clock, where a primed context lets the thread's spontaneous path fire
            # at its first turn, and the calls a `live` sitting makes are meant to be what they were.
            d = self.dish
            self._context(d.census(), self.last_phase or d.phase())
        self._interrupted = False
        self.mutagen.start()
        if config.NOTES_EVERY and self.mind.awake:  # a dormant mind writes no notes; the mutagen's event says so
            self.naturalist.start()
        n = 0
        try:
            while not (stop and stop.is_set()):
                t0 = time.time()
                self.step()
                if self._interrupted:
                    raise KeyboardInterrupt  # ctrl-c inside a blocking call: the tick finished; the dish is whole
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
            self.naturalist.close()
            self.save()
            _unlock_incubator(lock)

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
                "clock": self.clock,
                "every_ticks": self.mutagen.every_ticks,
                "ready": self.mutagen.ready(),
                "pending": self.mutagen.pending(),
                "attempted": self.mutagen.attempted,
                "viable": self.mutagen.viable,
                "nonviable": self.mutagen.nonviable,
                "boosted": d.tick < self.mutagen.boost_until,
                "failures": self.mutagen.failures,
                "retry_in": max(0.0, self.mutagen.retry_at - self.mutagen.clock()),  # in the clock's unit
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
            "note": self.naturalist.latest(),
            "uptime": time.time() - self.started,
            "saved_at": self.saved_at,
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


def _last_event(path, kind: str, whole: bool = False) -> dict | None:
    """The most recent event of `kind` in the tail of the log, or None; with `whole`, the rest
    of the file is read when the tail holds none."""
    if not path.exists():
        return None
    lines, all_of_it = _tail(path)
    ev = _last_of_kind(lines, kind)
    if ev is None and whole and not all_of_it:
        ev = _last_of_kind(path.read_text().splitlines(), kind)
    return ev


def _last_call(path) -> dict | None:
    """The most recent `call` event in the log, or None. Its running totals are the truth about
    what the dish has spent when the process that made the calls never got to save. Found in
    the tail of the log; the whole of it is read only when the tail holds no call at all."""
    return _last_event(path, "call", whole=True)


def _last_note(path) -> dict | None:
    """The most recent `note` event, or None. A note dish.json missed was written within the
    last 150 ticks, which is always in the tail; a dish with no notes at all is never made to
    read its whole log for them."""
    return _last_event(path, "note")


def clock_words(clock: str, every_ticks: int | None) -> str:
    """`tick, every 40 ticks` or `wall`: the clock as `biotic status` and the vitals name it."""
    if clock == "tick" and every_ticks:
        return f"tick, every {_n(int(every_ticks), 'tick')}"
    return clock


def _last_gap(path) -> dict | None:
    """The most recent `gap` event, or None. It carries the `saved_at` it resumed from; when a
    process was killed before its first post-resume save, dish.json still holds that same
    saved_at, and load() reads this to keep one absence from being logged twice. A gap logged
    against the current saved_at was written at that resume, before any save, so it is in the
    tail; a dish that never resumed reads no more of its log for one."""
    return _last_event(path, "gap")


def _strain_sample(path: Path) -> dict:
    """A strain sample, read and admitted. Samples are files anyone can edit, so the genome
    passes the whole membrane again — the static gate and the smoke test — before it touches a
    dish, and the memory, decoded from its tags, is held to the rule the dish applies after
    every tick (both callers save right after placing the cells, before any tick runs it), so
    a sample whose memory breaks it is refused by name here, before the pre-revive freeze.
    Main thread only: the smoke test's budget is signal-based."""
    path = Path(path)
    doc = freezer.read(path)
    stem = freezer.stem_of(path)
    if doc["kind"] != "strain":
        raise ValueError(f"{stem} is a dish sample — `biotic revive {stem}`")
    sd = doc["strain"]
    check_record(sd)
    v = admit(sd["source"])
    if not v:
        raise ValueError(f"{sd.get('name', '?')} ({sd.get('id', '?')}) does not pass the membrane: {v.reasons[0]}")
    mem = decode_memory(doc.get("memory") or {})
    fault = memory_fault(mem)
    if fault:
        raise ValueError(f"{stem}: {fault}")
    doc["memory"] = mem
    return doc


# --- the incubator lock -------------------------------------------------------
LOCK_TRIES = 8  # a probe by `biotic status` holds the lock for microseconds; do not mistake it for an incubator
LOCK_RETRY = 0.03


def _lock_incubator():
    """Hold vessel/incubator.lock for as long as a culture runs. Advisory (flock), so the kernel
    lets go of it if the process dies; the pid inside is for the message only."""
    config.VESSEL.mkdir(parents=True, exist_ok=True)
    f = open(config.LOCK_FILE, "a+")
    for attempt in range(LOCK_TRIES):
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if attempt + 1 < LOCK_TRIES:
                time.sleep(LOCK_RETRY)
                continue
            f.seek(0)
            pid = f.read().strip() or "?"
            f.close()
            raise RuntimeError(f"the incubator is already running (pid {pid})") from None
    f.seek(0)
    f.truncate()
    f.write(f"{os.getpid()}\n")
    f.flush()
    return f


def _unlock_incubator(f) -> None:
    try:
        fcntl.flock(f, fcntl.LOCK_UN)
    finally:
        f.close()


def incubating() -> int | None:
    """The pid of the process running this vessel's culture, or None if nothing is. 0 if the
    lock is held but the pid could not be read."""
    if not config.LOCK_FILE.exists():
        return None
    with open(config.LOCK_FILE, "a+") as f:
        try:
            # a shared probe: an incubator's exclusive lock refuses it, and probes do not refuse
            # each other; the incubator retries in case a probe is what it ran into
            fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            f.seek(0)
            try:
                return int(f.read().strip())
            except ValueError:
                return 0
        fcntl.flock(f, fcntl.LOCK_UN)
    return None


def sterilize(freezer: bool = False) -> None:
    """Autoclave: wipe the vessel. The soma (the fossil record) lives inside the vessel now, so
    the loop below removes it too; the freezer is not in the flask, so vessel/freezer/ is kept
    unless `freezer` is true."""
    pid = incubating()
    if pid is not None:
        raise RuntimeError(f"the incubator is running (pid {pid}) — stop it first")
    if config.VESSEL.exists():
        for p in config.VESSEL.iterdir():
            if p == config.FREEZER and not freezer:
                continue
            if p.is_dir() and not p.is_symlink():
                shutil.rmtree(p)
            else:
                p.unlink()
    config.VESSEL.mkdir(exist_ok=True)
    config.INBOX.mkdir(exist_ok=True)


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
