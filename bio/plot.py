"""The growth curve drawn: braille in the terminal, PNG with matplotlib. Reads the curve
and the log; writes nothing but the PNG it is asked for.

A figure is small multiples: the first column asked for is the tall panel, every further
column a shorter panel beneath it, all on one tick axis. Phase changes are rules through
the main panel; drops, revives and gaps are glyphs in a row under the axis. Markers come
from events.jsonl and are joined on (branch, tick), the last branch by default.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from rich.text import Text

from . import curve

PLOTTABLE: tuple[str, ...] = tuple(c for c in curve.COLUMNS if c not in ("tick", "phase", "branch"))
INTEGER = frozenset(c for c in PLOTTABLE if c not in curve.DECIMALS)
# axis labels, in docs/curve.md's words
LABELS: dict[str, str] = {
    "population": "population (cells)",
    "strains": "strains living",
    "nutrient": "agar nutrient (mean, 0–1)",
    "births": "births (cumulative)",
    "starved": "starved (cumulative)",
    "lysed": "lysed (cumulative)",
    "senescent": "senescent (cumulative)",
    "killed": "killed (cumulative)",
    "shannon": "diversity H (nats)",
    "dominance": "dominance (Berger–Parker)",
    "mean_gen": "mean generation (lineage depth)",
    "arisen": "strains arisen (cumulative)",
    "extinct": "strains extinct (cumulative)",
    "pheromone": "pheromone (mean)",
    "mutations_ready": "variants ready (pool)",
    "mutations_taken": "variants taken (cumulative)",
    "mutations_attempted": "mutagen calls (cumulative)",
    "mutations_viable": "variants viable (cumulative)",
    "predated": "predated (cumulative)",
    "arisen_llm": "strains arisen · LLM (cumulative)",
    "arisen_random": "strains arisen · random (cumulative)",
}
STYLES = {"population": "cyan", "strains": "yellow"}
TRACE_STYLE = "green4"  # every other column
# One style per flask in an overlay, cycled when there are more than twelve (Lenski had twelve).
# rich colour names; every one is distinct in a 256-colour terminal and in matplotlib.
FLASK_STYLES = [
    "cyan",
    "yellow",
    "green3",
    "magenta",
    "red",
    "blue",
    "bright_cyan",
    "dark_orange3",
    "bright_magenta",
    "spring_green3",
    "bright_red",
    "medium_purple",
]
# kind -> (glyph, style). phase, drop and revived are the eyepiece's icons (tui.ICONS; a test
# pins them equal, plot does not import tui). Every glyph is one cell wide.
MARKERS: dict[str, tuple[str, str]] = {
    "phase": ("◐", "bold white"),
    "drop": ("⚗", "magenta"),
    "revived": ("↺", "bold cyan"),
    "gap": ("⋯", "dim"),
}
RULE = "┆"
INSTALL = "matplotlib is not installed — `uv sync --extra plot` in the checkout, or `pip install 'biotic[plot]'`"

_PHASE_MSG = re.compile(r"entered (\w+) phase")  # phase events older than the `phase` field
_STRAIN_MSG = re.compile(r"^revived (\S+) \(")  # `revived tide_drift (3f1a) into …`
_BRAILLE = 0x2800
_DOTS = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))  # [dy][dx]
_LABEL_EVERY = 12  # cells between tick labels, about


@dataclass(frozen=True)
class Trace:
    label: str
    xs: list[int]
    ys: list[float]
    style: str = "cyan"


@dataclass(frozen=True)
class Panel:
    label: str  # LABELS[col]
    traces: list[Trace] = field(default_factory=list)  # one today; a flask overlay is one per flask
    empty: str | None = None  # "no values for shannon in this file" when no row has a value
    integer: bool = False  # y labels as ints


@dataclass(frozen=True)
class Marker:
    tick: int
    kind: str  # a key of MARKERS
    label: str  # "log", "nutrient", "from 4000", "tide_drift", ""
    branch: int


@dataclass(frozen=True)
class Figure:
    title: str  # 'seed “tide” · branch 0 · ticks 10–1220 · 122 rows'
    panels: list[Panel]
    markers: list[Marker]
    x0: int
    x1: int


class PlotUnavailable(RuntimeError):
    """matplotlib is not installed; the message says how to install it."""


# --- the figure ----------------------------------------------------------------


def parse_cols(text: str) -> list[str]:
    """`--cols` as a list of plottable column names, in order, without repeats.

    Raises ValueError naming the plottable columns for an empty list, a name the curve does not
    have, or one that is a coordinate rather than a series (`tick`, `phase`, `branch`)."""
    cols: list[str] = []
    for name in (n.strip() for n in text.split(",")):
        if not name:
            continue
        if name not in PLOTTABLE:
            raise ValueError(f"{name!r} is not a column that can be plotted; pick from: {', '.join(PLOTTABLE)}")
        if name not in cols:
            cols.append(name)
    if not cols:
        raise ValueError(f"--cols wants at least one column; pick from: {', '.join(PLOTTABLE)}")
    return cols


def markers(events: list[dict]) -> list[Marker]:
    """The markers in a log, in file order. `events` is curve.events(): each carries `branch`.

    phase -> the phase entered (the `phase` field, else parsed from the message); drop -> what
    was dropped; a dish revive (the event with `from`) -> `from <tick>`; a strain revive (`into`)
    -> the strain's name; gap -> its message. A revive's `took` / `did not take` verdict, and every
    other kind, is not a marker. An event with no tick is skipped."""
    out: list[Marker] = []
    for ev in events:
        tick, kind = ev.get("tick"), ev.get("kind")
        if kind not in MARKERS or not isinstance(tick, int) or isinstance(tick, bool):
            continue
        msg = str(ev.get("msg") or "")
        if kind == "phase":
            label = ev.get("phase")
            if not label:
                m = _PHASE_MSG.search(msg)
                if not m:
                    continue
                label = m.group(1)
        elif kind == "drop":
            label = str(ev.get("what") or "")
        elif kind == "revived":
            if "from" in ev:
                label = f"from {ev['from']}"
            elif "into" in ev:
                m = _STRAIN_MSG.match(msg)
                label = m.group(1) if m else str(ev.get("strain") or "")
            else:
                continue
        else:
            label = msg
        out.append(Marker(tick=tick, kind=kind, label=str(label), branch=int(ev.get("branch") or 0)))
    return out


def figure(
    rows: list[dict],
    events: list[dict],
    cols: list[str],
    *,
    since: int | None = None,
    branch: int | None = None,
    seed: str | None = None,
) -> Figure:
    """One branch of the curve as panels and markers. `rows` is curve.read(), `events` is
    curve.events(), `cols` is parse_cols().

    The last branch unless `branch` says otherwise; a branch the curve does not have raises
    ValueError naming the ones it has. `since` keeps rows from that tick on. A trailing row
    whose tick does not climb past the row before it is a torn line an incubator is still
    writing, and is left out. The rest are ordered by tick before plotting: a crash-resume
    rewrites ticks the dish already visited without opening a branch, so a branch is not always
    monotone in the file, and every row is still drawn in its place. No rows at all is a
    ValueError too. Markers are those of the
    branch inside the plotted ticks, plus the revive that opened the branch, drawn at the left
    edge when its tick lies before the first row and `since` does not exclude it."""
    by = curve.branches(rows)
    if not by:
        raise ValueError("the growth curve has no rows yet")
    if branch is None:
        branch = max(by)
    if branch not in by:
        raise ValueError(f"no branch {branch} in the curve; it has {', '.join(str(b) for b in sorted(by))}")
    sel = [r for r in by[branch] if r.get("tick") is not None]
    if len(sel) >= 2 and sel[-1]["tick"] <= sel[-2]["tick"]:
        sel = sel[:-1]  # a torn tail: the incubator's half-written last row
    # a crash-resume rewrites ticks the dish already visited without opening a branch, so tick is
    # not monotone within a branch; sort by tick so downsample's buckets and x0/x1 stay honest.
    sel = sorted(sel, key=lambda r: r["tick"])
    if since is not None:
        sel = [r for r in sel if r["tick"] >= since]
        if not sel:
            raise ValueError(f"no rows from tick {since}")
    if not sel:
        raise ValueError("the growth curve has no rows yet")
    x0, x1 = sel[0]["tick"], sel[-1]["tick"]
    panels = []
    for col in cols:
        xs = [r["tick"] for r in sel if r.get(col) is not None]
        ys = [float(r[col]) for r in sel if r.get(col) is not None]
        if xs:
            panels.append(
                Panel(LABELS[col], [Trace(col, xs, ys, STYLES.get(col, TRACE_STYLE))], integer=col in INTEGER)
            )
        else:
            panels.append(Panel(LABELS[col], [], empty=f"no values for {col} in this file", integer=col in INTEGER))
    every = markers(events)
    ms = [m for m in every if m.branch == branch and x0 <= m.tick <= x1]
    opener = next(
        (m for m in every if m.kind == "revived" and m.branch == branch and m.label.startswith("from ")), None
    )
    if opener is not None and opener.tick < x0 and (since is None or since <= opener.tick):
        ms.append(Marker(tick=x0, kind="revived", label=opener.label, branch=branch))
    ms.sort(key=lambda m: m.tick)
    head = f"seed “{seed}” · " if seed else ""
    title = f"{head}branch {branch} · ticks {x0}–{x1} · {len(sel)} row{'s' if len(sel) != 1 else ''}"
    return Figure(title=title, panels=panels, markers=ms, x0=x0, x1=x1)


def overlay(seed: str, series: list[tuple[str, list[dict]]], cols: list[str], *, since: int | None = None) -> Figure:
    """Several flasks' curves on one figure: one Panel per column, one Trace per flask.

    `series` is `(flask_id, rows)` for each flask, `rows` being `curve.read()` sorted by tick.
    For each column a Panel holds one Trace per flask that has any value for it, styled from
    FLASK_STYLES in flask order (cycled past twelve). `since` keeps rows from that tick on. x0/x1
    span every flask, so the panels share one tick axis. No markers: an overlay is about the shape
    of the replicates, not the events of any one of them. Raises ValueError when no flask has a
    single plottable row (an empty column is drawn as an empty panel, as `figure` does)."""
    x0: int | None = None
    x1: int | None = None
    panels = []
    for col in cols:
        traces: list[Trace] = []
        for i, (fid, rows) in enumerate(series):
            xs, ys = [], []
            for r in rows:
                tick = r.get("tick")
                if tick is None or (since is not None and tick < since) or r.get(col) is None:
                    continue
                xs.append(tick)
                ys.append(float(r[col]))
            if not xs:
                continue
            traces.append(Trace(fid, xs, ys, FLASK_STYLES[i % len(FLASK_STYLES)]))
            x0 = xs[0] if x0 is None else min(x0, xs[0])
            x1 = xs[-1] if x1 is None else max(x1, xs[-1])
        if traces:
            panels.append(Panel(LABELS[col], traces, integer=col in INTEGER))
        else:
            panels.append(Panel(LABELS[col], [], empty=f"no values for {col} in any flask", integer=col in INTEGER))
    if x0 is None or x1 is None:
        raise ValueError("no rows in any flask yet")
    n = len(series)
    head = f"seed “{seed}” · " if seed else ""
    title = f"{head}{n} flask{'s' if n != 1 else ''} · ticks {x0}–{x1}"
    return Figure(title=title, panels=panels, markers=[], x0=x0, x1=x1)


def downsample(xs: list[int], ys: list[float], x0: int, x1: int, buckets: int) -> tuple[list[int], list[float]]:
    """At most two points per bucket of x: the lowest and the highest, in x order, so a one-row
    spike or crash survives however long the curve is. The first and last points are always
    kept. Buckets are by x over [x0, x1], not by index, so a stretch with no rows does not
    pull the rest across the axis. A series that already fits (2 points per bucket) is
    returned as it is. Pure, and linear in the number of points."""
    n = len(xs)
    if buckets < 1 or n <= 2 * buckets:
        return list(xs), list(ys)
    span = x1 - x0 + 1
    keep = {0, n - 1}
    cur, lo, hi = -1, 0, 0
    for i, (x, y) in enumerate(zip(xs, ys)):
        b = min(buckets - 1, max(0, int((x - x0) / span * buckets)))
        if b != cur:
            if cur >= 0:
                keep.add(lo)
                keep.add(hi)
            cur, lo, hi = b, i, i
        else:
            if y < ys[lo]:
                lo = i
            if y > ys[hi]:
                hi = i
    keep.add(lo)
    keep.add(hi)
    idx = sorted(keep)
    return [xs[i] for i in idx], [ys[i] for i in idx]


# --- the terminal -----------------------------------------------------------------


class _Canvas:
    """A braille dot grid of `cw` × `ch` cells; each cell keeps the style of the last trace
    that set a dot in it."""

    def __init__(self, cw: int, ch: int):
        self.cw, self.ch = cw, ch
        self.bits = [[0] * cw for _ in range(ch)]
        self.style = [[""] * cw for _ in range(ch)]

    def dot(self, dx: int, dy: int, style: str) -> None:
        if 0 <= dx < 2 * self.cw and 0 <= dy < 4 * self.ch:
            self.bits[dy // 4][dx // 2] |= _DOTS[dy % 4][dx % 2]
            self.style[dy // 4][dx // 2] = style

    def line(self, x0: int, y0: int, x1: int, y1: int, style: str) -> None:
        """Bresenham between two dots, both ends included."""
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            self.dot(x0, y0, style)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def cells(self) -> list[list[tuple[str, str]]]:
        return [
            [(chr(_BRAILLE + b) if b else " ", s) for b, s in zip(row, styles)]
            for row, styles in zip(self.bits, self.style)
        ]


def _fmt(v: float, integer: bool) -> str:
    if integer:
        return str(round(v))
    return f"{v:.3g}"


def _range(panel: Panel) -> tuple[float, float]:
    """The y axis: from 0 (or below, should a series ever go negative) to the highest value; a
    flat series gets a unit of headroom so it sits on the floor and the top label is honest."""
    ys = [y for t in panel.traces for y in t.ys]
    ymin = min(0.0, min(ys)) if ys else 0.0
    ymax = max(ys) if ys else 1.0
    if ymax <= ymin:
        ymax = ymin + 1
    return ymin, ymax


def _ylabels(panel: Panel, ch: int) -> dict[int, str]:
    """Row -> label: the top of the axis, the bottom, and the value at the top dot of the middle row."""
    if panel.empty:
        return {}
    ymin, ymax = _range(panel)
    mid = ch // 2
    at_mid = ymax - (4 * mid) / (4 * ch - 1) * (ymax - ymin)
    labels = {0: _fmt(ymax, panel.integer), ch - 1: _fmt(ymin, panel.integer)}
    if _fmt(at_mid, panel.integer) not in labels.values():  # a middle label that repeats an end says nothing
        labels[mid] = _fmt(at_mid, panel.integer)
    return labels


def _nice(step: float) -> int:
    """The smallest of 1, 2, 5 × 10^k that is at least `step`."""
    if step <= 1:
        return 1
    e = 10 ** math.floor(math.log10(step))
    for m in (1, 2, 5, 10):
        if m * e >= step:
            return int(m * e)
    return int(10 * e)


def _xticks(x0: int, x1: int, cw: int) -> list[int]:
    """Tick values to label: the two ends and round numbers between them, about one per
    _LABEL_EVERY cells."""
    if x1 <= x0:
        return [x0]
    n = max(1, cw // _LABEL_EVERY)
    step = _nice((x1 - x0) / n)
    first = (x0 // step + 1) * step
    between = list(range(first, x1, step)) if first < x1 else []
    return [x0, *between, x1]


def _put(row: list[tuple[str, str]], at: int, text: str, style: str) -> None:
    for i, ch in enumerate(text):
        if 0 <= at + i < len(row):
            row[at + i] = (ch, style)


def _text(runs: list[tuple[str, str]], width: int, overflow: str = "crop") -> Text:
    t = Text(no_wrap=True)
    last: tuple[str, str] | None = None
    for ch, style in runs:  # merge neighbours of one style into one span
        if last is not None and last[1] == style:
            last = (last[0] + ch, style)
        else:
            if last is not None:
                t.append(*last)
            last = (ch, style)
    if last is not None:
        t.append(*last)
    t.truncate(width, overflow=overflow)
    return t


def render(fig: Figure, width: int, height: int) -> Text:
    """The figure as text for a terminal `width` cells wide: the title, then each panel with its
    label above and its y axis in the gutter (the main panel `height` rows tall, the others half),
    the tick axis, the tick labels, and a row of markers. No line is wider than `width`, and two
    renders of one figure are identical: nothing here reads a clock."""
    height = max(4, height)
    heights = [height if i == 0 else max(4, height // 2) for i in range(len(fig.panels))]
    ylabels = [_ylabels(p, h) for p, h in zip(fig.panels, heights)]
    gw = max([len(s) for d in ylabels for s in d.values()] or [1]) + 2  # `{label} ┤`
    cw = max(1, width - gw - 1)
    span = fig.x1 - fig.x0

    def dot_col(x: int) -> int:
        return 0 if span <= 0 else round((x - fig.x0) / span * (2 * cw - 1))

    def gutter(label: str = "", axis: str = "┤") -> list[tuple[str, str]]:
        return [(c, "dim") for c in f"{label:>{gw - 2}} {axis}"]

    lines = [_text([(c, "dim") for c in fig.title], width, overflow="ellipsis")]
    for i, (panel, ch) in enumerate(zip(fig.panels, heights)):
        lines.append(_text([(" ", "")] * gw + [(c, "bold") for c in panel.label], width))
        if panel.empty:
            lines.append(_text(gutter() + [(c, "dim") for c in panel.empty], width))
            continue
        ymin, ymax = _range(panel)
        canvas = _Canvas(cw, ch)
        for tr in panel.traces:
            xs, ys = downsample(tr.xs, tr.ys, fig.x0, fig.x1, 2 * cw)
            pts = [
                (dot_col(x), (4 * ch - 1) - round((y - ymin) / (ymax - ymin) * (4 * ch - 1))) for x, y in zip(xs, ys)
            ]
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                canvas.line(ax, ay, bx, by, tr.style)
            if len(pts) == 1:
                canvas.dot(pts[0][0], pts[0][1], tr.style)
        cells = canvas.cells()
        if i == 0:
            _rules(cells, fig, dot_col)
        for r, row in enumerate(cells):
            lines.append(_text(gutter(ylabels[i].get(r, "")) + row, width))
    lines.append(_text(gutter("", "┼") + [("─", "dim")] * cw, width))
    xrow: list[tuple[str, str]] = [(" ", "")] * cw
    end = -2
    for j, tick in enumerate(_xticks(fig.x0, fig.x1, cw)):
        label = str(tick)
        at = cw - len(label) if j and tick == fig.x1 else dot_col(tick) // 2
        if at < end + 2:
            continue
        _put(xrow, at, label, "dim")
        end = at + len(label)
    lines.append(_text([(" ", "")] * gw + xrow, width))
    mrow: list[tuple[str, str]] = [(" ", "")] * cw
    for m in fig.markers:
        if m.kind == "phase":
            continue
        at = dot_col(m.tick) // 2
        if mrow[at][0] == " ":
            mrow[at] = MARKERS[m.kind]
    lines.append(_text([(" ", "")] * gw + mrow, width))
    return Text("\n").join(lines)


def _rules(cells: list[list[tuple[str, str]]], fig: Figure, dot_col) -> None:
    """Phase markers on the main panel: a rule through every row at the marker's column, and
    the phase's name on the top row beside it — to the right, or to the left when the right
    has no room. A name that would touch another name or cross another rule is left out;
    the rule stays."""
    phases = [m for m in fig.markers if m.kind == "phase"]
    cols = [dot_col(m.tick) // 2 for m in phases]
    cw = len(cells[0])
    glyph_style = MARKERS["phase"][1]
    taken: list[tuple[int, int]] = []  # [start, end) of names drawn on the top row
    for k, (m, col) in enumerate(zip(phases, cols)):
        for row in cells:
            row[col] = (RULE, "dim")
        prev_col = cols[k - 1] if k else -1
        next_col = cols[k + 1] if k + 1 < len(cols) else cw + 1
        n = len(m.label)
        right, left = col + 1, col - n
        for start in (right, left):
            end = start + n
            if start < 0 or end > cw:
                continue
            if start <= prev_col or end > next_col:
                continue
            if any(start < b + 1 and end + 1 > a for a, b in taken):
                continue
            _put(cells[0], start, m.label, glyph_style)
            taken.append((start, end))
            break


# --- the PNG ----------------------------------------------------------------------


def _pyplot():
    """The one matplotlib seam: pyplot on the Agg backend, or None when it is not installed."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    return plt


