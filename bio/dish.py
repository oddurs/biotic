"""The dish: agar, cells, physics.

Knows nothing about language models. A cell is a position, an energy level,
and a strain id; the strain id resolves to a genome, and the genome is a
`live(me)` function that gets called once per tick.
"""

from __future__ import annotations

import copy
import math
import random
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from . import config
from .membrane import Budget, Lysis, compile_genome, memory_fault

# clockwise from north
DIRS = [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]
DIR_NAMES = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

_ALIASES = {"split": "divide", "sleep": "rest", "wait": "rest", "stay": "rest", "go": "move", "feed": "eat"}
_COERCE_ERRORS = (TypeError, ValueError, OverflowError)  # int(nan), int(inf), float(10**400), int(None)


def parse_action(out):
    """Coerce whatever a genome returned into (kind, arg), or None if nonsense."""
    if out is None:
        return ("rest", None)
    if isinstance(out, bool):
        return None
    if isinstance(out, (int, float)):
        try:
            return ("move", int(out) % 8)
        except _COERCE_ERRORS:
            return None
    if isinstance(out, str):
        s = _ALIASES.get(out.strip().lower(), out.strip().lower())
        if s in ("eat", "rest", "divide"):
            return (s, None)
        return None
    if isinstance(out, (tuple, list)) and 1 <= len(out) <= 2:
        kind, arg = out[0], (out[1] if len(out) > 1 else None)
        if not isinstance(kind, str):
            return None
        kind = _ALIASES.get(kind.strip().lower(), kind.strip().lower())
        try:
            if isinstance(arg, bool) and kind in ("move", "divide", "emit"):
                return None  # int(True) is 1 and float(True) is 1.0, but a bool is neither a direction nor an amount
            if kind == "move":
                return ("move", int(arg) % 8)
            if kind == "divide":
                return ("divide", None if arg is None else int(arg) % 8)
            if kind == "emit":
                x = 0.2 if arg is None else float(arg)
                if x != x:  # nan: nonsense, not "emit everything"
                    return None
                return ("emit", max(0.0, min(1.0, x)))
            if kind in ("eat", "rest"):
                return (kind, None)
        except _COERCE_ERRORS:
            return None
    return None


@dataclass
class Cell:
    x: int
    y: int
    strain: str
    energy: float
    age: int = 0
    born: int = 0
    memory: dict = field(default_factory=dict)


class Me:
    """What a cell can perceive. Rebuilt every tick; genomes only see this."""

    __slots__ = (
        "energy",
        "age",
        "here",
        "around",
        "crowd",
        "kin",
        "scent",
        "scent_here",
        "memory",
        "rng",
        "tick",
        "strain",
        "population",
    )

    def __init__(self, cell: Cell, dish: Dish):
        self.energy = cell.energy
        self.age = cell.age
        self.tick = dish.tick
        self.strain = cell.strain
        self.population = len(dish.cells)
        self.memory = cell.memory
        self.rng = dish.rng
        self.here = dish.nutrient[cell.y][cell.x]
        self.scent_here = dish.pheromone[cell.y][cell.x]
        around, crowd, kin, scent = [], [], [], []
        for dx, dy in DIRS:
            x, y = cell.x + dx, cell.y + dy
            if dish.inside(x, y):
                around.append(dish.nutrient[y][x])
                scent.append(dish.pheromone[y][x])
                other = dish.cells.get((x, y))
                crowd.append(other is not None)
                kin.append(other is not None and other.strain == cell.strain)
            else:  # the glass wall
                around.append(0.0)
                scent.append(0.0)
                crowd.append(True)
                kin.append(False)
        self.around, self.crowd, self.kin, self.scent = around, crowd, kin, scent


