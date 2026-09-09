"""Diversity and turnover: what the dish and the culture report, and what the growth curve holds."""

from __future__ import annotations

import csv
import io
import json
import math
import threading

import pytest
from rich.console import Console
from rich.panel import Panel

from bio import config, curve
from bio.__main__ import main
from bio.culture import FALLBACK_GENESIS
from bio.dish import Dish
from bio.tui import events as log_panel
from bio.tui import vitals

OLD_HEADER = "tick,population,strains,nutrient,phase,births,starved,lysed,senescent"
NEW_HEADER = OLD_HEADER + ",killed,shannon,dominance,mean_gen,arisen,extinct,pheromone,mutations_ready,mutations_taken"
OLD_ROWS = [
    "10,5,1,0.7103,lag,0,0,0,0",
    "20,10,1,0.7314,lag,5,0,0,0",
    "30,12,1,0.7280,lag,7,0,0,0",
]


def _dish(seed: str = "test", strains: dict[str, int] | None = None) -> Dish:
    """A 24x12 dish; if `strains` is given, that many cells of each id are placed near the centre."""
    d = Dish(seed, width=24, height=12)
    if strains:
        cx, cy = d.center()
        spots = iter((cx + dx, cy + dy) for dy in (-1, 0, 1) for dx in range(-3, 4))
        for sid, n in strains.items():
            d.register(sid, FALLBACK_GENESIS)
            for _ in range(n):
                assert d.place(*next(spots), sid) is not None
    return d


def _events(c, kind: str) -> list[dict]:
    return [ev for ev in c.events if ev["kind"] == kind]


# --- the dish ---------------------------------------------------------------


def test_monoculture_has_zero_shannon_and_full_dominance():
    d = _dish()
    d.register("f", FALLBACK_GENESIS)
    d.inoculate("f")
    for _ in range(30):
        d.step()
    m = d.metrics()
    assert m["strains"] == 1
    assert m["shannon"] == 0.0
    assert m["dominance"] == 1.0
    assert f"{m['shannon']:.4f}" == "0.0000"  # not -0.0000


def test_shannon_of_an_even_mixture_is_log_strain_count():
    m = _dish(strains={"a": 4, "b": 4, "c": 4}).metrics()
    assert m["population"] == 12 and m["strains"] == 3
    assert m["shannon"] == pytest.approx(math.log(3))
    assert m["dominance"] == pytest.approx(1 / 3)


def test_a_sweep_reads_as_high_dominance_and_low_shannon():
    m = _dish(strains={"a": 9, "b": 1}).metrics()
    assert m["dominance"] == 0.9
    assert m["shannon"] == pytest.approx(-(0.9 * math.log(0.9) + 0.1 * math.log(0.1)), abs=1e-4)
    assert m["shannon"] == pytest.approx(0.3251, abs=1e-4)


def test_sterile_dish_metrics_are_zero():
    m = _dish().metrics()
    assert m["population"] == 0 and m["strains"] == 0
    assert m["shannon"] == 0.0 and m["dominance"] == 0.0 and m["pheromone"] == 0.0
    assert m["births"] == 0 and m["killed"] == 0


def test_pheromone_mean_reflects_emission():
    d = _dish()
    assert d.pheromone_mean() == 0.0
    cx, cy = d.center()
    d.pheromone[cy][cx] = 1.0
    assert d.pheromone_mean() == pytest.approx(1 / d.tiles)
    emitter = _dish()
    emitter.register("e", "def live(me):\n    return ('emit', 1.0)\n")
    emitter.place(*emitter.center(), "e")
    emitter.step()
    total = sum(v for y, row in enumerate(emitter.pheromone) for x, v in enumerate(row) if emitter.mask[y][x])
    assert emitter.pheromone_mean() > 0
    assert emitter.pheromone_mean() == pytest.approx(total / emitter.tiles)
    assert emitter.metrics()["pheromone"] == emitter.pheromone_mean()


def test_dish_metrics_do_not_change_the_trajectory():
    quiet, watched = _dish(), _dish()
    for d in (quiet, watched):
        d.register("f", FALLBACK_GENESIS)
        d.inoculate("f")
    for _ in range(100):
        quiet.step()
        watched.step()
        watched.metrics()
    assert watched.census() == quiet.census()
    assert watched.rng.getstate() == quiet.rng.getstate()
    assert watched.nutrient == quiet.nutrient
    assert watched.deaths == quiet.deaths


