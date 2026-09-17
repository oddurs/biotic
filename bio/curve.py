"""The growth curve: what vessel/curve.csv holds, how it is written, how it is read.

One row every CADENCE ticks. Columns are only ever appended. A file written by an
older apparatus is widened in place, once, with empty cells for what it did not
record. Markers (drops, revives, incubation gaps) belong in events.jsonl, not here.
`branch` is not a marker but a coordinate: with it, (branch, tick) names a row
uniquely after a revive has sent the tick column back through ticks it had already
visited.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterator
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
    # the timeline: 0 until the first dish revive, one more at each; empty in rows older than the column
    "branch",
    # the mutagen's supply, cumulative: calls made; daughters that passed the membrane. docs/experiments.md
    "mutations_attempted",
    "mutations_viable",
    # predation: cells burst by a lysing neighbour of another strain, cumulative. docs/predation.md
    "predated",
    # the arms of the mutagen, cumulative: strains that arose by each. docs/mutagen.md
    "arisen_llm",
    "arisen_random",
    # sharing: energy that left givers, and the smaller amount that reached recipients, cumulative
    # and dish-wide. The gap is heat. 0.0 unless the `give` feature is on. docs/sharing.md
    "given",
    "received",
)
DECIMALS = {"nutrient": 4, "shannon": 4, "dominance": 4, "mean_gen": 2, "pheromone": 4, "given": 4, "received": 4}
_INT = frozenset(COLUMNS) - frozenset(DECIMALS) - {"phase"}

# What a damaged or unwritable file raises out of reconcile(), append() and read(): it
# cannot be opened or written, is not UTF-8, is not CSV, has a row wider than its header,
# or holds a cell that is not the number its column says. A caller that must not stop on
# a bad curve catches these and nothing broader.
ERRORS = (OSError, UnicodeDecodeError, csv.Error, ValueError)
_ENCODING = "utf-8"


def _open(path: Path):
    """The file for reading. A leading byte-order mark, which a spreadsheet's 'CSV UTF-8'
    re-save prefixes, is dropped so the first cell reads `tick` and not `\\ufefftick`."""
    return open(path, newline="", encoding="utf-8-sig")


def _rows(f) -> tuple[list[str] | None, Iterator[list[str]]]:
    """The header of an open file, its first non-blank row, and a reader over the rows after it.

    The header is None when the file has no non-blank row; the reader is then exhausted.
    Blank lines come out of the reader as []; its `line_num` is the file line just read.
    """
    reader = csv.reader(f)
    header = next((r for r in reader if r), None)
    return header, reader


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
    their place. A row with more cells than the header has no column for the extra ones:
    rather than drop them, the widening is refused with csv.Error and the file is left as
    it is. Raises one of ERRORS when the file cannot be read or rewritten.
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
            reader = _rows(src)[1]
            writer = csv.writer(dst)
            writer.writerow(target)
            for cells in reader:
                if not cells:
                    continue  # a blank line; a rewrite drops them
                if len(cells) > len(header):
                    raise csv.Error(
                        f"{path.name} line {reader.line_num} has {len(cells)} cells under a "
                        f"{len(header)}-column header; not widened"
                    )
                writer.writerow(cells + [""] * (len(target) - len(cells)))
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
    as strings; cells beyond the header, which have no name to return them under, are
    not returned. An absent file, or one with no header, reads as []. A cell that is not
    the number its column says (a hand-edited or truncated file) raises ValueError naming
    the line and column; it is one of ERRORS. `path` defaults to the vessel's curve,
    resolved when called. Reading never rewrites the file.
    """
    path = config.CURVE if path is None else path
    if not path.exists():
        return []
    rows = []
    with _open(path) as f:
        header, reader = _rows(f)
        for cells in reader:  # nothing when there is no header
            if not cells:
                continue
            raw = dict(zip(header, cells))
            row = {}
            for name in COLUMNS:
                try:
                    row[name] = _parse(name, raw.get(name))
                except ValueError as e:
                    raise ValueError(
                        f"{path.name} line {reader.line_num}, {name}: {raw[name]!r} is not a number"
                    ) from e
            row.update((name, v) for name, v in raw.items() if name not in row)
            rows.append(row)
    return rows


def branches(rows: list[dict]) -> dict[int, list[dict]]:
    """Rows by branch, each list in file order; a row with no branch (older than the column)
    is branch 0. Keys come out in the order the branches first appear, which is climbing."""
    by: dict[int, list[dict]] = {}
    for r in rows:
        b = r.get("branch")
        by.setdefault(0 if b is None else int(b), []).append(r)
    return by


def events(path: Path | None = None) -> list[dict]:
    """events.jsonl as dicts, each with a `branch` key so that events join the curve on
    (branch, tick).

    A dish `revived` event (one with `from` and `was`) opens a branch: the events after it are
    on the branch it carries, and it keeps that `branch` itself, since the culture logs it after
    the swap. Before any such event everything is branch 0. An event that already has a
    `branch` (not null) keeps it. A line that does not parse, or is not an object, is skipped: the torn
    tail while an incubator writes. An absent file reads as []. `path` defaults to the vessel's
    log, resolved when called."""
    path = config.EVENTS if path is None else path
    if not path.exists():
        return []
    out: list[dict] = []
    branch = 0
    with open(path, encoding=_ENCODING, errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(ev, dict):
                continue
            if ev.get("kind") == "revived" and "from" in ev and "was" in ev:
                branch = int(ev["branch"]) if isinstance(ev.get("branch"), int) else branch + 1
            if ev.get("branch") is None:
                ev["branch"] = branch
            out.append(ev)
    return out


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