def _safe(s: str) -> str:
    """matplotlib reads `$…$` as mathtext; the seed is free text."""
    return s.replace("$", r"\$")


def png(fig: Figure, path: Path) -> Path:
    """The same figure through matplotlib at full resolution, one axis per panel sharing the
    tick axis, written to `path`. Raises PlotUnavailable with the install line when matplotlib
    is not installed; OSError when the file cannot be written."""
    plt = _pyplot()
    if plt is None:
        raise PlotUnavailable(INSTALL)
    n = len(fig.panels)
    f, axes = plt.subplots(n, 1, sharex=True, figsize=(11, 3 + 2 * n), height_ratios=[2] + [1] * (n - 1))
    axes = list(axes) if n > 1 else [axes]
    for i, (ax, panel) in enumerate(zip(axes, fig.panels)):
        for tr in panel.traces:
            ax.plot(tr.xs, tr.ys, lw=1.0, label=_safe(tr.label))
        if len(panel.traces) > 1:  # a flask overlay: name each line; a single-trace panel stays legend-free
            ax.legend(fontsize=8, ncols=min(4, len(panel.traces)), loc="best")
        ax.set_ylabel(_safe(panel.label))
        if panel.empty:
            ax.text(0.5, 0.5, _safe(panel.empty), transform=ax.transAxes, ha="center", va="center", fontsize=9)
        if i == 0:
            # x in data, y in axes fraction: a label rides its rule at the top or foot of the
            # panel whatever the autoscaled y-range, rather than at a data y that can fall off it.
            trans = ax.get_xaxis_transform()
            for m in fig.markers:
                if m.kind == "phase":
                    ax.axvline(m.tick, ls=":", color="0.5", lw=0.8)
                    ax.text(
                        m.tick,
                        1.0,
                        _safe(m.label),
                        transform=trans,
                        rotation=90,
                        va="top",
                        ha="right",
                        fontsize=8,
                        color="0.3",
                    )
                else:
                    ax.axvline(m.tick, ls="--", color="m", lw=0.8)
                    label = _safe(f"{m.kind} {m.label}".strip())
                    ax.text(
                        m.tick,
                        0.0,
                        label,
                        transform=trans,
                        rotation=90,
                        va="bottom",
                        ha="right",
                        fontsize=8,
                        color="m",
                    )
    axes[-1].set_xlabel("tick")
    f.suptitle(_safe(fig.title))
    f.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(f)
    return Path(path)