def test_culture_observers_do_not_change_the_trajectory(make_culture):
    """A culture polled by the eyepiece every tick walks the same path as a bare dish."""
    c = make_culture()
    bare = _dish()
    bare.register("f", FALLBACK_GENESIS)
    bare.inoculate("f")
    for _ in range(60):
        c.step()
        c.snapshot()
        bare.step()
    assert sorted(c.dish.cells) == sorted(bare.cells)
    assert c.dish.rng.getstate() == bare.rng.getstate()
    assert c.dish.nutrient == bare.nutrient
    assert c.dish.births == bare.births and c.dish.deaths == bare.deaths


def test_snapshot_reads_the_agar_once(make_culture):
    """The vitals' agar figure and the curve's nutrient column are the same reading."""
    c = make_culture()
    for _ in range(5):
        c.step()
    s = c.snapshot()
    assert s["nutrient"] == s["metrics"]["nutrient"] == c.dish.nutrient_mean()
    assert s["population"] == s["metrics"]["population"] == sum(s["census"].values())


def test_metrics_survive_a_round_trip():
    d = _dish()
    d.register("f", FALLBACK_GENESIS)
    d.inoculate("f")
    for _ in range(10):
        d.step()
    assert Dish.from_dict(d.to_dict()).metrics() == d.metrics()


# --- the culture ------------------------------------------------------------


def test_culture_metrics_count_lineage_and_turnover(make_culture):
    c = make_culture()
    founder = next(iter(c.registry.strains.values()))
    child = c.registry.new(FALLBACK_GENESIS, founder.id, 0, "child", "")
    c.dish.register(child.id, FALLBACK_GENESIS)
    cx, cy = c.dish.center()
    placed = 0
    for dy in range(-3, 4):
        for dx in range(-6, 7):
            if placed < 3 and c.dish.place(cx + dx, cy + dy, child.id):
                placed += 1
    assert placed == 3
    m = c.metrics()
    assert m["population"] == config.INOCULUM + 3 and m["strains"] == 2
    assert m["arisen"] == 2 and m["mutations_taken"] == 1 and m["extinct"] == 0
    assert m["mutations_ready"] == 0
    assert m["mean_gen"] == pytest.approx(3 / m["population"])  # founder gen 0, child gen 1
    assert m["shannon"] == pytest.approx(-(5 / 8 * math.log(5 / 8) + 3 / 8 * math.log(3 / 8)))

    c.step()  # the registry records the child's peak; extinction needs peak > 0
    for pos, cell in list(c.dish.cells.items()):
        if cell.strain == child.id:
            del c.dish.cells[pos]
    c.step()
    m = c.metrics()
    assert m["extinct"] == 1 and m["arisen"] == 2 and m["mutations_taken"] == 1 and m["strains"] == 1
    assert m["shannon"] == 0.0 and m["dominance"] == 1.0
    gone = _events(c, "extinct")
    assert len(gone) == 1 and gone[0]["strain"] == child.id


def test_death_ledger_closes_after_an_antibiotic_disc(make_culture):
    c = make_culture()
    for _ in range(40):
        c.step()
    m = c.metrics()
    assert m["births"] > 0
    assert m["births"] - (m["starved"] + m["lysed"] + m["senescent"] + m["killed"]) == m["population"] - config.INOCULUM
    msg = c.drop("antibiotic", at=c.dish.center(), r=2.0)
    assert "killed" in msg
    for _ in range(10):
        c.step()
    m = c.metrics()
    assert m["killed"] > 0
    assert m["births"] - (m["starved"] + m["lysed"] + m["senescent"] + m["killed"]) == m["population"] - config.INOCULUM
    assert curve.read()[-1]["killed"] == m["killed"]


# --- the growth curve -------------------------------------------------------


