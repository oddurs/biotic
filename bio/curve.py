"""The growth curve: what vessel/curve.csv holds, how it is written, how it is read.

One row every CADENCE ticks. Columns are only ever appended. A file written by an
older apparatus is widened in place, once, with empty cells for what it did not
record. Markers (drops, revives, incubation gaps) belong in events.jsonl, not here.
"""

from __future__ import annotations

import csv
from pathlib import Path

from . import config

CADENCE = 10  # ticks between rows

COLUMNS: tuple[str, ...] = (
    # the original nine, in their original order
    "tick",
    "population",
    "strains",
    "nutrient",
    "phase",
    "births",
    "starved",
    "lysed",
    "senescent",
    # diversity and turnover
    "killed",
    "shannon",
    "dominance",
    "mean_gen",
    "arisen",
    "extinct",
    "pheromone",
    "mutations_ready",
    "mutations_taken",
)
DECIMALS = {"nutrient": 4, "shannon": 4, "dominance": 4, "mean_gen": 2, "pheromone": 4}
_INT = frozenset(COLUMNS) - frozenset(DECIMALS) - {"phase"}


def _header(path: Path) -> list[str] | None:
    """The header row of an existing file; None if the file is absent or empty."""
    if not path.exists():
        return None
    with open(path, newline="") as f:
        return next(csv.reader(f), None)


def reconcile(path: Path) -> tuple[list[str], list[str]]:
    """Field order for appending to `path`; widens the file in place if it lacks columns.

    Returns (fieldnames, added). An absent or empty file, or one whose header already
    holds every column, is left alone. Otherwise the target header is the old header
    followed by the columns it lacks, in COLUMNS order; the file is rewritten through a
    temporary neighbour and swapped in, so a crash leaves the original intact. Columns
    this apparatus does not know (a file from a newer one) keep their place.
    """
    header = _header(path)
    if not header:
        return list(COLUMNS), []
    target = header + [c for c in COLUMNS if c not in header]
    if target == header:
        return target, []
    tmp = path.with_name(path.name + ".tmp")
    with open(path, newline="") as src, open(tmp, "w", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=target, restval="", extrasaction="ignore")
        writer.writeheader()
        for row in csv.DictReader(src):
            writer.writerow(row)
    tmp.replace(path)
    return target, target[len(header) :]


def append(path: Path, fieldnames: list[str], row: dict) -> None:
    """Append one row, writing the header first if the file is absent or empty."""
    new = not path.exists() or path.stat().st_size == 0
    out = {k: _format(k, v) for k, v in row.items()}
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="", extrasaction="ignore")
        if new:
            writer.writeheader()
        writer.writerow(out)


def read(path: Path | None = None) -> list[dict]:
    """The curve as typed rows.

    Every name in COLUMNS is a key of every row: ints and floats are parsed by column,
    `phase` stays a string, and a cell the file does not have (an empty cell, or a
    column older than the file) is None. Columns this apparatus does not know are kept
    as strings. An absent or empty file reads as []. `path` defaults to the vessel's
    curve, resolved when called.
    """
    path = config.CURVE if path is None else path
    if not path.exists() or path.stat().st_size == 0:
        return []
    with open(path, newline="") as f:
        raw_rows = list(csv.DictReader(f))
    rows = []
    for raw in raw_rows:
        row = {name: _parse(name, raw.get(name)) for name in COLUMNS}
        for name, v in raw.items():
            if name is not None and name not in row:
                row[name] = v
        rows.append(row)
    return rows


def _format(name: str, v):
    d = DECIMALS.get(name)
    if d is not None and v is not None:
        return f"{v:.{d}f}"
    return v


def _parse(name: str, v):
    if v is None or v == "":
        return None
    if name in _INT:
        return int(v)
    if name in DECIMALS:
        return float(v)
    return v
