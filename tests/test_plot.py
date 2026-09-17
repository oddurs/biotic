"""`biotic curve`: the growth curve drawn in the terminal and as a PNG. Markers come from the log
and are joined on (branch, tick); a long curve is downsampled without losing a spike or a crash;
the command reads the vessel and writes nothing; matplotlib is optional and its absence is
explained. Everything here is offline and seeded: synthetic curves from closed forms or a fixed
`random.Random`, and one real culture with a dormant mind."""

from __future__ import annotations

import csv
import fcntl
import json
import math
import random
from pathlib import Path
from types import SimpleNamespace

import pytest
from rich.cells import cell_len

from bio import config, curve, plot, tui
from bio.__main__ import main
from bio.culture import incubating

OLD_HEADER = "tick,population,strains,nutrient,phase,births,starved,lysed,senescent"
OLD_ROWS = [
    "10,5,1,0.7103,lag,0,0,0,0",
    "20,10,1,0.7314,lag,5,0,0,0",
    "30,12,1,0.7280,lag,7,0,0,0",
]
PANEL_LABELS = set(plot.LABELS.values())

# --- helpers ------------------------------------------------------------------


@pytest.fixture(autouse=True)
def plain_console(monkeypatch):
    """rich writes no escape codes to a captured stdout unless the environment forces a terminal."""
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.delenv("TTY_COMPATIBLE", raising=False)


@pytest.fixture
def run(capsys):
    def _run(argv: list[str]) -> str:
        main(argv)
        return capsys.readouterr().out

    return _run


def row(tick: int, population: int, strains: int = 1, branch: int | None = 0, **kw) -> dict:
    r = {
        "tick": tick,
        "population": population,
        "strains": strains,
        "nutrient": 0.5,
        "phase": "log",
        "births": 0,
        "starved": 0,
        "lysed": 0,
        "senescent": 0,
        "killed": 0,
        "shannon": 0.0,
        "dominance": 1.0,
        "mean_gen": 0.0,
        "arisen": 1,
        "extinct": 0,
        "pheromone": 0.0,
        "mutations_ready": 0,
        "mutations_taken": 0,
        "branch": branch,
    }
    r.update(kw)
    return r


def write_curve(path: Path, rows: list[dict]) -> None:
    """A full-header curve.csv, written directly (not through curve.append) so 50,000 rows are cheap."""
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(curve.COLUMNS), restval="")
        w.writeheader()
        w.writerows(rows)


def write_events(path: Path, evs: list[dict]) -> None:
    with open(path, "w") as f:
        for i, ev in enumerate(evs):
            f.write(json.dumps({"t": 1.0 + i, **ev}) + "\n")


def phase(tick: int, name: str, **kw) -> dict:
    return {"tick": tick, "kind": "phase", "msg": f"culture entered {name} phase", "phase": name, **kw}


def drop(tick: int, what: str = "nutrient", **kw) -> dict:
    return {"tick": tick, "kind": "drop", "msg": f"{what} dropped at (3,3)", "what": what, "at": [3, 3], **kw}


def dish_revive(tick: int, was: int, branch: int) -> dict:
    return {
        "tick": tick,
        "kind": "revived",
        "msg": f"revived from tick {tick} (the dish was at {was}) — 9 cells, 1 strain",
        "sample": f"{tick:08d}-t",
        "was": was,
        "branch": branch,
        "from": tick,
    }


def logistic(i: int, n: int) -> int:
    return int(500 / (1 + math.exp(-(i - n / 3) / 30)))


