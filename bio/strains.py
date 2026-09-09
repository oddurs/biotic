"""Strains: lineage, color, and the fossil record in soma/."""

from __future__ import annotations

import colorsys
import hashlib
import json
import random
import re
from dataclasses import asdict, dataclass

from . import config


@dataclass
class Strain:
    id: str
    parent: str | None
    name: str
    note: str
    source: str
    born: int
    hue: float
    extinct_at: int | None = None
    peak: int = 0
    generation: int = 0


class Registry:
    def __init__(self, seed: str = ""):
        self.strains: dict[str, Strain] = {}
        self._rng = random.Random(f"{seed}::hue")
        self._n = 0

    # --- creation -----------------------------------------------------------
    def new(self, source: str, parent: str | None, tick: int, name: str, note: str) -> Strain:
        self._n += 1
        sid = hashlib.sha1(f"{self._n}:{source}".encode()).hexdigest()[:4]
        while sid in self.strains:
            sid = hashlib.sha1(f"{sid}:x".encode()).hexdigest()[:4]
        if parent and parent in self.strains:
            p = self.strains[parent]
            hue = (p.hue + self._rng.gauss(0, 0.07)) % 1.0
            gen = p.generation + 1
        else:
            hue = self._rng.random()
            gen = 0
        cname = _clean_name(name) or f"strain_{sid}"
        if any(x.name == cname for x in self.strains.values()):
            cname = f"{cname}_{sid}"
        s = Strain(sid, parent, cname, note.strip()[:200], source, tick, hue, generation=gen)
        self.strains[sid] = s
        self.fossilize(s)
        return s

    # --- color --------------------------------------------------------------
    def color(self, sid: str, energy: float = 1.0) -> str:
        s = self.strains.get(sid)
        hue = s.hue if s else 0.0
        light = 0.38 + 0.28 * max(0.0, min(1.0, energy / 1.2))
        r, g, b = colorsys.hls_to_rgb(hue, light, 0.72)
        return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

    # --- fossil record ------------------------------------------------------
    def fossilize(self, s: Strain) -> None:
        config.SOMA.mkdir(exist_ok=True)
        parent = self.strains.get(s.parent) if s.parent else None
        lineage = f"from {parent.name} ({parent.id})" if parent else "the founding cell"
        header = (
            f'"""strain {s.id} — {s.name}\n\n'
            f"generation {s.generation}, arose at tick {s.born}, {lineage}.\n"
            f"{s.note}\n"
            f'"""\n\n'
        )
        (config.SOMA / f"{s.id}_{s.name}.py").write_text(header + s.source.rstrip() + "\n")

    # --- bookkeeping --------------------------------------------------------
    def update(self, census: dict[str, int], tick: int) -> list[Strain]:
        """Record peaks; mark extinctions. Returns strains that just went extinct."""
        gone = []
        for s in self.strains.values():
            n = census.get(s.id, 0)
            if n > s.peak:
                s.peak = n
            if n == 0 and s.extinct_at is None and s.peak > 0:
                s.extinct_at = tick
                gone.append(s)
        return gone

    def living(self, census: dict[str, int]) -> list[tuple[Strain, int]]:
        rows = [(self.strains[sid], n) for sid, n in census.items() if sid in self.strains]
        rows.sort(key=lambda r: -r[1])
        return rows

    def lineage_of(self, sid: str) -> list[Strain]:
        out = []
        cur = self.strains.get(sid)
        while cur:
            out.append(cur)
            cur = self.strains.get(cur.parent) if cur.parent else None
        return list(reversed(out))

    # --- persistence --------------------------------------------------------
    def save(self) -> None:
        config.STRAINS_FILE.write_text(
            json.dumps(
                {"n": self._n, "rng": self._rng.getstate(), "strains": [asdict(s) for s in self.strains.values()]}
            )
        )

    @classmethod
    def load(cls, seed: str) -> Registry:
        reg = cls(seed)
        if not config.STRAINS_FILE.exists():
            return reg
        d = json.loads(config.STRAINS_FILE.read_text())
        reg._n = d.get("n", 0)
        try:
            st = d["rng"]
            reg._rng.setstate((st[0], tuple(st[1]), st[2]))
        except Exception:  # noqa: BLE001
            pass
        for sd in d["strains"]:
            reg.strains[sd["id"]] = Strain(**sd)
        return reg


def _clean_name(name: str) -> str:
    name = re.sub(r"[^a-z0-9_]+", "_", (name or "").strip().lower()).strip("_")
    return name[:28]
