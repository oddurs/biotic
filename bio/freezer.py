"""The freezer: samples of the dish and of strains, kept on disk under vessel/freezer/.

This module knows the file format, the naming rules, and how to list and find samples.
Freezing and reviving — what goes into a sample and what happens when it thaws — is the
culture's business (see Culture.freeze, Culture.revive and friends).

Two kinds of sample:

  <tick:08d>-<label>.json.gz   a dish sample: the whole dish, the culture's own state, and the
                               strain registry at that tick. Gzipped JSON.
  strain-<id>[-<label>].json   a strain sample: one genome, its lineage, and one cell's memory
                               (tuples and non-string keys tagged; docs/freezer.md). Plain JSON,
                               small enough to read and edit by hand.

Nothing in the freezer is ever overwritten: a second sample with the same name gets -2, -3, ...
"""

from __future__ import annotations

import gzip
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from . import config

FORMAT = 1
KINDS = ("dish", "strain")
_LABEL = re.compile(r"^[a-z0-9_-]{1,32}$")
_DISH_STEM = re.compile(r"^(\d{8})-[a-z0-9_-]+$")  # a dish sample's name; the tick is all it is asked for


def version() -> str:
    try:
        from importlib.metadata import version as v

        return v("biotic")
    except Exception:  # noqa: BLE001 — a checkout that was never installed
        return "0"


# --- names ------------------------------------------------------------------
def clean_label(label: str) -> str:
    label = (label or "").strip().lower()
    if not _LABEL.match(label):
        raise ValueError(f"a label is 1-32 characters of a-z, 0-9, _ and -; got {label!r}")
    return label


def stem(tick: int, label: str) -> str:
    return f"{tick:08d}-{label}"


def strain_stem(sid: str, label: str | None) -> str:
    return f"strain-{sid}-{label}" if label else f"strain-{sid}"


