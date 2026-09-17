"""Strains: lineage, color, and the fossil record in vessel/soma/."""

from __future__ import annotations

import colorsys
import hashlib
import json
import random
import re
from dataclasses import MISSING, asdict, dataclass, fields

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
    mutagen: str | None = None  # what produced it: "llm", "random", "hgt", or null for a founder


class Registry:
    def __init__(self, seed: str = ""):
        self.strains: dict[str, Strain] = {}
        self._rng = random.Random(f"{seed}::hue")
        self._n = 0

    # --- creation -----------------------------------------------------------
    def new(
        self, source: str, parent: str | None, tick: int, name: str, note: str, mutagen: str | None = None
    ) -> Strain:
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
        s = Strain(sid, parent, cname, note.strip()[:200], source, tick, hue, generation=gen, mutagen=mutagen)
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
        config.SOMA.mkdir(parents=True, exist_ok=True)  # soma is nested under the vessel now
        parent = self.strains.get(s.parent) if s.parent else None
        lineage = f"from {parent.name} ({parent.id})" if parent else "the founding cell"
        # the header's prose name for the arm; docs/mutagen.md calls the LLM arm "semantic"
        arm = {"llm": "semantic"}.get(s.mutagen, s.mutagen)
        origin = f" by the {arm} mutagen" if s.mutagen else ""
        header = (
            f'"""strain {s.id} — {s.name}\n\n'
            f"generation {s.generation}, arose at tick {s.born}, {lineage}{origin}.\n"
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
    def to_dict(self) -> dict:
        return {"n": self._n, "rng": self._rng.getstate(), "strains": [asdict(s) for s in self.strains.values()]}

    @classmethod
    def from_dict(cls, seed: str, d: dict) -> Registry:
        reg = cls(seed)
        reg._n = d.get("n", 0)
        try:
            st = d["rng"]
            reg._rng.setstate((st[0], tuple(st[1]), st[2]))
        except Exception:  # noqa: BLE001
            pass
        for sd in d.get("strains", []):
            s = _strain_from(sd)
            reg.strains[s.id] = s
        return reg

    def save(self) -> None:
        config.STRAINS_FILE.write_text(json.dumps(self.to_dict()))

    @classmethod
    def load(cls, seed: str) -> Registry:
        if not config.STRAINS_FILE.exists():
            return cls(seed)
        return cls.from_dict(seed, json.loads(config.STRAINS_FILE.read_text()))

    def check(self, sd: dict) -> None:
        """Whether adopt() would take this record: every field a Strain needs is there, and its
        id is free or already holds the same genome. Raises ValueError; changes nothing, so a
        caller can ask before it does anything it would rather not undo."""
        check_record(sd)
        have = self.strains.get(sd["id"])
        if have is not None and have.source != sd["source"]:
            raise ValueError(f"strain id {sd['id']} is already taken by a different genome")

    def adopt(self, sd: dict, tick: int) -> Strain:
        """Take in a strain from a sample. Its id, name, note, genome, hue and generation are kept;
        it is born now, with no peak and not extinct. A strain already registered under that id
        with the same genome is simply marked living again; a different genome under the same
        id is refused (see check)."""
        self.check(sd)
        have = self.strains.get(sd["id"])
        if have is not None:
            have.extinct_at = None
            return have
        s = _strain_from({**sd, "born": tick, "extinct_at": None, "peak": 0})
        if any(x.name == s.name for x in self.strains.values()):
            s.name = f"{s.name[: NAME_MAX - 5]}_{s.id}"  # still a name check_record admits
        self.strains[s.id] = s
        self.fossilize(s)
        return s


_FIELDS = {f.name for f in fields(Strain)}
_REQUIRED = [f.name for f in fields(Strain) if f.default is MISSING and f.default_factory is MISSING]
NAME_MAX = 64
_ID = re.compile(r"^[0-9a-f]{4}$")  # what new() derives: four hex characters
_NAME = re.compile(rf"^[a-z0-9_]{{1,{NAME_MAX}}}$")  # what _clean_name() makes, with room for the _<id> a clash adds


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_tick(v) -> bool:
    return _is_int(v) and v >= 0


def _is_id(v) -> bool:
    return isinstance(v, str) and bool(_ID.match(v))


def _is_hue(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0.0 <= v < 1.0


# field -> (accepts, what a refusal calls it). Every field a Strain has, so a record is taken
# only when each value is what the culture will do arithmetic, file names and colours with.
_SHAPE: dict[str, tuple] = {
    "id": (_is_id, "a strain id (four hex characters)"),
    "parent": (lambda v: v is None or _is_id(v), "a strain id or null"),
    "name": (
        lambda v: isinstance(v, str) and bool(_NAME.match(v)),
        f"a strain name (a-z, 0-9 and _, up to {NAME_MAX})",
    ),
    "note": (lambda v: isinstance(v, str), "text"),
    "source": (lambda v: isinstance(v, str), "a genome (text)"),
    "born": (_is_tick, "a tick (an integer, 0 or more)"),
    "hue": (_is_hue, "a hue (a number from 0 up to, not including, 1)"),
    "extinct_at": (lambda v: v is None or _is_tick(v), "a tick or null"),
    "peak": (_is_tick, "a count (an integer, 0 or more)"),
    "generation": (_is_tick, "a generation (an integer, 0 or more)"),
    "mutagen": (lambda v: v is None or v in ("llm", "random", "hgt"), "an origin: llm, random, hgt or null"),
}
assert set(_SHAPE) == _FIELDS


def check_record(sd: dict) -> None:
    """A strain record — from a sample, or from strains.json — must carry every field a Strain
    has no default for, and every field it carries must be what a Strain holds there: adopt()
    and from_dict() take the values as they are, the culture sums generations and subtracts
    birth ticks, and the id names a fossil under vessel/soma/. Samples are edited by hand; a missing
    or malformed field is a refusal that names it, before anything is frozen or written, not
    a traceback ticks later."""
    if not isinstance(sd, dict):
        raise ValueError("strain record is not a record")
    missing = [k for k in _REQUIRED if k not in sd]
    if missing:
        raise ValueError(f"strain record is missing {', '.join(repr(k) for k in missing)}")
    for k, (accepts, what) in _SHAPE.items():
        if k in sd and not accepts(sd[k]):
            got = repr(sd[k])
            raise ValueError(f"strain record {k!r} is not {what}: {got if len(got) <= 40 else got[:37] + '...'}")


def _strain_from(sd: dict) -> Strain:
    """A Strain from a dict, ignoring keys this version does not know."""
    check_record(sd)
    d = {k: v for k, v in sd.items() if k in _FIELDS}
    d["hue"] = float(d["hue"])  # JSON may carry 0 as an integer
    return Strain(**d)


def _clean_name(name: str) -> str:
    name = re.sub(r"[^a-z0-9_]+", "_", (name or "").strip().lower()).strip("_")
    return name[:28]