def test_curve_has_the_new_columns(make_culture):
    c = make_culture()
    for _ in range(20):
        c.step()
    header = config.CURVE.read_text().splitlines()[0].split(",")
    assert header == list(curve.COLUMNS)
    assert header[:9] == OLD_HEADER.split(",")  # the prefix rule: what 0.1.0 wrote, in its order
    assert header == NEW_HEADER.split(",")  # the full order docs/curve.md promises is stable
    rows = curve.read()
    assert [r["tick"] for r in rows] == [10, 20]
    first = rows[0]
    assert first["shannon"] == 0.0 and first["dominance"] == 1.0
    assert isinstance(first["phase"], str) and first["phase"] in ("lag", "log")
    assert first["killed"] == 0 and first["arisen"] == 1 and first["extinct"] == 0
    assert first["mutations_ready"] == 0 and first["mutations_taken"] == 0
    assert isinstance(first["nutrient"], float) and isinstance(first["mean_gen"], float)
    assert (
        first["population"]
        == first["births"] - sum(first[k] for k in ("starved", "lysed", "senescent", "killed")) + config.INOCULUM
    )
    assert not _events(c, "curve")


def test_old_curve_is_widened_in_place(make_culture):
    config.CURVE.write_text(OLD_HEADER + "\n" + "\n".join(OLD_ROWS) + "\n")
    c = make_culture()
    c.dish.tick = 30  # resuming a dish that had already written three rows
    for _ in range(20):
        c.step()
    lines = config.CURVE.read_text().splitlines()
    assert lines[0].split(",") == list(curve.COLUMNS)
    assert lines[1].startswith("10,5,1,0.7103,lag,0,0,0,0,")
    rows = curve.read()
    assert [r["tick"] for r in rows] == [10, 20, 30, 40, 50]
    old, new = rows[0], rows[-1]
    assert old["population"] == 5 and old["nutrient"] == 0.7103 and old["phase"] == "lag"
    assert old["shannon"] is None and old["killed"] is None and old["mutations_taken"] is None
    assert isinstance(new["shannon"], float) and new["killed"] == 0
    widened = _events(c, "curve")
    assert len(widened) == 1
    assert "9 columns added" in widened[0]["msg"] and "shannon" in widened[0]["msg"]
    assert not config.CURVE.with_name("curve.csv.tmp").exists()
    with open(config.CURVE, newline="") as f:
        assert {len(r) for r in csv.reader(f)} == {len(curve.COLUMNS)}


def test_read_tolerates_an_old_curve(tmp_path):
    old = tmp_path / "old.csv"
    old.write_text(OLD_HEADER + "\n" + "\n".join(OLD_ROWS) + "\n")
    rows = curve.read(old)
    assert len(rows) == 3
    for r in rows:
        assert set(curve.COLUMNS) <= set(r)
    assert [r["tick"] for r in rows] == [10, 20, 30]
    assert rows[1]["population"] == 10 and rows[1]["nutrient"] == 0.7314 and rows[1]["phase"] == "lag"
    assert all(rows[0][k] is None for k in curve.COLUMNS[9:])
    assert old.read_text().splitlines()[0] == OLD_HEADER  # reading never widens
    assert curve.read(tmp_path / "absent.csv") == []


def test_unknown_columns_are_kept(make_culture):
    header = list(curve.COLUMNS) + ["mystery"]
    row = ["10", "5", "1", "0.7000", "lag", "0", "0", "0", "0", "0", "0.0000", "1.0000", "0.00", "1", "0"]
    row += ["0.0000", "0", "0", "x"]
    config.CURVE.write_text(",".join(header) + "\n" + ",".join(row) + "\n")
    c = make_culture()
    for _ in range(10):
        c.step()
    lines = config.CURVE.read_text().splitlines()
    assert lines[0].split(",") == header
    assert len(lines) == 3
    rows = curve.read()
    assert rows[0]["mystery"] == "x" and rows[0]["tick"] == 10
    assert rows[1]["mystery"] == "" and rows[1]["tick"] == 10
    with open(config.CURVE, newline="") as f:
        assert {len(r) for r in csv.reader(f)} == {19}
    assert not _events(c, "curve")


def test_appending_after_the_curve_is_removed_writes_a_header(make_culture):
    c = make_culture()
    for _ in range(10):
        c.step()
    config.CURVE.unlink()
    for _ in range(10):
        c.step()
    lines = config.CURVE.read_text().splitlines()
    assert lines[0].split(",") == list(curve.COLUMNS)
    assert curve.read()[0]["tick"] == 20