class Dish:
    def __init__(self, seed: str, width: int = config.WIDTH, height: int = config.HEIGHT, flask: str = ""):
        self.seed = seed
        self.flask = flask  # "" for a lone dish; a flask id (e.g. "03") for one replicate of many
        self.w, self.h = width, height
        # The agar is a function of the seed alone (_make_agar), so replicates of one seed share
        # it exactly; a per-flask salt on the dynamics RNG is the only source of divergence, and
        # an empty flask keeps the exact bytes a lone dish has always used (docs/flasks.md).
        tag = f"{seed}::{flask}" if flask else seed
        self.rng = random.Random(f"{tag}::dish")
        self.tick = 0
        self.cells: dict[tuple[int, int], Cell] = {}
        self.genomes: dict[str, str] = {}
        self._compiled: dict[str, Callable] = {}
        self.mask = self._make_mask()
        self.nutrient = self._make_agar()
        self.pheromone = [[0.0] * self.w for _ in range(self.h)]
        self.history: deque[int] = deque(maxlen=600)
        self.deaths = {"starved": 0, "lysed": 0, "senescent": 0, "killed": 0}
        self.births = 0
        self.replenish = config.REPLENISH
        # hooks the culture installs
        self.on_divide: Callable[[Cell], tuple[str, str] | None] | None = None
        self.on_death: Callable[[Cell, str], None] | None = None

    # --- geometry -----------------------------------------------------------
    def _make_mask(self):
        cx, cy = (self.w - 1) / 2, (self.h - 1) / 2
        rx, ry = self.w / 2, self.h / 2
        return [[((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0 for x in range(self.w)] for y in range(self.h)]

    def inside(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h and self.mask[y][x]

    @property
    def tiles(self) -> int:
        return sum(sum(1 for v in row if v) for row in self.mask)

    def center(self) -> tuple[int, int]:
        return self.w // 2, self.h // 2

    # --- agar ---------------------------------------------------------------
    def _make_agar(self):
        rng = random.Random(f"{self.seed}::agar")
        blobs = [
            (rng.uniform(0, self.w), rng.uniform(0, self.h), rng.uniform(4, 14), rng.uniform(0.3, 1.0))
            for _ in range(9)
        ]
        grid = []
        for y in range(self.h):
            row = []
            for x in range(self.w):
                if not self.mask[y][x]:
                    row.append(0.0)
                    continue
                v = config.AGAR_MEAN * (1 - config.AGAR_PATCHINESS)
                for bx, by, br, bs in blobs:
                    d2 = ((x - bx) / 2) ** 2 + (y - by) ** 2  # terminal cells are 2:1
                    v += config.AGAR_PATCHINESS * bs * math.exp(-d2 / (br * br))
                v += rng.gauss(0, 0.04)
                row.append(max(0.0, min(1.0, v)))
            grid.append(row)
        return grid

    def _mean(self, grid: list[list[float]]) -> float:
        tot = n = 0
        for y in range(self.h):
            for x in range(self.w):
                if self.mask[y][x]:
                    tot += grid[y][x]
                    n += 1
        return tot / n if n else 0.0

    def nutrient_mean(self) -> float:
        return self._mean(self.nutrient)

    def pheromone_mean(self) -> float:
        return self._mean(self.pheromone)

    # --- genomes ------------------------------------------------------------
    def register(self, strain: str, source: str) -> None:
        self.genomes[strain] = source
        self._compiled.pop(strain, None)

    def _fn(self, strain: str) -> Callable:
        fn = self._compiled.get(strain)
        if fn is None:
            fn = compile_genome(self.genomes[strain], self.rng)
            self._compiled[strain] = fn
        return fn

    # --- population ---------------------------------------------------------
    def place(
        self, x: int, y: int, strain: str, energy: float = config.INITIAL_ENERGY, memory: dict | None = None
    ) -> Cell | None:
        if not self.inside(x, y) or (x, y) in self.cells:
            return None
        c = Cell(x, y, strain, energy, born=self.tick, memory=_inherit(memory))
        self.cells[(x, y)] = c
        return c

    def inoculate(
        self, strain: str, n: int = config.INOCULUM, at: tuple[int, int] | None = None, memory: dict | None = None
    ) -> int:
        """Place up to `n` cells of `strain`, each with its own copy of `memory`. With no `at`, they
        scatter around the centre using the dish's own RNG (as at genesis). With `at`, they take
        the `n` free tiles nearest that point, in a fixed order, and the RNG is not touched."""
        if at is None:
            cx, cy = self.center()
            placed = 0
            tries = 0
            while placed < n and tries < 200:
                tries += 1
                x = cx + self.rng.randint(-2, 2)
                y = cy + self.rng.randint(-1, 1)
                if self.place(x, y, strain, memory=memory):
                    placed += 1
            return placed
        ax, ay = at
        free = [(x, y) for y in range(self.h) for x in range(self.w) if self.mask[y][x] and (x, y) not in self.cells]
        free.sort(key=lambda t: (((t[0] - ax) / 2) ** 2 + (t[1] - ay) ** 2, t[1], t[0]))
        placed = 0
        for x, y in free[:n]:
            if self.place(x, y, strain, memory=memory):
                placed += 1
        return placed

    def census(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for c in self.cells.values():
            out[c.strain] = out.get(c.strain, 0) + 1
        return out

    def metrics(self, census: dict[str, int] | None = None) -> dict:
        """What the dish can say about its own population: size, diversity, the death ledger.

        Shannon diversity H = -sum(p ln p) over the strain census, in nats, and dominance,
        the share of the commonest strain; both 0.0 for a sterile dish, and a monoculture
        reads H = 0.0, dominance = 1.0. Reads only; no registry, no mind, no RNG.
        """
        if census is None:
            census = self.census()
        total = sum(census.values())
        h = 0.0
        top = 0
        for n in census.values():
            if n <= 0:
                continue
            top = max(top, n)
            p = n / total
            h -= p * math.log(p)
        return {
            "tick": self.tick,
            "population": total,
            "strains": len(census),
            "nutrient": self.nutrient_mean(),
            "pheromone": self.pheromone_mean(),
            "shannon": h,
            "dominance": top / total if total else 0.0,
            "births": self.births,
            "starved": self.deaths.get("starved", 0),
            "lysed": self.deaths.get("lysed", 0),
            "senescent": self.deaths.get("senescent", 0),
            "killed": self.deaths.get("killed", 0),
        }

    def _die(self, cell: Cell, cause: str) -> None:
        self.cells.pop((cell.x, cell.y), None)
        self.deaths[cause] = self.deaths.get(cause, 0) + 1
        back = max(0.0, cell.energy) * config.NECROMASS + config.CORPSE_NUTRIENT
        self.nutrient[cell.y][cell.x] = min(1.0, self.nutrient[cell.y][cell.x] + back)
        if self.on_death:
            self.on_death(cell, cause)

    def lyse(self, strain: str) -> int:
        """Burst every cell of a strain and drop its genome. Returns how many cells burst."""
        n = 0
        for c in list(self.cells.values()):
            if c.strain == strain:
                self._die(c, "lysed")
                n += 1
        self.genomes.pop(strain, None)
        self._compiled.pop(strain, None)
        return n

    def kill_region(self, cx: int, cy: int, r: float) -> int:
        n = 0
        for (x, y), c in list(self.cells.items()):
            if ((x - cx) / 2) ** 2 + (y - cy) ** 2 <= r * r:
                self._die(c, "killed")
                n += 1
        return n

    def feed_region(self, cx: int, cy: int, r: float, amount: float = 0.6) -> None:
        for y in range(self.h):
            for x in range(self.w):
                if self.mask[y][x] and ((x - cx) / 2) ** 2 + (y - cy) ** 2 <= r * r:
                    self.nutrient[y][x] = min(1.0, self.nutrient[y][x] + amount)

    # --- the tick -----------------------------------------------------------
    def step(self) -> None:
        order = list(self.cells.values())
        self.rng.shuffle(order)
        for cell in order:
            if self.cells.get((cell.x, cell.y)) is not cell:
                continue  # died earlier this tick
            cell.age += 1
            cell.energy -= config.BASAL_COST
            try:
                me = Me(cell, self)
                with Budget(config.CELL_TIME_BUDGET):
                    out = self._fn(cell.strain)(me)
                    fault = memory_fault(cell.memory)  # the walk over what this cell built is charged to it
                action = parse_action(out)
                if action is None:
                    raise ValueError("unparseable action")
                if fault:
                    raise ValueError(fault)  # what the genome left in memory cannot be saved: lysis, before its action
                self._apply(cell, action)
            except (Lysis, Exception):  # noqa: BLE001 — anything a genome does wrong is lysis
                self._die(cell, "lysed")
                continue
            if cell.energy <= 0:
                self._die(cell, "starved")
            elif cell.age > config.MAX_AGE:
                self._die(cell, "senescent")
            elif cell.energy > config.MAX_ENERGY:
                cell.energy = config.MAX_ENERGY
        self._diffuse()
        self.tick += 1
        self.history.append(len(self.cells))

    def _apply(self, cell: Cell, action) -> None:
        kind, arg = action
        if kind == "eat":
            avail = self.nutrient[cell.y][cell.x]
            take = min(avail, config.EAT_RATE)
            self.nutrient[cell.y][cell.x] = avail - take
            cell.energy += take
        elif kind == "move":
            cell.energy -= config.MOVE_COST
            dx, dy = DIRS[arg]
            nx, ny = cell.x + dx, cell.y + dy
            if self.inside(nx, ny) and (nx, ny) not in self.cells:
                del self.cells[(cell.x, cell.y)]
                cell.x, cell.y = nx, ny
                self.cells[(nx, ny)] = cell
        elif kind == "divide":
            if cell.energy < config.DIVIDE_THRESHOLD:
                return
            dirs = [arg] if arg is not None else []
            rest = list(range(8))
            self.rng.shuffle(rest)
            for d in dirs + rest:
                dx, dy = DIRS[d]
                nx, ny = cell.x + dx, cell.y + dy
                if self.inside(nx, ny) and (nx, ny) not in self.cells:
                    strain = cell.strain
                    if self.on_divide:
                        mut = self.on_divide(cell)
                        if mut:
                            strain, source = mut
                            self.register(strain, source)
                    cell.energy /= 2
                    self.place(nx, ny, strain, cell.energy, cell.memory)
                    self.births += 1
                    return
        elif kind == "emit":
            cell.energy -= config.EMIT_COST
            self.pheromone[cell.y][cell.x] = min(1.0, self.pheromone[cell.y][cell.x] + arg)
        # rest: nothing

    def _diffuse(self) -> None:
        D, PD, decay, rep = config.DIFFUSION, config.PHEROMONE_DIFFUSION, config.PHEROMONE_DECAY, self.replenish
        nut, ph, mask = self.nutrient, self.pheromone, self.mask
        new_n = [row[:] for row in nut]
        new_p = [row[:] for row in ph]
        for y in range(self.h):
            for x in range(self.w):
                if not mask[y][x]:
                    continue
                sn = sp = 0.0
                k = 0
                for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < self.w and 0 <= yy < self.h and mask[yy][xx]:
                        sn += nut[yy][xx]
                        sp += ph[yy][xx]
                        k += 1
                if k:
                    new_n[y][x] = nut[y][x] * (1 - D) + D * sn / k
                    new_p[y][x] = (ph[y][x] * (1 - PD) + PD * sp / k) * (1 - decay)
                if rep:
                    new_n[y][x] = min(1.0, new_n[y][x] + rep)
        self.nutrient, self.pheromone = new_n, new_p

    # --- phase of growth ----------------------------------------------------
    def phase(self) -> str:
        """Read the growth curve the way a microbiologist would."""
        h = self.history
        if not h:
            return "lag"
        now = h[-1]
        if now == 0:
            return "sterile"
        if len(h) < 60:
            return "lag" if now < 40 else "log"
        recent = sum(list(h)[-10:]) / 10
        before = sum(list(h)[-60:-50]) / 10 or 1
        r = (recent - before) / before
        if now < 12 and abs(r) < 0.5:
            return "lag"
        if r > 0.10:
            return "log"
        if r < -0.10:
            return "death"
        return "stationary"

    # --- persistence --------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "seed": self.seed,
            "flask": self.flask,
            "w": self.w,
            "h": self.h,
            "tick": self.tick,
            "rng": self.rng.getstate(),
            "nutrient": self.nutrient,
            "pheromone": self.pheromone,
            "cells": [
                [c.x, c.y, c.strain, c.energy, c.age, c.born, encode_memory(c.memory)] for c in self.cells.values()
            ],
            "genomes": self.genomes,
            "history": list(self.history),
            "deaths": self.deaths,
            "births": self.births,
            "replenish": self.replenish,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Dish:
        # flask governs only the fresh RNG key; setstate below restores the running state, so it
        # is load-bearing only for a dish built and never stepped. Persisting it keeps a freeze
        # sample and dish.json self-describing about which replicate they came from.
        dish = cls(d["seed"], d["w"], d["h"], flask=d.get("flask", ""))
        dish.tick = d["tick"]
        try:
            st = d["rng"]
            dish.rng.setstate((st[0], tuple(st[1]), st[2]))
        except Exception:  # noqa: BLE001
            pass
        dish.nutrient = d["nutrient"]
        dish.pheromone = d["pheromone"]
        dish.genomes = d["genomes"]
        dish.history = deque(d.get("history", []), maxlen=600)
        dish.deaths = d.get("deaths", dish.deaths)
        dish.births = d.get("births", 0)
        dish.replenish = d.get("replenish", config.REPLENISH)
        for x, y, strain, energy, age, born, mem in d["cells"]:
            dish.cells[(x, y)] = Cell(x, y, strain, energy, age, born, decode_memory(mem or {}))
        return dish


# Memory is bounded in the tick: membrane.memory_fault runs on every cell's memory after every
# live(), and a cell that breaks the rule bursts. What is here is a faithful codec for what
# passes, not a bound: JSON cannot tell a tuple from a list or an int key from a str key, so the
# encoder tags those and the decoder undoes the tags.


def _inherit(memory: dict | None) -> dict:
    """What a new cell gets of the memory it is given: a deep copy, so a mother and her daughter
    never share a list or a dict. The shallow copy is for memory deepcopy cannot take; nothing
    that has lived a tick holds any (memory_fault admits only what deepcopy copies exactly), so
    it is reachable only from place() and inoculate() with hand-made memory."""
    if not memory:
        return {}
    try:
        return copy.deepcopy(memory)
    except Exception:  # noqa: BLE001
        return dict(memory)


def encode_memory(m: dict) -> dict:
    """A cell's memory as dish.json and a strain sample carry it.

    None, bools, ints, floats and strings are themselves; a list is a list; a tuple is
    {"~t": [items]}; a dict whose keys are all strings and none begins with "~" is a plain
    object, and any other dict is {"~d": [[key, value], ...]}, so an int key, a bool key or a
    key that happens to begin with "~" comes back as it was. Insertion order is kept. Everything
    memory_fault admits goes through exactly. Anything else — a set or a range in hand-made
    memory a test placed, never a cell that has lived a tick — is written as up to 80
    characters of its str(), so a save never fails on it.
    """
    if _plain(m):
        return {k: _value(v) for k, v in m.items()}
    return {"~d": [[_value(k), _value(v)] for k, v in m.items()]}


def decode_memory(d) -> dict:
    """The inverse of encode_memory, total on any JSON: {"~t": [...]} is a tuple, {"~d": [[k, v],
    ...]} is a dict with those keys, any other object is a dict with string keys, and anything
    malformed under a tag stays the plain JSON it is. Untagged input — a dish.json or a sample
    written before the tags, or by hand — comes back as JSON gives it. The result is a dict: a
    top level that is not one (a hand-edited {"~t": [...]}) is an empty memory."""
    m = _decode(d)
    return m if type(m) is dict else {}


def _plain(d: dict) -> bool:
    return all(type(k) is str and not k.startswith("~") for k in d)


def _value(v):
    try:
        return _encode(v)
    except RecursionError:  # nested past the interpreter's limit: never admitted, and not a save's problem
        return _text(v)[:80]


def _encode(v):
    t = type(v)
    if v is None or t is bool or t is int or t is float or t is str:
        return v
    if t is list:
        return [_encode(x) for x in v]
    if t is tuple:
        return {"~t": [_encode(x) for x in v]}
    if t is dict:
        if _plain(v):
            return {k: _encode(x) for k, x in v.items()}
        return {"~d": [[_encode(k), _encode(x)] for k, x in v.items()]}
    return _text(v)[:80]


def _decode(v):
    t = type(v)
    if t is list:
        return [_decode(x) for x in v]
    if t is not dict:
        return v
    if len(v) == 1:
        tag, body = next(iter(v.items()))
        if tag == "~t" and type(body) is list:
            return tuple(_decode(x) for x in body)
        if tag == "~d" and type(body) is list and all(type(p) is list and len(p) == 2 for p in body):
            try:
                return {_decode(k): _decode(x) for k, x in body}
            except TypeError:  # an unhashable key: not a dict the encoder wrote
                pass
    return {k: _decode(x) for k, x in v.items()}


def _text(v) -> str:
    """str(v), or a placeholder when str() itself refuses.

    An int past sys.get_int_max_str_digits() has no decimal form, and a container nested past
    the recursion limit has no repr. Neither survives a tick any more, but hand-made memory can
    hold either, and neither may stop a save.
    """
    try:
        return str(v)
    except (ValueError, RecursionError):
        return f"<{type(v).__name__}>"