def logistic_rows(n: int = 120) -> list[dict]:
    return [row(10 * (i + 1), logistic(i, n), strains=1 + i // 40) for i in range(n)]


def panel_rows(out: str, label: str) -> list[str]:
    """The canvas of the panel under `label`: what follows the axis glyph on each of its rows,
    padded to one width."""
    lines = out.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == label) + 1
    rows = []
    for ln in lines[start:]:
        if ln.strip() in PANEL_LABELS or "┼" in ln:
            break
        rows.append(ln.split("┤", 1)[1])
    w = max(len(r) for r in rows)
    return [r.ljust(w) for r in rows]


def columns(rows: list[str]) -> list[str]:
    return ["".join(r[i] for r in rows) for i in range(len(rows[0]))]


def is_braille(ch: str) -> bool:
    return 0x2800 <= ord(ch) < 0x2900


def top_of(column: str) -> int | None:
    """The highest set dot in a column of cells, as a dot row from the top; None for no dots."""
    for r, ch in enumerate(column):
        if is_braille(ch):
            bits = ord(ch) - 0x2800
            for dy in range(4):
                if bits & (plot._DOTS[dy][0] | plot._DOTS[dy][1]):
                    return 4 * r + dy
    return None


def under_axis(out: str) -> tuple[str, str]:
    """The tick-label row and the marker row, aligned to the canvas."""
    lines = out.splitlines()
    k = next(i for i, ln in enumerate(lines) if "┼" in ln)
    gw = lines[k].index("┼") + 1
    markers = lines[k + 2][gw:] if k + 2 < len(lines) else ""
    return lines[k + 1][gw:], markers


def col_of(tick: int, x0: int, x1: int, cw: int) -> int:
    """The cell column render() puts a tick in."""
    return (0 if x1 == x0 else round((tick - x0) / (x1 - x0) * (2 * cw - 1))) // 2


# --- the vocabulary -------------------------------------------------------------


def test_plottable_columns_and_labels_use_the_docs_words():
    assert plot.PLOTTABLE == tuple(c for c in curve.COLUMNS if c not in ("tick", "phase", "branch"))
    assert set(plot.LABELS) == set(plot.PLOTTABLE), "every plottable column has an axis label"
    assert plot.LABELS["dominance"] == "dominance (Berger–Parker)"
    assert "lineage depth" in plot.LABELS["mean_gen"]
    assert plot.parse_cols("population, shannon") == ["population", "shannon"]
    assert plot.parse_cols("population,population,strains") == ["population", "strains"]
    for bad in ("phase", "tick", "branch", "nope", ""):
        with pytest.raises(ValueError, match="pick from: population, strains, nutrient"):
            plot.parse_cols(bad)


def test_marker_glyphs_match_the_eyepiece():
    for kind in ("phase", "drop", "revived", "gap"):
        assert plot.MARKERS[kind] == tui.ICONS[kind]
    for glyph, _ in plot.MARKERS.values():
        assert cell_len(glyph) == 1, glyph
    assert cell_len(plot.RULE) == 1


# --- the data ---------------------------------------------------------------------


def test_downsample_keeps_every_column_extreme_and_the_ends():
    rng = random.Random(4)
    xs = [10 + 10 * i for i in range(50_000)]
    ys = [float(rng.randint(100, 400)) for _ in xs]
    ys[31_337] = 4000.0  # one row's spike
    sx, sy = plot.downsample(xs, ys, xs[0], xs[-1], 200)
    assert len(sx) <= 402
    assert (xs[31_337], 4000.0) in set(zip(sx, sy))
    assert (sx[0], sy[0]) == (xs[0], ys[0]) and (sx[-1], sy[-1]) == (xs[-1], ys[-1])
    assert sx == sorted(sx)
    assert plot.downsample(xs, ys, xs[0], xs[-1], 200) == (sx, sy)
    span = xs[-1] - xs[0] + 1
    raw: dict[int, list[float]] = {}
    kept: dict[int, list[float]] = {}
    for x, y in zip(xs, ys):
        raw.setdefault(int((x - xs[0]) / span * 200), []).append(y)
    for x, y in zip(sx, sy):
        kept.setdefault(int((x - xs[0]) / span * 200), []).append(y)
    for b, vals in raw.items():
        assert min(vals) in kept[b] and max(vals) in kept[b], f"bucket {b} lost an extreme"
    short = list(range(100))
    assert plot.downsample(short, [float(v) for v in short], 0, 99, 200) == (short, [float(v) for v in short])
    # buckets are by x, not by index: a gap in the ticks is a gap on the axis
    xs2 = list(range(10, 101)) + list(range(5000, 5091))
    sx2, _ = plot.downsample(xs2, [1.0] * len(xs2), 10, 5090, 45)
    assert sx2 == [10, 5000, 5090], "two occupied buckets at the ends, nothing in between"


def test_events_are_stamped_with_their_branch(tmp_path):
    evs = [
        {"tick": 0, "kind": "genesis", "msg": "inoculated 5 cells of founder"},
        phase(60, "log"),
        drop(100),
        dish_revive(40, was=140, branch=1),
        drop(55),
        {
            "tick": 70,
            "kind": "revived",
            "msg": "revived bud (ab12) into the dish at (3,3) — 5 cells",
            "into": "current",
        },
        dish_revive(30, was=80, branch=2),
        phase(90, "stationary"),
    ]
    write_events(config.EVENTS, evs)
    with open(config.EVENTS, "a") as f:
        f.write("42\n")  # not an object
        f.write('{"t": 1, "ki')  # torn by a write in progress
    got = curve.events()
    assert [e["kind"] for e in got] == [e["kind"] for e in evs]
    assert [e["branch"] for e in got] == [0, 0, 0, 1, 1, 1, 2, 2]
    other = tmp_path / "other.jsonl"
    write_events(other, [drop(5, branch=7), {**dish_revive(9, was=99, branch=1), "branch": None}, drop(6)])
    stamped = curve.events(other)
    assert stamped[0]["branch"] == 7, "a branch an event carries is kept"
    assert [e["branch"] for e in stamped[1:]] == [1, 1], "an opener without a branch opens the next one"
    assert curve.events(tmp_path / "absent.jsonl") == []


def test_branches_group_rows_and_none_is_zero():
    rows = [row(10, 1, branch=None), row(20, 2, branch=0), row(15, 3, branch=1)]
    by = curve.branches(rows)
    assert list(by) == [0, 1]
    assert [r["tick"] for r in by[0]] == [10, 20] and [r["tick"] for r in by[1]] == [15]
    fig = plot.figure(rows, [], ["population"])
    assert (fig.x0, fig.x1) == (15, 15) and fig.title == "branch 1 · ticks 15–15 · 1 row"
    fig0 = plot.figure(rows, [], ["population"], branch=0)
    assert (fig0.x0, fig0.x1) == (10, 20) and fig0.title == "branch 0 · ticks 10–20 · 2 rows"
    with pytest.raises(ValueError, match=r"no branch 7 in the curve; it has 0, 1"):
        plot.figure(rows, [], ["population"], branch=7)


def test_markers_from_events_new_and_old():
    evs = [
        phase(60, "log", branch=0),
        {"tick": 200, "kind": "phase", "msg": "culture entered stationary phase", "branch": 0},  # before the field
        {
            "tick": 300,
            "kind": "revived",
            "msg": "revived bud took — 12 cells after 100 ticks",
            "took": True,
            "branch": 0,
        },
        {
            "tick": 70,
            "kind": "revived",
            "msg": "revived bud (ab12) into the dish at (3,3) — 5 cells",
            "into": "current",
        },
        dish_revive(40, was=140, branch=1),
        {"tick": 0, "kind": "revived", "msg": "revived bud (ab12) into a fresh dish — 5 cells", "into": "fresh"},
        {"tick": 500, "kind": "gap", "msg": "incubator off for 2h", "branch": 0},
        {"tick": 10, "kind": "arose", "msg": "bud arose from founder", "branch": 0},
        {"tick": 11, "kind": "extinct", "msg": "bud went extinct after 1 ticks (peak 1)", "branch": 0},
        {"kind": "drop", "msg": "no tick", "what": "nutrient", "branch": 0},
        {"tick": 12, "kind": "phase", "msg": "something else entirely", "branch": 0},
    ]
    assert [(m.tick, m.kind, m.label, m.branch) for m in plot.markers(evs)] == [
        (60, "phase", "log", 0),
        (200, "phase", "stationary", 0),
        (70, "revived", "bud", 0),
        (40, "revived", "from 40", 1),
        (0, "revived", "bud", 0),
        (500, "gap", "incubator off for 2h", 0),
    ]


def test_figure_handles_one_row_a_flat_series_and_a_torn_tail():
    fig = plot.figure([row(10, 5)], [], ["population", "strains"])
    assert (fig.x0, fig.x1) == (10, 10)
    out = plot.render(fig, 60, 8).plain
    assert "ticks 10–10 · 1 row" in out
    assert sum(1 for ch in out if is_braille(ch)) == 2, "one dot per panel"
    # a series that never leaves zero sits on the floor under an honest top label
    fig = plot.figure([row(t, 0) for t in range(10, 110, 10)], [], ["population"])
    out = plot.render(fig, 60, 8).plain
    rows = panel_rows(out, plot.LABELS["population"])
    assert out.splitlines()[2].split("┤")[0].strip() == "1", "top label"
    assert not any(is_braille(ch) for r in rows[:-1] for ch in r)
    assert all((ord(ch) - 0x2800) & ~0xC0 == 0 for ch in rows[-1] if is_braille(ch)), "bottom dots only"
    # a trailing row whose tick fell back is a torn line, not a point
    rows_ = [row(t, t) for t in range(10, 101, 10)] + [{"tick": 12, "branch": None}]
    fig = plot.figure(rows_, [], ["population"])
    assert (fig.x0, fig.x1) == (10, 100) and "10 rows" in fig.title


def test_figure_orders_a_branch_by_tick_after_a_crash_resume():
    # a crash-resume reloads dish.json and re-runs ticks it had already written, without opening a
    # branch: within branch 0 the file climbs to 60, then a resume replays 40, 50 — so the last row
    # is not the highest tick, and the branch is not monotone in the file.
    rows = [row(t, t) for t in (10, 20, 30, 40, 50, 60)] + [row(t, t) for t in (40, 50)]
    fig = plot.figure(rows, [], ["population"])
    assert (fig.x0, fig.x1) == (10, 60), "the true range, not the last row's tick"
    tr = fig.panels[0].traces[0]
    assert tr.xs == [10, 20, 30, 40, 40, 50, 50, 60], "every row drawn, in tick order"
    assert len(tr.xs) == len(rows), "none silently dropped or bucketed off the axis"
    out = plot.render(fig, 80, 8).plain
    assert "8 rows" in out
    assert all(cell_len(ln) <= 80 for ln in out.splitlines())
    canvas = panel_rows(out, plot.LABELS["population"])
    assert top_of(columns(canvas)[-1]) == 0, "the highest tick reaches the right edge, not off it"


# --- the command ------------------------------------------------------------------


def test_curve_prints_a_plot_with_phase_markers(run):
    config.SEED_FILE.write_text("tide\n")
    write_curve(config.CURVE, logistic_rows(120))
    write_events(config.EVENTS, [phase(90, "log"), drop(250), phase(400, "stationary")])
    out = run(["curve", "--width", "80"])
    assert all(cell_len(ln) <= 80 for ln in out.splitlines())
    assert "seed “tide” · branch 0 · ticks 10–1200 · 120 rows" in out
    assert "population (cells)" in out and "strains living" in out
    rows = panel_rows(out, plot.LABELS["population"])
    cw = len(rows[0])
    log_col, stat_col, drop_col = (col_of(t, 10, 1200, cw) for t in (90, 400, 250))
    assert {i for i, ch in enumerate(rows[1]) if ch == plot.RULE} == {log_col, stat_col}
    assert all({rows[r][log_col], rows[r][stat_col]} == {plot.RULE} for r in range(len(rows)))
    assert rows[0][log_col + 1 :].startswith("log") and rows[0][stat_col + 1 :].startswith("stationary")
    xlabels, markers = under_axis(out)
    assert xlabels.startswith("10") and xlabels.rstrip().endswith("1200")
    assert markers.index("⚗") == drop_col and log_col < drop_col < stat_col
    cols = columns(rows)
    assert top_of(cols[-1]) < top_of(cols[0]), "the logistic curve climbs: the last column is higher"
    assert run(["curve", "--width", "80"]) == out, "no clock in the picture"


def test_curve_on_a_real_run_shows_its_phases(make_culture, run):
    c = make_culture()
    for _ in range(500):
        c.step()
    phases = [json.loads(ln) for ln in config.EVENTS.read_text().splitlines()]
    phases = [e for e in phases if e["kind"] == "phase"]
    assert [(e["tick"], e["phase"]) for e in phases] == [(60, "log"), (189, "death"), (419, "stationary")]
    for e in phases:
        assert e["msg"] == f"culture entered {e['phase']} phase"
    out = run(["curve", "--width", "80"])
    assert "seed “test” · branch 0 · ticks 10–500 · 50 rows" in out
    rows = panel_rows(out, plot.LABELS["population"])
    cw = len(rows[0])
    assert [i for i, ch in enumerate(rows[1]) if ch == plot.RULE] == [col_of(t, 10, 500, cw) for t in (60, 189, 419)]
    top = rows[0]
    assert top.index("log") < top.index("death") < top.index("stationary")
    since = run(["curve", "--width", "80", "--since", "300"])
    assert "ticks 300–500 · 21 rows" in since
    rows = panel_rows(since, plot.LABELS["population"])
    assert under_axis(since)[0].startswith("300")
    assert [i for i, ch in enumerate(rows[1]) if ch == plot.RULE] == [col_of(419, 300, 500, len(rows[0]))]
    assert "stationary" in rows[0] and "death" not in since


def test_curve_with_fifty_thousand_rows_downsamples(run, monkeypatch):
    rng = random.Random(1)
    rows = [row(10 * (i + 1), rng.randint(100, 400)) for i in range(50_000)]
    rows[20_000]["population"] = 5000  # one row's spike
    write_curve(config.CURVE, rows)
    seen: list[tuple[int, int, int]] = []
    real = plot.downsample

    def spy(xs, ys, x0, x1, buckets):
        sx, sy = real(xs, ys, x0, x1, buckets)
        seen.append((len(xs), buckets, len(sx)))
        return sx, sy

    monkeypatch.setattr(plot, "downsample", spy)
    out = run(["curve", "--width", "100"])
    assert all(cell_len(ln) <= 100 for ln in out.splitlines())
    assert "ticks 10–500000 · 50000 rows" in out
    n_in, buckets, n_out = seen[0]
    assert n_in == 50_000 and n_out <= 2 * buckets + 2
    canvas = panel_rows(out, plot.LABELS["population"])
    cw = len(canvas[0])
    assert buckets == 2 * cw
    spike = col_of(rows[20_000]["tick"], 10, 500_000, cw)
    tops = [top_of(c) for c in columns(canvas)]
    assert tops[spike] == 0, "the spike reaches the top row"
    assert [i for i, t in enumerate(tops) if t == 0] == [spike], "and nothing else does"


def test_curve_plots_the_last_branch_and_joins_markers_on_branch_and_tick(run):
    rows = [row(t, t) for t in range(10, 150, 10)] + [row(50, 8, branch=1), row(60, 9, branch=1)]
    write_curve(config.CURVE, rows)
    write_events(config.EVENTS, [drop(55), dish_revive(40, was=140, branch=1), drop(55)])
    out = run(["curve", "--width", "80"])
    assert "branch 1 · ticks 50–60 · 2 rows" in out
    xlabels, markers = under_axis(out)
    assert xlabels.startswith("50") and xlabels.rstrip().endswith("60")
    assert markers.count("⚗") == 1 and markers[0] == "↺", "the branch's own drop, and the revive that opened it"
    out0 = run(["curve", "--width", "80", "--branch", "0"])
    assert "branch 0 · ticks 10–140 · 14 rows" in out0
    xlabels, markers = under_axis(out0)
    assert xlabels.startswith("10") and xlabels.rstrip().endswith("140")
    assert markers.count("⚗") == 1 and "↺" not in markers
    since = run(["curve", "--width", "80", "--since", "45"])
    assert "ticks 50–60" in since and "↺" not in since and under_axis(since)[1].count("⚗") == 1
    assert "↺" in under_axis(run(["curve", "--width", "80", "--since", "40"]))[1], "since at the opener keeps it"
    with pytest.raises(SystemExit, match="no branch 3 in the curve; it has 0, 1"):
        main(["curve", "--branch", "3"])


def test_cols_pick_panels_and_an_old_file_says_what_it_lacks(run):
    write_curve(config.CURVE, [row(t, t, shannon=0.5, nutrient=0.4) for t in range(10, 210, 10)])
    out = run(["curve", "--width", "80", "--cols", "population,shannon,nutrient"])
    labels = [plot.LABELS[c] for c in ("population", "shannon", "nutrient")]
    assert [out.index(lb) for lb in labels] == sorted(out.index(lb) for lb in labels)
    assert [len(panel_rows(out, lb)) for lb in labels] == [12, 6, 6]
    config.CURVE.write_text(OLD_HEADER + "\n" + "\n".join(OLD_ROWS) + "\n")
    out = run(["curve", "--width", "80", "--cols", "population,shannon"])
    assert "ticks 10–30 · 3 rows" in out and "population (cells)" in out
    assert "no values for shannon in this file" in out
    with pytest.raises(SystemExit, match="'phase' is not a column that can be plotted; pick from: population"):
        main(["curve", "--cols", "phase"])


def test_png_says_how_to_install_matplotlib_when_absent(tmp_path, monkeypatch, capsys):
    write_curve(config.CURVE, logistic_rows(20))
    monkeypatch.setattr(plot, "_pyplot", lambda: None)
    target = tmp_path / "c.png"
    with pytest.raises(SystemExit, match="uv sync --extra plot"):
        main(["curve", "--png", str(target)])
    assert not target.exists() and capsys.readouterr().out == ""


def test_png_is_written_through_the_pyplot_seam(tmp_path, monkeypatch, run):
    class Axis:
        transAxes = object()

        def __init__(self):
            self.calls: list[tuple] = []
            self.blended = object()  # what get_xaxis_transform returns: x in data, y in axes fraction

        def get_xaxis_transform(self):
            self.calls.append(("get_xaxis_transform", (), {}))
            return self.blended

        def __getattr__(self, name):
            def record(*a, **kw):
                self.calls.append((name, a, kw))

            return record

        def named(self, what):
            return [(a, kw) for n, a, kw in self.calls if n == what]

    class Fig:
        def __init__(self):
            self.title = None
            self.saved = None

        def suptitle(self, t):
            self.title = t

        def savefig(self, path, **kw):
            self.saved = (path, kw)
            Path(path).write_bytes(b"\x89PNG stub")

    made: list = []
    closed: list = []

    def subplots(n, m, **kw):
        f, axes = Fig(), [Axis() for _ in range(n)]
        made.append((n, m, kw, f, axes))
        return f, (axes if n > 1 else axes[0])

    monkeypatch.setattr(plot, "_pyplot", lambda: SimpleNamespace(subplots=subplots, close=closed.append))
    config.SEED_FILE.write_text("costs $3\n")
    write_curve(config.CURVE, logistic_rows(60))
    write_events(config.EVENTS, [phase(90, "log"), drop(250), phase(400, "stationary")])
    target = tmp_path / "out" / "c.png"
    target.parent.mkdir()
    out = run(["curve", "--png", str(target)])
    assert out == f"wrote {target}\n"
    assert target.read_bytes().startswith(b"\x89PNG")
    ((n, m, kw, f, axes),) = made
    assert (n, m, kw["sharex"], kw["height_ratios"]) == (2, 1, True, [2, 1])
    assert [ax.named("set_ylabel")[0][0][0] for ax in axes] == [plot.LABELS["population"], plot.LABELS["strains"]]
    assert len(axes[0].named("plot")) == 1 and axes[0].named("plot")[0][0][0] == [r["tick"] for r in logistic_rows(60)]
    assert len(axes[0].named("axvline")) == 3 and axes[1].named("axvline") == []
    texts = axes[0].named("text")
    assert [a[2] for a, _ in texts] == ["log", "drop nutrient", "stationary"]
    # the labels ride their rules at the axes-fraction top (phase) and foot (other) through the
    # blended transform, so they stay on the panel whatever the autoscaled data y-range is — not
    # at a data y that can fall outside it.
    assert [a[1] for a, _ in texts] == [1.0, 0.0, 1.0]
    assert all(kw["transform"] is axes[0].blended for _, kw in texts)
    assert axes[1].named("set_xlabel") == [(("tick",), {})]
    assert f.title == "seed “costs \\$3” · branch 0 · ticks 10–600 · 60 rows", "mathtext escaped"
    assert f.saved[0] == target and closed == [f]


def test_png_renders_with_matplotlib_when_installed(tmp_path, run):
    pytest.importorskip("matplotlib")
    config.SEED_FILE.write_text("costs $3\n")
    write_curve(config.CURVE, logistic_rows(60))
    write_events(config.EVENTS, [phase(90, "log"), drop(250), phase(400, "stationary")])
    target = tmp_path / "c.png"
    out = run(["curve", "--png", str(target), "--cols", "population,strains,shannon"])
    assert out == f"wrote {target}\n"
    assert target.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_curve_without_a_curve_or_rows_says_so(capsys):
    with pytest.raises(SystemExit, match="no growth curve yet"):
        main(["curve"])
    config.CURVE.write_text(",".join(curve.COLUMNS) + "\n")
    with pytest.raises(SystemExit, match="the growth curve has no rows yet"):
        main(["curve"])
    write_curve(config.CURVE, [row(t, t) for t in range(10, 110, 10)])
    with pytest.raises(SystemExit, match="no rows from tick 999999"):
        main(["curve", "--since", "999999"])
    with open(config.CURVE, "a") as f:
        f.write("110,five,1,0.5,log,0,0,0,0,0,0.0,1.0,0.0,1,0,0.0,0,0,0\n")
    with pytest.raises(SystemExit, match="could not read .*curve.csv: curve.csv line 12, population: 'five'"):
        main(["curve"])
    assert capsys.readouterr().out == ""


def test_curve_reports_an_unreadable_log_or_seed_cleanly(capsys):
    # events.jsonl and seed.txt are read like curve.csv: an OSError on either (a delete racing the
    # exists() check, a permission change) is a clean message, not an uncaught traceback.
    write_curve(config.CURVE, [row(t, t) for t in range(10, 60, 10)])
    config.EVENTS.mkdir()  # a path where the log should be a file: open() raises OSError
    with pytest.raises(SystemExit, match="could not read"):
        main(["curve"])
    assert capsys.readouterr().out == ""
    config.EVENTS.rmdir()
    config.SEED_FILE.mkdir()  # the same for the seed
    with pytest.raises(SystemExit, match="could not read"):
        main(["curve"])
    assert capsys.readouterr().out == ""


def test_curve_reads_beside_a_running_incubator_and_writes_nothing(make_culture, run):
    c = make_culture()
    for _ in range(200):
        c.step()
    with open(config.CURVE, "a") as f:
        f.write("21")  # a row torn inside its tick
    with open(config.EVENTS, "a") as f:
        f.write('{"t": 1, "ki')

    def files() -> dict[Path, int]:
        return {p: p.stat().st_mtime_ns for p in config.VESSEL.rglob("*") if p.is_file()}

    before = files()
    assert config.DISH_FILE in before, "the culture saved at tick 150; curve must not touch it"
    out = run(["curve", "--width", "80"])
    assert "ticks 10–200 · 20 rows" in out and "log" in out
    assert files() == before and incubating() is None
    f = open(config.LOCK_FILE, "a+")
    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    f.write("4242\n")
    f.flush()
    try:
        assert incubating() == 4242
        assert run(["curve", "--width", "80"]) == out, "the plot needs no lock"
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()


def test_render_never_exceeds_the_width_and_fits_small_terminals():
    write_events(config.EVENTS, [phase(90, "log"), drop(300), phase(400, "stationary"), phase(800, "death")])
    with open(config.EVENTS, "a") as f:
        f.write(json.dumps({"t": 9.0, "tick": 900, "kind": "gap", "msg": "incubator off for 2h"}) + "\n")
    seed = "a seed long enough that a forty-column terminal cannot hold the title"
    fig = plot.figure(logistic_rows(120), curve.events(), ["population", "strains", "shannon"], seed=seed)
    for w in (40, 60, 80, 120, 200):
        for h in (4, 12):
            text = plot.render(fig, w, h).plain
            lines = text.splitlines()
            assert all(cell_len(ln) <= w for ln in lines), (w, h)
            assert any(is_braille(ch) for ch in text)
            assert text.count(plot.RULE) == 3 * h, "three rules through every row of the main panel"
            assert "⚗" in lines[-1] and "⋯" in lines[-1], "the marker row"
            assert plot.render(fig, w, h).plain == text
    assert plot.render(fig, 40, 4).plain.splitlines()[0].endswith("…")