def stem_of(path: Path) -> str:
    name = path.name
    for suffix in (".json.gz", ".json"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def unique_path(path: Path) -> Path:
    """The path itself if free, else the first of -2, -3, ... that is."""
    if not path.exists():
        return path
    base = stem_of(path)
    suffix = path.name[len(base) :]
    n = 2
    while True:
        cand = path.with_name(f"{base}-{n}{suffix}")
        if not cand.exists():
            return cand
        n += 1


# --- files ------------------------------------------------------------------
def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_tick(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _is_size(v) -> bool:
    return _is_tick(v) and v > 0


def _is_record(v) -> bool:
    return isinstance(v, dict)


# What read() checks beyond presence: every reader — the listing, resolve(), Culture.revive() and
# germinate() — does arithmetic and formatting with these, so a hand edit that changes a field's
# type is refused here, by name, instead of surfacing as a traceback in one of them.
_SHAPE: dict[str, tuple] = {
    "seed": (lambda v: isinstance(v, str), "text"),
    "tick": (_is_tick, "a tick (an integer, 0 or more)"),
    "label": (lambda v: v is None or isinstance(v, str), "text or null"),
    "frozen_at": (lambda v: v is None or _is_number(v), "a time (a number)"),
    "dish": (_is_record, "a record"),
    "strains": (_is_record, "a record"),
    "culture": (_is_record, "a record"),
    "strain": (_is_record, "a record"),
    "memory": (lambda v: v is None or _is_record(v), "a record"),
    "w": (_is_size, "a size (an integer, 1 or more)"),
    "h": (_is_size, "a size (an integer, 1 or more)"),
}


def write(doc: dict, path: Path) -> Path:
    """Write a sample: gzipped if the name ends in .gz, plain JSON otherwise. Written to a
    temporary file first and moved into place, so a crash never leaves half a sample."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        if path.name.endswith(".gz"):
            with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as f:
                json.dump(doc, f)
        else:
            tmp.write_text(json.dumps(doc, indent=1))
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)  # a failed write leaves nothing behind, not even the half
        raise
    return path


def read(path: Path) -> dict:
    """Read and check a sample. Raises ValueError for anything that is not a sample this
    version understands."""
    try:
        if path.name.endswith(".gz"):
            with gzip.open(path, "rt", encoding="utf-8") as f:
                doc = json.load(f)
        else:
            doc = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise ValueError(f"{path.name} is not a readable sample: {e}") from None
    if not isinstance(doc, dict) or not isinstance(doc.get("format"), int):
        raise ValueError(f"{path.name} is not a sample")
    if doc["format"] > FORMAT:
        raise ValueError(f"{path.name} is format {doc['format']}; this biotic reads up to {FORMAT}")
    kind = doc.get("kind")
    if kind not in KINDS:
        raise ValueError(f"{path.name} has unknown kind {kind!r}")
    need = ("dish", "strains", "culture") if kind == "dish" else ("strain", "w", "h")
    for k in ("seed", "tick") + need:
        if k not in doc:
            raise ValueError(f"{path.name} is missing {k!r}")
    for k, (accepts, what) in _SHAPE.items():
        if k in doc and not accepts(doc[k]):
            raise ValueError(f"{path.name}: {k!r} is not {what}")
    return doc


# --- listing ----------------------------------------------------------------
@dataclass
class Entry:
    path: str
    stem: str
    kind: str
    tick: int
    label: str | None
    seed: str
    frozen_at: float
    population: int | None = None
    strains_living: int | None = None
    strains_total: int | None = None
    revived_from: int | None = None
    strain_id: str | None = None
    strain_name: str | None = None
    generation: int | None = None
    size: int = 0


def _entry(path: Path) -> Entry | None:
    try:
        doc = read(path)
    except ValueError:
        return None
    e = Entry(
        path=str(path),
        stem=stem_of(path),
        kind=doc["kind"],
        tick=int(doc["tick"]),
        label=doc.get("label"),
        seed=str(doc["seed"]),
        frozen_at=float(doc.get("frozen_at") or 0.0),
        size=path.stat().st_size,
    )
    if e.kind == "dish":
        e.population = doc.get("population")
        e.strains_living = doc.get("strains_living")
        e.strains_total = doc.get("strains_total")
        chain = doc.get("revivals") or []
        if chain:
            e.revived_from = chain[-1].get("from")
    else:
        s = doc["strain"]
        e.strain_id = s.get("id")
        e.strain_name = s.get("name")
        e.generation = s.get("generation")
    return e


def files() -> list[Path]:
    if not config.FREEZER.is_dir():
        return []
    return sorted(
        (p for p in config.FREEZER.iterdir() if p.is_file() and p.name.endswith((".json", ".json.gz"))),
        key=lambda p: (stem_of(p), p.name),
    )


def stems() -> list[str]:
    """Sample names from the directory listing alone: cheap enough for `biotic status`."""
    return [stem_of(p) for p in files()]


def dish_ticks() -> list[int]:
    out = []
    for s in stems():
        m = _DISH_STEM.match(s)
        if m:
            out.append(int(m.group(1)))
    return sorted(out)


def entries() -> list[Entry]:
    """Every sample, read: dishes by (tick, time frozen), then strains by the same."""
    es = [e for e in (_entry(p) for p in files()) if e is not None]
    dishes = sorted((e for e in es if e.kind == "dish"), key=lambda e: (e.tick, e.frozen_at))
    strains = sorted((e for e in es if e.kind == "strain"), key=lambda e: (e.tick, e.frozen_at))
    return dishes + strains


def _label(path: Path) -> str | None:
    """The label a dish sample stores. Not parsed from the name: a label may itself end in
    -<digits> (run-2), which the name cannot tell from the -2 a second sample gets."""
    try:
        return read(path).get("label")
    except ValueError:
        return None


def resolve(key: str, label: str | None = None, kind: str | None = None) -> Path:
    """Find one sample from what a person typed: a path to a sample, a sample's name, a tick
    (dish samples) or a strain id (strain samples). `label` narrows a tick to the samples with
    that label; `kind` ("dish" or "strain") says which of the two a bare key is, since a strain
    id can be all digits. Exactly one match, or LookupError says what to try."""
    key = key.strip()
    p = Path(key)
    if os.sep in key or key.endswith((".json", ".json.gz")):
        if p.is_file():
            return p
        if os.sep in key:
            raise LookupError(f"no such file {key}")
    for suffix in (".json.gz", ".json"):
        if key.endswith(suffix):
            key = key[: -len(suffix)]
    for suffix in (".json.gz", ".json"):
        cand = config.FREEZER / f"{key}{suffix}"
        if cand.is_file():
            return cand
    if kind != "strain" and key.isdigit():
        tick = int(key)
        hits = [p for p in files() if p.name.endswith(".json.gz") and p.name.startswith(f"{tick:08d}-")]
        what = f"nothing frozen at tick {tick}"
        if label:
            hits = [p for p in hits if _label(p) == label]
            what += f" with label {label}"
    elif kind != "dish":
        hits = [
            p
            for p in files()
            if p.name.endswith(".json")
            and (p.name == f"strain-{key}.json" or p.name.startswith(f"strain-{key}-"))
            and not p.name.endswith(".json.gz")
        ]
        what = f"no strain sample {key}"
    else:
        hits, what = [], f"no dish sample {key}"
    if not hits:
        raise LookupError(what + (" — `biotic freezer` lists what there is" if files() else " — the freezer is empty"))
    if len(hits) > 1:
        raise LookupError("say which: " + ", ".join(stem_of(p) for p in hits))
    return hits[0]


def when(t: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(t)) if t else "?"