def test_a_headerless_curve_gets_a_header_with_the_next_row(make_culture):
    """A file truncated to a blank line has no header: reconcile leaves it and append starts it over,
    so the header is the first line and the row is not mistaken for one."""
    config.CURVE.write_text("\n")
    assert curve.read() == []
    assert curve.reconcile(config.CURVE) == (list(curve.COLUMNS), [])
    assert config.CURVE.read_text() == "\n"
    c = make_culture()
    for _ in range(10):
        c.step()
    lines = config.CURVE.read_text().splitlines()
    assert lines[0].split(",") == list(curve.COLUMNS) and len(lines) == 2
    assert [r["tick"] for r in curve.read()] == [10]
    assert not _events(c, "curve")


def test_blank_lines_before_the_header_are_not_the_header(tmp_path):
    """The header is the first non-blank row, so only a file with no row at all counts as headerless
    and nothing readable is ever started over."""
    p = tmp_path / "curve.csv"
    p.write_text("\n\n" + OLD_HEADER + "\n" + "\n".join(OLD_ROWS) + "\n")
    assert [r["tick"] for r in curve.read(p)] == [10, 20, 30]
    fields, added = curve.reconcile(p)
    assert fields == list(curve.COLUMNS) and added == list(curve.COLUMNS[9:])
    lines = p.read_text().splitlines()
    assert lines[0] == ",".join(curve.COLUMNS) and len(lines) == 4  # the rewrite drops the blank lines
    assert [r["tick"] for r in curve.read(p)] == [10, 20, 30]


def test_a_spreadsheets_byte_order_mark_is_not_a_column(make_culture):
    """Excel's 'CSV UTF-8' save prefixes a byte-order mark; `tick` must still be recognised as tick."""
    bom = "\ufeff"
    config.CURVE.write_bytes((bom + OLD_HEADER + "\n" + "\n".join(OLD_ROWS) + "\n").encode())
    fields, added = curve.reconcile(config.CURVE)
    assert fields == list(curve.COLUMNS) and added == list(curve.COLUMNS[9:])
    assert config.CURVE.read_bytes().startswith(b"tick,")  # rewritten without the mark
    assert curve.read()[0]["tick"] == 10
    # a file with every column and a mark is read in place, not rewritten
    row = "10,5,1,0.7000,lag,0,0,0,0,0,0.0000,1.0000,0.00,1,0,0.0000,0,0"
    config.CURVE.write_bytes((bom + ",".join(curve.COLUMNS) + "\n" + row + "\n").encode())
    assert curve.reconcile(config.CURVE) == (list(curve.COLUMNS), [])
    assert config.CURVE.read_bytes().startswith(bom.encode())
    rows = curve.read()
    assert rows[0]["tick"] == 10 and set(rows[0]) == set(curve.COLUMNS)
    c = make_culture()
    for _ in range(10):
        c.step()
    with open(config.CURVE, newline="", encoding="utf-8-sig") as f:
        assert {len(r) for r in csv.reader(f)} == {len(curve.COLUMNS)}
    assert [r["tick"] for r in curve.read()] == [10, 10]
    assert not _events(c, "curve")


def test_a_curve_the_culture_cannot_read_does_not_stop_the_dish(make_culture):
    damaged = b"tick,population\xff\n10,5\n"
    config.CURVE.write_bytes(damaged)
    c = make_culture()
    for _ in range(20):
        c.step()
    assert c.dish.tick == 20
    assert config.CURVE.read_bytes() == damaged
    said = _events(c, "curve")
    assert len(said) == 1  # once, not every row
    assert said[0]["msg"].startswith("growth curve not written from tick 10: ") and "codec" in said[0]["msg"]
    config.CURVE.unlink()  # the repair
    for _ in range(10):
        c.step()
    assert [ev["msg"] for ev in _events(c, "curve")][1:] == ["growth curve resumed at tick 30"]
    assert config.CURVE.read_text().splitlines()[0].split(",") == list(curve.COLUMNS)
    assert [r["tick"] for r in curve.read()] == [30]


