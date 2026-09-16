"""The naturalist: an observer thread that keeps the lab notebook, vessel/fieldnotes.md.

Every NOTES_EVERY ticks the culture hands it an observation packet — what the instruments
record and the dish's own history, never a genome — and it asks the mind for the next entry.
The dish never waits on it: the main thread builds the packet, this thread makes the call.

One slot, no queue: a packet the thread has not yet written is replaced by the next one, and
`due()` refuses a look sooner than NOTES_MIN_SECONDS after the last, so the number of notes
is a function of wall time and call latency, never of the seed. The last note written and
what it measured is the baseline every later note is compared with; it is saved with the
dish, rides on every `note` event so a hard kill loses nothing, and is marked with a seam
when the dish is replaced from the freezer, so the next entry compares nothing across it.

Nothing the naturalist writes reaches the mutagen. The observer whispers; the observer
does not grade.
"""

from __future__ import annotations

import contextlib
import copy
import math
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import config, freezer, prompts
from .mind import Dormant, Exhausted, Mind, MindError, backoff, fmt_budget
from .mutagen import fmt_wait

SWEEP_FROM, SWEEP_TO = 0.10, 0.70  # a strain under SWEEP_FROM at the last entry and over SWEEP_TO now is a sweep
CENSUS_ROWS = 12  # strains the prompt lists; the rest are one line
LOG_LINES = 20  # events the prompt shows, the most recent since the last entry
EVENTS_KEPT = 60  # visible events the packet copies; compose() keeps those after the last entry
SKETCH_W = 48  # the sketch is at most this wide: k×k tiles per glyph for the smallest k that fits
MAX_TOKENS = 400  # eight sentences and room to spare
TEMPERATURE = 0.7
NOTE_EVENTS = frozenset({"genesis", "arose", "nonviable", "extinct", "phase", "drop", "whisper", "frozen", "revived"})
METRIC_KEYS = (
    "population",
    "strains",
    "shannon",
    "dominance",
    "births",
    "starved",
    "lysed",
    "senescent",
    "killed",
    "arisen",
    "extinct",
)
LETTERS = "abcdefghijklmnopqrstuvwxyz"
HEADING = re.compile(r"^## tick (\d+) · (.+)$")


@dataclass
class Note:
    tick: int
    when: str
    text: str


# --- the notebook file ----------------------------------------------------------
def heading(tick: int, t: float) -> str:
    return f"## tick {tick} · {freezer.when(t)}"


