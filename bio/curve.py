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

# What a damaged or unwritable file raises out of reconcile(), append() and read().
# A caller that must not stop on a bad curve catches these and nothing broader.
ERRORS = (OSError, UnicodeDecodeError, csv.Error)
_ENCODING = "utf-8"


def _open(path: Path):
    """The file for reading. A leading byte-order mark, which a spreadsheet's 'CSV UTF-8'
    re-save prefixes, is dropped so the first cell reads `tick` and not `\\ufefftick`."""
    return open(path, newline="", encoding="utf-8-sig")


def _rows(f) -> tuple[list[str] | None, csv.DictReader]:
    """The header of an open file, its first non-blank row, and a reader over the rows after it.

    The header is None when the file has no non-blank row; the reader is then empty.
    """
    header = next((r for r in csv.reader(f) if r), None)
    return header, csv.DictReader(f, fieldnames=header)


def _header(path: Path) -> list[str] | None:
    """The header row of an existing file; None if the file is absent or has no header.

    This is the one test of 'has a header' that reconcile, append and read share: a file
    that is empty, or holds nothing but blank lines, has none.
    """
    if not path.exists():
        return None
    with _open(path) as f:
        return _rows(f)[0]


def reconcile(path: Path) -> tuple[list[str], list[str]]:
    """Field order for appending to `path`; widens the file in place if it lacks columns.

    Returns (fieldnames, added). A file with no header (absent, empty, blank lines only)
    or one whose header already holds every column is left alone. Otherwise the target
    header is the old header followed by the columns it lacks, in COLUMNS order; the file
    is rewritten through a temporary neighbour and swapped in, so a crash leaves the
    original intact. Columns this apparatus does not know (a file from a newer one) keep
    their place. Raises one of ERRORS when the file cannot be read or rewritten.
    """
    header = _header(path)
    if header is None:
        return list(COLUMNS), []
    target = header + [c for c in COLUMNS if c not in header]
    if target == header:
        return target, []
    tmp = path.with_name(path.name + ".tmp")
    try:
        with _open(path) as src, open(tmp, "w", newline="", encoding=_ENCODING) as dst:
            writer = csv.DictWriter(dst, fieldnames=target, restval="", extrasaction="ignore")
            writer.writeheader()
            for row in _rows(src)[1]:
                writer.writerow(row)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(path)
    return target, target[len(header) :]


def append(path: Path, fieldnames: list[str], row: dict) -> None:
    """Append one row, writing the header first if the file has none.

    'Has none' is _header's test, the same one reconcile applies: absent, empty, or blank
    lines only. Such a file is started over so that the header is its first line; nothing
    readable is lost, since it held no row.
    """
    new = _header(path) is None
    out = {k: _format(k, v) for k, v in row.items()}
    with open(path, "w" if new else "a", newline="", encoding=_ENCODING) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="", extrasaction="ignore")
        if new:
            writer.writeheader()
        writer.writerow(out)


def read(path: Path | None = None) -> list[dict]:
    """The curve as typed rows.

    Every name in COLUMNS is a key of every row: ints and floats are parsed by column,
    `phase` stays a string, and a cell the file does not have (an empty cell, or a
    column older than the file) is None. Columns this apparatus does not know are kept
    as strings. An absent file, or one with no header, reads as []. `path` defaults to
    the vessel's curve, resolved when called.
    """
    path = config.CURVE if path is None else path
    if not path.exists():
        return []
    with _open(path) as f:
        raw_rows = list(_rows(f)[1])  # [] when there is no header
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