def test_a_failed_rewrite_leaves_the_file_and_no_temporary(tmp_path):
    p = tmp_path / "curve.csv"
    text = OLD_HEADER + "\n" + OLD_ROWS[0] + "\n" + "20,10,1,0.7314," + "x" * 40 + ",5,0,0,0\n"
    p.write_text(text)
    limit = csv.field_size_limit(30)  # the header reads; the second row does not
    try:
        with pytest.raises(curve.ERRORS):
            curve.reconcile(p)
    finally:
        csv.field_size_limit(limit)
    assert p.read_text() == text
    assert not p.with_name("curve.csv.tmp").exists()


# --- the eyepiece, status, run ----------------------------------------------


def _render(renderable, width: int) -> list[str]:
    console = Console(file=io.StringIO(), width=width, force_terminal=False)
    console.print(renderable)
    return console.file.getvalue().splitlines()


def test_vitals_show_diversity_next_to_the_strain_count(make_culture):
    c = make_culture()
    for _ in range(5):
        c.step()
    lines = _render(vitals(c, c.snapshot()), 80)
    strains = next(i for i, ln in enumerate(lines) if ln.lstrip().startswith("strains"))
    assert "1  1 arisen  0 extinct" in lines[strains]
    assert lines[strains + 1].lstrip().startswith("diversity")
    assert "H 0.00" in lines[strains + 1]
    assert "dominance 100%" in lines[strains + 1]
    assert "gen 0.0" in lines[strains + 1]


def test_vitals_rows_fit_the_side_panel(make_culture):
    """At the default 120-column bench the side panel is 48 cells wide; the two rows must not wrap
    even with three-digit counts, full dominance and a two-digit mean generation."""
    c = make_culture()
    snap = c.snapshot()
    snap["census"] = {f"s{i}": 1 for i in range(123)}
    snap["metrics"].update(shannon=4.81, dominance=1.0, mean_gen=12.3, arisen=456, extinct=789)
    lines = _render(Panel(vitals(c, snap), title="vitals"), 48)
    labels = [ln[2:13].strip() for ln in lines]
    s = labels.index("strains")
    assert labels[s + 1] == "diversity" and labels[s + 2] == "agar"
    assert "123  456 arisen  789 extinct" in lines[s]
    assert "H 4.81  dominance 100%  gen 12.3" in lines[s + 1]


def test_the_log_panel_marks_curve_events(make_culture):
    c = make_culture()
    c.log("curve", "growth curve widened: 9 columns added (killed)")
    line = [ln for ln in _render(log_panel(c, 1), 120) if ln.strip()][-1]
    assert "≡ growth curve widened" in line


def test_status_prints_diversity(make_culture, capsys):
    c = make_culture()
    for _ in range(5):
        c.step()
    c.save()
    main(["status"])
    out = capsys.readouterr().out
    assert "strains     1 living / 1 arisen / 0 extinct" in out
    assert "diversity   H 0.000 nats · dominance 1.00 · mean generation 0.0" in out


def test_run_reports_diversity_in_its_progress_line(make_culture, capsys):
    c = make_culture()
    c.save()
    main(["run", "--ticks", "20", "--tick", "0", "--quiet"])
    err = capsys.readouterr().err
    assert "tick     20" in err
    assert "H 0.00" in err
    assert [r["tick"] for r in curve.read()] == [10, 20]


def test_run_starts_the_mutagen_thread_and_a_dormant_one_exits(make_culture, capsys):
    """Culture.run() is the one path in the suite that starts the mutagen thread. With no key the
    mind is dormant, so the thread says so once and returns; nothing outlives the run."""
    c = make_culture()
    c.save()
    main(["run", "--ticks", "10", "--tick", "0", "--quiet"])
    capsys.readouterr()
    for t in threading.enumerate():
        if t.name == "mutagen":
            t.join(1.0)  # close() sets the stop flag and does not join; give a live one a moment
    assert not any(t.name == "mutagen" and t.is_alive() for t in threading.enumerate())
    said = [json.loads(ln) for ln in config.EVENTS.read_text().splitlines()]
    dormant = [ev for ev in said if ev["kind"] == "mind" and ev["msg"].startswith("mutagen dormant")]
    assert len(dormant) == 1
