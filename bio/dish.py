"""The dish: agar, cells, physics.

Knows nothing about language models. A cell is a position, an energy level,
and a strain id; the strain id resolves to a genome, and the genome is a
`live(me)` function that gets called once per tick.
"""

from __future__ import annotations

import math
import random
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from . import config
from .membrane import Budget, compile_genome

# clockwise from north
DIRS = [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]
DIR_NAMES = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

_ALIASES = {"split": "divide", "sleep": "rest", "wait": "rest", "stay": "rest", "go": "move", "feed": "eat"}


def parse_action(out):
    """Coerce whatever a genome returned into (kind, arg), or None if nonsense."""
    if out is None:
        return ("rest", None)
    if isinstance(out, bool):
        return None
    if isinstance(out, (int, float)):
        return ("move", int(out) % 8)
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
            if kind == "move":
                return ("move", int(arg) % 8)
            if kind == "divide":
                return ("divide", None if arg is None else int(arg) % 8)
            if kind == "emit":
                x = 0.2 if arg is None else float(arg)
                return ("emit", max(0.0, min(1.0, x)))
            if kind in ("eat", "rest"):
                return (kind, None)
        except (TypeError, ValueError):
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
    def __init__(self, seed: str, width: int = config.WIDTH, height: int = config.HEIGHT):
        self.seed = seed
        self.w, self.h = width, height
        self.rng = random.Random(f"{seed}::dish")
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

    def nutrient_mean(self) -> float:
        tot = n = 0
        for y in range(self.h):
            for x in range(self.w):
                if self.mask[y][x]:
                    tot += self.nutrient[y][x]
                    n += 1
        return tot / n if n else 0.0

    # --- genomes ------------------------------------------------------------
    def register(self, strain: str, source: str) -> None:
        self.genomes[strain] = source
        self._compiled.pop(strain, None)

    def _fn(self, strain: str) -> Callable:
        fn = self._compiled.get(strain)
        if fn is None:
            fn = compile_genome(self.genomes[strain])
            self._compiled[strain] = fn
        return fn

    # --- population ---------------------------------------------------------
    def place(
        self, x: int, y: int, strain: str, energy: float = config.INITIAL_ENERGY, memory: dict | None = None
    ) -> Cell | None:
        if not self.inside(x, y) or (x, y) in self.cells:
            return None
        c = Cell(x, y, strain, energy, born=self.tick, memory=dict(memory or {}))
        self.cells[(x, y)] = c
        return c

    def inoculate(self, strain: str, n: int = config.INOCULUM) -> int:
        cx, cy = self.center()
        placed = 0
        tries = 0
        while placed < n and tries < 200:
            tries += 1
            x = cx + self.rng.randint(-2, 2)
            y = cy + self.rng.randint(-1, 1)
            if self.place(x, y, strain):
                placed += 1
        return placed

    def census(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for c in self.cells.values():
            out[c.strain] = out.get(c.strain, 0) + 1
        return out

    def _die(self, cell: Cell, cause: str) -> None:
        self.cells.pop((cell.x, cell.y), None)
        self.deaths[cause] = self.deaths.get(cause, 0) + 1
        back = max(0.0, cell.energy) * config.NECROMASS + config.CORPSE_NUTRIENT
        self.nutrient[cell.y][cell.x] = min(1.0, self.nutrient[cell.y][cell.x] + back)
        if self.on_death:
            self.on_death(cell, cause)

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
                action = parse_action(out)
                if action is None:
                    raise ValueError("unparseable action")
                self._apply(cell, action)
            except Exception:  # noqa: BLE001 — anything a genome does wrong is lysis
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
            "w": self.w,
            "h": self.h,
            "tick": self.tick,
            "rng": self.rng.getstate(),
            "nutrient": self.nutrient,
            "pheromone": self.pheromone,
            "cells": [
                [c.x, c.y, c.strain, round(c.energy, 4), c.age, c.born, _jsonable(c.memory)]
                for c in self.cells.values()
            ],
            "genomes": self.genomes,
            "history": list(self.history),
            "deaths": self.deaths,
            "births": self.births,
            "replenish": self.replenish,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Dish:
        dish = cls(d["seed"], d["w"], d["h"])
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
            dish.cells[(x, y)] = Cell(x, y, strain, energy, age, born, mem or {})
        return dish


def _jsonable(m: dict) -> dict:
    out = {}
    for k, v in list(m.items())[:64]:
        if isinstance(v, (int, float, str, bool)) or v is None:
            out[str(k)] = v
        else:
            out[str(k)] = str(v)[:80]
    return out