def append_note(path: Path, seed: str, tick: int, t: float, text: str) -> None:
    """Append one entry. A new file gets the notebook's title first; each entry is one write,
    so a reader beside the incubator sees whole entries."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = not path.exists() or path.stat().st_size == 0
    with open(path, "a", encoding="utf-8") as f:
        if fresh:
            f.write(f"# field notes — “{seed}”\n")
        f.write(f"\n{heading(tick, t)}\n\n{text.strip()}\n")


def read_notes(path: Path) -> list[Note]:
    """Every entry in the notebook, oldest first. Tolerant: a heading with no text yet is an
    entry with empty text; anything before the first heading is the title and is skipped."""
    if not path.exists():
        return []
    notes: list[Note] = []
    head: tuple[int, str] | None = None
    body: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = HEADING.match(line)
        if m:
            if head is not None:
                notes.append(Note(head[0], head[1], "\n".join(body).strip()))
            head, body = (int(m.group(1)), m.group(2).strip()), []
        elif head is not None:
            body.append(line)
    if head is not None:
        notes.append(Note(head[0], head[1], "\n".join(body).strip()))
    return notes


def first_sentence(text: str, limit: int = 100) -> str:
    """The first sentence of a note on one line: whitespace collapsed, cut at the first sentence
    end, and cut again with an ellipsis when it is longer than `limit` cells."""
    s = " ".join(text.split())
    end = len(s)
    for sep in (". ", "! ", "? "):
        i = s.find(sep)
        if i != -1:
            end = min(end, i + 1)
    s = s[:end]
    if len(s) > limit:
        s = s[: max(1, limit - 1)].rstrip() + "…"
    return s


def clean_reply(text: str) -> str:
    """A reply as prose: fences, surrounding quotes and a leading heading go; any other line that
    starts with `#` loses its hashes, since `## tick` inside an entry would forge a heading when
    the notebook is read back."""
    s = (text or "").strip()
    if "```" in s:
        parts = s.split("```")
        blocks = [p for i, p in enumerate(parts) if i % 2 == 1]
        if blocks:
            s = max(blocks, key=len)
            head, _, rest = s.partition("\n")
            if head.strip().isalpha():  # a language tag
                s = rest
    s = s.strip()
    for open_, close in (('"', '"'), ("“", "”"), ("'", "'")):
        if len(s) > 1 and s.startswith(open_) and s.endswith(close):
            s = s[1:-1].strip()
    lines = s.splitlines()
    if lines and lines[0].lstrip().startswith("#"):
        lines = lines[1:]
    out = []
    for ln in lines:
        stripped = ln.lstrip()
        out.append(stripped.lstrip("#").lstrip() if stripped.startswith("#") else ln)
    return "\n".join(out).strip()


# --- the packet ---------------------------------------------------------------------
def remarks(prev_census: dict[str, int] | None, census: list[dict]) -> list[str]:
    """Computed facts the prompt puts under "Changes worth noting", so a sweep is never left to
    the model to spot: a strain under SWEEP_FROM of the population at the last entry (absent
    counts as nothing) and over SWEEP_TO now. Later detectors extend this."""
    if prev_census is None:
        return []
    total = sum(prev_census.values())
    out = []
    for r in census:
        was = prev_census.get(r["id"], 0) / total if total else 0.0
        if was < SWEEP_FROM and r["share"] > SWEEP_TO:
            if r["id"] in prev_census and total:
                out.append(f"{r['name']} went from {was:.0%} to {r['share']:.0%} of the population")
            else:
                out.append(f"{r['name']} was not in the census at the last entry and is {r['share']:.0%} of it now")
    return out


def sketch(dish, census: dict[str, int], names: dict[str, str]) -> dict:
    """A coarse text rendering of the dish: k×k tiles per glyph for the smallest k that keeps it
    within SKETCH_W columns. A block with cells shows its dominant strain as a letter, a–z by
    census rank (ties by id), `*` past z; the dominant strain is the one with most cells, ties to
    the smaller id, as the eyepiece draws it. A block with none shows its mean nutrient:
    blank under 0.02, `.` under 0.28, `:` under 0.5, `#` otherwise. Glass is blank."""
    k = 1
    while -(-dish.w // k) > SKETCH_W:
        k += 1
    rank = sorted(census, key=lambda s: (-census[s], s))
    letters = {s: LETTERS[i] if i < len(LETTERS) else "*" for i, s in enumerate(rank)}
    cells, nut, mask = dish.cells, dish.nutrient, dish.mask
    rows = []
    for by in range(0, dish.h, k):
        ys = range(by, min(by + k, dish.h))
        row = []
        for bx in range(0, dish.w, k):
            tiles = [(x, y) for y in ys for x in range(bx, min(bx + k, dish.w)) if mask[y][x]]
            if not tiles:
                row.append(" ")
                continue
            counts: dict[str, int] = {}
            for xy in tiles:
                cell = cells.get(xy)
                if cell is not None:
                    counts[cell.strain] = counts.get(cell.strain, 0) + 1
            if counts:
                top = min(counts, key=lambda s: (-counts[s], s))
                row.append(letters.get(top, "*"))
                continue
            mean = sum(nut[y][x] for x, y in tiles) / len(tiles)
            row.append(" " if mean < 0.02 else "." if mean < 0.28 else ":" if mean < 0.5 else "#")
        rows.append("".join(row).rstrip())
    return {"scale": k, "rows": rows, "legend": [(letters[s], names.get(s, s)) for s in rank]}


def compose(packet: dict, previous: dict | None) -> dict:
    """The packet the culture built, set against the baseline: what changed since the last entry,
    the census with each strain's share then, the sweep, the events after that entry, and the
    entry itself. Pure. With no baseline it is the first entry; across a seam nothing is compared."""
    m = packet["metrics"]
    census = [dict(r) for r in packet["census"]]
    events = list(packet.get("events") or [])
    since = None
    prev_census = None
    if previous:
        events = [e for e in events if e["t"] > previous["t"]]
        if previous.get("seam"):
            since = {"seam": True, "prev_tick": previous["tick"]}
        else:
            pm = previous.get("metrics") or {}
            prev_census = dict(previous.get("census") or {})
            ticks = packet["tick"] - previous["tick"]
            seconds = max(0.0, packet["t"] - previous["t"])
            pace = packet.get("tick_seconds") or 0.0
            since = {
                "seam": False,
                "prev_tick": previous["tick"],
                "ticks": ticks,
                "seconds": seconds,
                "wall": fmt_wait(seconds),
                "pace": fmt_wait(ticks * pace) if pace > 0 and ticks > 0 else None,
                "population": (pm.get("population", 0), m["population"]),
                "strains": (pm.get("strains", 0), m["strains"]),
                "shannon": (pm.get("shannon", 0.0), m["shannon"]),
                "dominance": (pm.get("dominance", 0.0), m["dominance"]),
            }
            for k in ("births", "starved", "lysed", "senescent", "killed", "arisen", "extinct"):
                since[k] = max(0, m.get(k, 0) - pm.get(k, 0))
            total = sum(prev_census.values())
            for r in census:
                r["was"] = prev_census[r["id"]] / total if total and r["id"] in prev_census else None
    more = None
    if len(census) > CENSUS_ROWS:
        more = (len(census) - CENSUS_ROWS, sum(r["cells"] for r in census[CENSUS_ROWS:]))
    return {
        **packet,
        "census": census[:CENSUS_ROWS],
        "more": more,
        "since": since,
        "remarks": remarks(prev_census, census),
        "events": events[-LOG_LINES:],
        "previous": {"tick": previous["tick"], "text": previous["text"]} if previous else None,
    }


def _baseline(d) -> dict:
    """A baseline as the naturalist keeps it, from dish.json or a `note` event's data; {} when
    there is none. Tolerant of missing keys: an older vessel has none of them."""
    if not isinstance(d, dict) or "tick" not in d or "text" not in d:
        return {}
    metrics = d.get("metrics") if isinstance(d.get("metrics"), dict) else {}
    census = d.get("census") if isinstance(d.get("census"), dict) else {}
    try:
        t = float(d["at"] if "at" in d else d.get("t") or 0.0)
        return {
            "tick": int(d["tick"]),
            "t": t,
            "text": str(d["text"]),
            "branch": int(d.get("branch") or 0),
            "seam": bool(d.get("seam", False)),
            "metrics": {k: metrics[k] for k in METRIC_KEYS if k in metrics},
            "census": {str(k): int(v) for k, v in census.items()},
        }
    except (TypeError, ValueError):
        return {}


# --- the thread ---------------------------------------------------------------------
class Naturalist(threading.Thread):
    def __init__(self, mind: Mind, seed: str, log: Callable[..., None]):
        super().__init__(daemon=True, name="naturalist")
        self.mind = mind
        self.seed = seed
        self.log = log
        self.clock: Callable[[], float] = time.time  # the wall clock; tests turn it by hand
        self.lock = threading.Lock()  # guards pending and last; never held across a call
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.pending: dict | None = None  # the one slot: the newest packet not yet written
        self.last: dict = {}  # the baseline: the last note written and what it measured; {} before the first
        self.last_look = -math.inf  # clock time of the last packet handed over: the wall-clock floor
        self.failures = 0  # consecutive failed calls
        self.retry_at = 0.0  # clock time before which no note is attempted
        self.written = 0
        self.dropped = 0  # packets replaced in the slot before they were written
        self.silenced = False  # the budget went while it was looking: said once, quiet after

    # --- called from the dish thread ----------------------------------------------
    def due(self, tick: int) -> bool:
        """Whether this tick is a look: on the cadence, with an awake mind, not silenced, not
        backing off, and at least NOTES_MIN_SECONDS after the last look. Cheap; every tick asks."""
        every = config.NOTES_EVERY
        if not every or tick % every or self.silenced or not self.mind.awake:
            return False
        now = self.clock()
        return now >= self.retry_at and now - self.last_look >= config.NOTES_MIN_SECONDS

    def observe(self, packet: dict) -> None:
        """Hand a packet over. It replaces one not yet written; it never waits."""
        with self.lock:
            if self.pending is not None:
                self.dropped += 1
            self.pending = packet
            self.last_look = self.clock()
        self.wake.set()

    def latest(self) -> dict | None:
        """The last note: tick, the time it observed, and its text; None before the first."""
        with self.lock:
            if not self.last:
                return None
            return {"tick": self.last["tick"], "t": self.last["t"], "text": self.last["text"]}

    def baseline(self) -> dict:
        """A copy of the baseline, for dish.json and every dish sample; {} before the first note."""
        with self.lock:
            return copy.deepcopy(self.last) if self.last else {}

    def restore(self, d) -> None:
        """Take up a baseline saved with a dish. None or {} is no note yet."""
        with self.lock:
            self.last = _baseline(d)

    def reconcile(self, ev: dict) -> None:
        """Take the baseline from the last `note` event when it observed later than the one saved:
        a process killed between saves left its notes in the log and the notebook, not in dish.json."""
        b = _baseline(ev)
        if not b:
            return
        with self.lock:
            if b["t"] > self.last.get("t", -math.inf):
                self.last = b

    def reset(self) -> None:
        """The dish was replaced from the freezer: a pending packet described the old one and is
        dropped, and the baseline is marked with a seam, so the next entry compares nothing with
        it and says the dish was replaced. Writing that entry clears the seam."""
        with self.lock:
            self.pending = None
            if self.last:
                self.last["seam"] = True

    # --- the thread -----------------------------------------------------------------
    def run(self) -> None:
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
        """One pass: take the slot and write it, unless backing off, in which case the packet waits
        (and is replaced by a newer one when the dish hands it over). Returns True when told to stop."""
        if self.stop.is_set():
            return True
        if self.clock() < self.retry_at:
            return False  # run()'s two-second wake bounds the poll
        with self.lock:
            packet, self.pending = self.pending, None
        if packet is None:
            return False
        try:
            self._write(packet)
        except Exception as e:  # noqa: BLE001 — the thread must outlive any single fault
            self._fail(
                f"field note at tick {packet.get('tick', '?')} not written: naturalist fault: {type(e).__name__}: {e}"
            )
        return False

    def _write(self, packet: dict) -> bool:
        """Compose the packet against the baseline, ask the mind, append the entry, log it, and
        make it the new baseline. Synchronous, so tests run it on the main thread. Returns whether
        an entry was written."""
        tick = packet["tick"]
        with self.lock:
            previous = copy.deepcopy(self.last) if self.last else None
        composed = compose(packet, previous)
        try:
            reply = self.mind.think(
                prompts.NATURALIST_SYSTEM,
                prompts.naturalist_user(composed),
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                role="naturalist",
            )
        except Dormant:
            return False
        except Exhausted:
            self._silence(tick)
            return False
        except MindError as e:
            self._fail(f"field note at tick {tick} not written: {e}", status=e.status, retry_after=e.retry_after)
            return False
        self.failures = 0
        self.retry_at = 0.0
        text = clean_reply(reply)
        if not text:
            self.log("mind", f"field note at tick {tick} was empty — nothing written")
            return False
        try:
            append_note(config.FIELDNOTES, self.seed, tick, packet["t"], text)
        except OSError as e:
            self.log("mind", f"field note at tick {tick} not written: {e}")
            return False
        new = {
            "tick": tick,
            "t": packet["t"],
            "text": text,
            "branch": int(packet.get("branch") or 0),
            "seam": False,
            "metrics": {k: packet["metrics"].get(k, 0) for k in METRIC_KEYS},
            "census": {r["id"]: r["cells"] for r in packet["census"]},
        }
        with self.lock:
            self.last = new
            self.written += 1
        # the whole baseline rides on the event, so a kill between saves loses nothing (reconcile);
        # tick and at are the observation's, not the dish clock's when the reply came back
        self.log(
            "note",
            first_sentence(text),
            tick=tick,
            at=new["t"],
            text=text,
            branch=new["branch"],
            metrics=new["metrics"],
            census=new["census"],
        )
        return True

    def _fail(self, msg: str, *, status: int | None = None, retry_after: float | None = None) -> None:
        """Record a failed call and schedule the next attempt, as the mutagen does."""
        self.failures += 1
        wait = backoff(self.failures)
        if retry_after:
            wait = max(wait, min(retry_after, config.RETRY_AFTER_MAX))
        self.retry_at = self.clock() + wait
        self.log(
            "mind",
            f"{msg} — no note before {fmt_wait(wait)}",
            status=status,
            retry_in=wait,
            failures=self.failures,
            latency=self.mind.last_latency,
        )

    def _last_resort(self, e: BaseException) -> None:
        self.failures += 1
        self.retry_at = self.clock() + config.MUTAGEN_BACKOFF_MAX
        with contextlib.suppress(Exception):  # nowhere left to say it
            self.log(
                "mind",
                f"naturalist fault: {type(e).__name__}: {e} — no note before {fmt_wait(config.MUTAGEN_BACKOFF_MAX)}",
                retry_in=config.MUTAGEN_BACKOFF_MAX,
                failures=self.failures,
            )

    def _silence(self, tick: int) -> None:
        """The budget is spent: said once, and no look is due again in this process. A raised
        budget arrives with a new process, which starts unsilenced."""
        if self.silenced:
            return
        self.silenced = True
        spent, budget = self.mind.spent_usd, self.mind.budget_usd
        self.log(
            "mind",
            f"field notes end at tick {tick} — budget spent ({fmt_budget(spent, budget)})",
            spent_usd=spent,
            budget_usd=budget,
        )

    def close(self) -> None:
        self.stop.set()
        self.wake.set()
