"""The eyepiece fits the terminal it is watched from: the agar is never clipped, a dish larger
than the window is shown at reduced resolution with a badge, the side panel folds into a strip,
the log gives way before the agar does, the census closes on screen and counts what it cannot
list, the header keeps its heartbeat and the footer its ctrl-c hint on one row, a resize is
fitted by the next frame, the log panel survives the other threads appending to the event deque,
and a frame that fails is logged rather than frozen over."""

from __future__ import annotations

import io
import os
import re
import shutil
import sys
import threading
from types import SimpleNamespace

import pytest
from rich.cells import cell_len
from rich.console import Console
from rich.layout import Layout
from rich.screen import Screen
from rich.text import Text

from bio import config, tui
from bio.culture import FALLBACK_GENESIS, _fit_dish
from bio.dish import Dish
from bio.strains import Registry
from bio.tui import (
    CENSUS_ROWS,
    CHROME_H,
    LOG_H,
    LOG_MIN,
    SIDE_MIN,
    VITALS_H,
    Fit,
    build,
    events,
    fit,
    footer,
    frame,
    header,
    plan,
    redraw,
    render_dish,
    vitals_strip,
)

# --- helpers ------------------------------------------------------------------


@pytest.fixture(autouse=True)
def steady_clock(monkeypatch):
    """Take the wall clock out of the dish: the 4 ms lysis budget could lyse a cell in one seeded
    culture and not in its twin when the scheduler stalls. dish.py reads the constant at call time."""
    monkeypatch.setattr(config, "CELL_TIME_BUDGET", 60.0)


def grow(c, n: int) -> None:
    for _ in range(n):
        c.step()


@pytest.fixture
def culture(make_culture):
    """A culture of the given dish size, grown `ticks` ticks on the main thread."""

    def _make(w: int, h: int, ticks: int = 0, seed: str = "test"):
        c = make_culture(seed, w, h)
        grow(c, ticks)
        return c

    return _make


def strains(c, n: int, name: str = "strain_with_a_long_name") -> int:
    """Add n living strains beside the founder, by hand: the i-th holds i + 1 cells on the first
    free tiles, so the census has a strict order, and the names are as long as a name can be.
    Returns the number of strains now living."""
    founder = next(iter(c.registry.strains.values()))
    free = (
        (x, y) for y in range(c.dish.h) for x in range(c.dish.w) if c.dish.inside(x, y) and (x, y) not in c.dish.cells
    )
    for i in range(n):
        s = c.registry.new(FALLBACK_GENESIS + "\n" * (i + 1), founder.id, c.dish.tick, f"{name}_{i:02d}", "")
        for _ in range(i + 1):
            x, y = next(free)
            assert c.dish.place(x, y, s.id) is not None
    return len(c.dish.census())


def window(w: int, h: int) -> Console:
    """A terminal of w×h cells that records what is printed to it."""
    return Console(width=w, height=h, file=io.StringIO(), force_terminal=True, color_system="truecolor", record=True)


def paint(renderable, w: int, h: int) -> str:
    """Put a frame on a w×h terminal the way Live does in alternate-screen mode: exactly w×h cells."""
    con = window(w, h)
    con.print(Screen(renderable))
    return con.export_text()


def shot(c, w: int, h: int) -> str:
    """One frame of the culture, built for and painted on a w×h terminal."""
    return paint(build(c, (w, h)), w, h)


def planned(c, size: tuple[int, int]) -> Fit | None:
    """The fit build() uses for this culture at `size`: its vitals panel measured as it is drawn."""
    return plan(c, c.snapshot(), size)


def rows_of(fr: str) -> list[str]:
    """A painted frame as rows: Screen paints exactly the terminal's rows, with no newline after the last."""
    return fr.split("\n")


def census_height(living: int, avail: int) -> int:
    """Rows census_table() fills for `living` strains in `avail` rows: the strains it lists, and the
    `… n more` line when it cannot list them all."""
    shown = living if living <= min(CENSUS_ROWS, avail) else min(CENSUS_ROWS, avail - 1)
    return shown + (shown < living)


def assert_unclipped(fr: str, f: Fit, rows: int | None = None, living: int | None = None) -> None:
    """The header keeps its heartbeat, the agar panel is whole, every panel the fit promised is
    there and closes its border on screen, and the footer keeps the ctrl-c hint. The census panel
    takes its natural height, so it is at most the rows the fit gave it, and exactly the rows its
    strains fill when `living` says how many there are."""
    lines = rows_of(fr)
    if rows is not None:
        assert len(lines) == rows, "the frame has other rows than the terminal"
    assert "♥" in lines[0] or "♡" in lines[0], "heartbeat lost from the header row"
    assert "ctrl-c" in lines[-1], "footer row lost its ctrl-c hint"
    top = next(i for i, ln in enumerate(lines) if ln.startswith("╭") and "agar" in ln)
    bot = next(i for i in range(top + 1, len(lines)) if lines[i].startswith("╰"))
    assert bot - top >= f.panel_h - 1, "agar panel cropped vertically"  # it may stretch to fill the body
    assert lines[top][f.panel_w - 1] == "╮", "agar panel cropped horizontally"
    if f.log_h:
        log_top = next(i for i, ln in enumerate(lines) if "incubator log" in ln)
        assert lines[log_top + f.log_h - 1].startswith("╰"), "log panel does not close on screen"
    if f.side:
        x = f.panel_w  # the side column starts where the agar panel ends
        corner = [ln[x] if len(ln) > x else " " for ln in lines]
        vit_top = next(i for i, ln in enumerate(lines) if corner[i] == "╭" and "vitals" in ln)
        vit_bot = next(i for i in range(vit_top + 1, len(lines)) if corner[i] == "╰")
        cen_top = next(i for i in range(vit_bot + 1, len(lines)) if corner[i] == "╭" and "census" in lines[i])
        cen_bot = next((i for i in range(cen_top + 1, len(lines)) if corner[i] == "╰"), None)
        assert cen_bot is not None, "census panel does not close on screen"
        assert cen_bot <= bot, "census panel runs below the agar panel"
        assert cen_bot - cen_top - 1 <= f.census_rows, "census panel has more rows than the fit gave it"
        if living is not None:
            assert cen_bot - cen_top - 1 == census_height(living, f.census_rows), "census rows are not its strains"
    else:
        assert " pop " in fr, "vitals strip missing"


def style_at(text: Text, offset: int) -> str:
    return next(str(sp.style) for sp in text.spans if sp.start <= offset < sp.end)


class Bounded(threading.Event):
    """A stop event that sets itself after `budget` waits. redraw() swallows everything a frame
    raises and Lens.update() is the only other place that sets the event, so without a bound a
    build() that failed on every call would spin the loop forever and hang the suite."""

    def __init__(self, budget: int = 200):
        super().__init__()
        self.budget, self.waits = budget, 0

    def wait(self, timeout=None):
        self.waits += 1
        if self.waits > self.budget:
            self.set()
        return super().wait(timeout)


class Lens:
    """Stands in for rich.Live under `redraw`: keeps every frame the render thread pushes with the
    size the console reported for it, then resizes the console as a resize would, following `plan`,
    and stops the loop when the plan is exhausted. Nothing is asserted in here: an AssertionError
    raised inside update() would be swallowed by redraw() like any other frame failure."""

    def __init__(self, con: Console, stop: threading.Event, plan: list[tuple[int, int]] = ()):
        self.con, self.stop, self.plan = con, stop, list(plan)
        self.frames: list[tuple[object, tuple[int, int]]] = []
        self.unrefreshed = 0  # frames pushed without refresh=True; auto_refresh is off, so those would never be painted

    def update(self, renderable, refresh: bool = False) -> None:
        self.unrefreshed += not refresh
        self.frames.append((renderable, tuple(self.con.size)))
        if self.plan:
            self.con.size = self.plan.pop(0)
        else:
            self.stop.set()


def watch(c, con: Console, plan: list[tuple[int, int]] = ()) -> Lens:
    """redraw() under a Lens until its plan is exhausted; a loop that never gets that far fails
    here instead of hanging."""
    stop = Bounded()
    lens = Lens(con, stop, plan)
    redraw(c, con, lens, stop, period=0.001)
    assert stop.waits <= stop.budget, "redraw() ran out of attempts before the plan was exhausted"
    assert not lens.plan and lens.unrefreshed == 0
    return lens


# --- fit: the pure layout decision ---------------------------------------------


@pytest.mark.parametrize(
    ("dish", "term", "expect"),
    [
        ((96, 35), (150, 50), Fit(1, True, 9, 24, 96, 35)),  # the terminal it was poured on: today's layout, unchanged
        ((96, 35), (100, 30), Fit(2, True, 8, 5, 48, 18)),  # acceptance criterion 1: half resolution, side panel kept
        ((40, 18), (80, 24), Fit(1, True, 0, 7, 40, 18)),  # the classic terminal: whole agar, side panel, no log
        ((40, 18), (60, 40), Fit(1, False, 9, 0, 40, 18)),  # too narrow for the side panel: strip mode
        ((96, 35), (80, 24), Fit(2, False, 0, 0, 48, 18)),
        ((72, 34), (80, 24), Fit(2, True, 3, 4, 36, 17)),  # the default dish on the classic terminal
        ((96, 35), (60, 20), Fit(3, False, 3, 0, 32, 12)),
        ((96, 35), (24, 10), None),  # even quarter resolution does not fit
    ],
)
def test_fit_worked_values(dish, term, expect):
    assert fit(*dish, *term) == expect


def test_fit_gives_the_census_the_rows_the_vitals_leave_or_folds_to_the_strip():
    """The vitals panel is VITALS_H rows when nothing wraps; in a narrow side column its rows wrap
    and it grows. The census gets what is left beside the agar; when not even one row is left the
    side panel folds into the strip at the same scale rather than run off the screen."""
    assert fit(40, 18, 80, 24, vitals_h=13) == Fit(1, True, 0, 7, 40, 18)
    assert fit(40, 18, 80, 24, vitals_h=19) == Fit(1, True, 0, 1, 40, 18)  # the panel as it wraps at 36 columns
    assert fit(40, 18, 80, 24, vitals_h=20) == Fit(1, False, 0, 0, 40, 18)  # one row more and the strip takes over
    assert fit(96, 35, 150, 50, vitals_h=15) == Fit(1, True, 9, 22, 96, 35)  # a mind error: the census gives up rows
    asked = []

    def measured(side_w: int) -> int:
        asked.append(side_w)
        return 13 if side_w >= 48 else 19

    assert fit(96, 35, 100, 30, vitals_h=measured) == Fit(2, True, 8, 5, 48, 18)
    assert asked == [48]  # measured once, at the side column of the scale that fits; scale 1 had no side column


def test_fit_badge_names_the_scale():
    assert fit(96, 35, 100, 30).badge == "½"
    assert fit(96, 35, 60, 20).badge == "⅓"
    assert fit(96, 35, 30, 14).badge == "¼"
    assert fit(96, 35, 150, 50).badge == ""


def test_fit_never_overflows_and_scale_is_minimal():
    n = 0
    for dw, dh in ((40, 18), (72, 34), (96, 44)):
        for vit in (VITALS_H, 19):
            for cols in range(10, 161, 10):
                for rows in range(5, 61, 5):
                    f = fit(dw, dh, cols, rows, vit)
                    if f is None:
                        continue
                    n += 1
                    avail = rows - CHROME_H
                    assert f.panel_w + (SIDE_MIN if f.side else 0) <= cols
                    assert f.log_h == 0 or LOG_MIN <= f.log_h <= LOG_H
                    assert f.view_w == -(-dw // f.scale) and f.view_h == -(-dh // f.scale)
                    if f.side:
                        assert f.census_rows >= 1 and f.panel_h + f.log_h <= avail
                        assert vit + 2 + f.census_rows + f.log_h == avail  # the side column fills the body
                    else:
                        assert f.census_rows == 0 and f.panel_h + 1 + f.log_h <= avail
                        assert cols - f.panel_w < SIDE_MIN or max(f.panel_h, vit + 3) > avail  # the side did not fit
                    if f.scale > 1:  # one step sharper would have fit neither with the side panel nor with the strip
                        k = f.scale - 1
                        pw, ph = -(-dw // k) + 4, -(-dh // k) + 2
                        assert not (pw <= cols and cols - pw >= SIDE_MIN and max(ph, vit + 3) <= avail)
                        assert not (pw <= cols and ph + 1 <= avail)
    assert n > 800  # the sweep actually exercised the fits


# --- the renderer ----------------------------------------------------------------


def test_render_dish_shapes(culture):
    c = culture(96, 35)
    for scale, (w, h) in {1: (96, 35), 2: (48, 18), 3: (32, 12)}.items():
        lines = render_dish(c, scale).plain.split("\n")
        assert lines[-1] == ""  # every row ends in a newline, like the full-resolution renderer
        assert len(lines) - 1 == h
        assert all(len(ln) == w for ln in lines[:-1])


def test_block_shows_the_dominant_strain():
    d, reg = Dish("t", 8, 4), Registry("t")
    a = reg.new(FALLBACK_GENESIS, None, 0, "a", "")
    b = reg.new(FALLBACK_GENESIS + "\n", None, 0, "b", "")
    for x, y in ((2, 0), (3, 0), (2, 1)):
        assert d.place(x, y, a.id, 1.2)
    assert d.place(3, 1, b.id, 1.2)
    assert d.place(4, 0, b.id, 1.2)
    out = render_dish(SimpleNamespace(dish=d, registry=reg), 2)
    row = out.plain.split("\n")[0]
    assert row[1] == "●" and style_at(out, 1) == reg.color(a.id, 1.2)  # three of a, one of b: a's colour
    assert row[2] == "▪" and style_at(out, 2) == reg.color(b.id, 1.2)  # a lone cell
    assert d.mask[0][1] and not d.mask[0][0]  # the first block is half inside the glass wall
    assert row[0] not in "●▪"  # and shows agar, not a cell glyph


def test_block_tie_goes_to_the_smaller_strain_id():
    d, reg = Dish("t", 8, 4), Registry("t")
    a = reg.new(FALLBACK_GENESIS, None, 0, "a", "")
    b = reg.new(FALLBACK_GENESIS + "\n", None, 0, "b", "")
    assert a.id != b.id
    for x, y in ((2, 0), (3, 0)):
        assert d.place(x, y, a.id, 1.0)
    for x, y in ((2, 1), (3, 1)):
        assert d.place(x, y, b.id, 1.0)
    out = render_dish(SimpleNamespace(dish=d, registry=reg), 2)
    assert out.plain[1] == "●"
    assert style_at(out, 1) == reg.color(min(a.id, b.id), 1.0)


def test_block_lightness_is_the_dominant_strain_mean_energy():
    d, reg = Dish("t", 8, 4), Registry("t")
    a = reg.new(FALLBACK_GENESIS, None, 0, "a", "")
    assert d.place(2, 0, a.id, 0.2) and d.place(3, 0, a.id, 1.0)
    out = render_dish(SimpleNamespace(dish=d, registry=reg), 2)
    assert style_at(out, 1) == reg.color(a.id, 0.6)
    assert reg.color(a.id, 0.6) != reg.color(a.id, 1.0)  # a hungry block really is dimmer


def test_vitals_strip_leads_with_population_and_ellipsises_the_tail(culture):
    c = culture(40, 18, ticks=60)
    snap = c.snapshot()
    with c.lock:
        t = vitals_strip(c, snap)
    plain = t.plain
    order = [" pop ", snap["phase"], " agar ", " ready ", " living ", " arisen ", " H ", " top "]
    assert [plain.index(k) for k in order] == sorted(plain.index(k) for k in order)
    assert plain.startswith(f" pop {snap['population']} ")
    assert plain.endswith(f" {snap['population']}")  # one strain: the founder is the top strain, with every cell
    assert (
        f" · {snap['mutagen']['state']} · " in plain
    )  # the mutagen's state as a word: its glyph would sit between two dots
    assert "· ·" not in plain
    assert len(plain) > 40
    lines = paint(t, 40, 3).split("\n")  # laid out in a region, as the strip row of a frame is
    assert len(lines[0]) == 40 and lines[0].endswith("…")  # cut with an ellipsis
    assert lines[1].strip() == "" and lines[2].strip() == ""  # never wrapped onto the rows below


# --- header and footer: one row each, whatever the width ----------------------------


def test_header_is_one_row_and_keeps_the_heartbeat_at_every_width(culture):
    """The header never wraps: the row under it is the agar's, so a second line would be cropped
    and the heartbeat with it. What gives way, in order: the seed (cut, then dropped), the uptime,
    the tick. At the terminal that poured the dish the row is what it always was."""
    c = culture(96, 35, ticks=60, seed="twenty-five characters ok")
    assert len(c.seed) == 25
    uptime = r"\d+h\d\dm\d\ds"
    for size in ((150, 50), (100, 30), (80, 24), (60, 20), (30, 14)):
        lines = rows_of(shot(c, *size))
        assert len(lines) == size[1]
        assert lines[0].rstrip()[-1] in "♥♡", f"no heartbeat at {size}"
    home = rows_of(shot(c, 150, 50))[0]
    assert re.fullmatch(rf" biotic   seed “twenty-five characters ok”   tick 60   {uptime}   ♥ *", home)
    narrow = rows_of(shot(c, 60, 20))[0]  # the seed gives way first, cut with an ellipsis, to exactly the width
    assert re.fullmatch(rf" biotic   seed “twenty-five chara…”   tick 60   {uptime}   ♥", narrow) and len(narrow) == 60
    tiny = rows_of(shot(c, 30, 14))[0]  # then the seed goes, then the uptime; the tick and the beat stay
    assert re.fullmatch(r" biotic   tick 60   ♥ *", tiny)
    snap = c.snapshot()
    assert re.fullmatch(rf" biotic   seed “twe…”   tick 60   {uptime}   ♥", header(c, snap, 46).plain)
    assert re.fullmatch(rf" biotic   tick 60   {uptime}   ♥", header(c, snap, 45).plain)  # fewer than 4 cells: no seed
    for cols in range(14, 160):  # 14 columns is the narrowest agar panel fit() ever draws
        t = header(c, snap, cols)
        assert t.no_wrap and t.overflow == "ellipsis"
        assert cell_len(t.plain) <= cols and t.plain.endswith("♥")


def test_footer_keeps_the_ctrl_c_hint_and_drops_commands_from_the_left():
    full = footer(150).plain
    assert full.startswith('  biotic whisper "…"') and full.endswith("ctrl-c to incubate (state is saved)")
    assert (
        footer(100).plain
        == "  biotic drop nutrient|antibiotic|mutagen   biotic strains   ctrl-c to incubate (state is saved)"
    )
    assert footer(60).plain == "  biotic strains   ctrl-c to incubate (state is saved)"
    assert footer(30).plain == "  ctrl-c to incubate (state is saved)"  # the last to go
    for cols in range(14, 160):
        t = footer(cols)
        assert t.no_wrap and t.overflow == "ellipsis"
        assert cell_len(t.plain) <= max(cols, 37)
    lines = paint(footer(30), 30, 2).split("\n")  # laid out in a region, as the footer row of a frame is
    assert lines[0] == "  ctrl-c to incubate (state i…" and lines[1].strip() == ""  # cut, never wrapped


# --- frames: acceptance criteria ---------------------------------------------------


def test_seeded_at_150x50_is_watchable_at_100x30_with_the_half_badge(culture, monkeypatch):
    monkeypatch.setattr(shutil, "get_terminal_size", lambda fallback=(0, 0): os.terminal_size((150, 50)))
    monkeypatch.delenv("BIOTIC_WIDTH", raising=False)
    monkeypatch.delenv("BIOTIC_HEIGHT", raising=False)
    w, h = _fit_dish()
    assert (w, h) == (96, 35)  # what `biotic seed` pours on a 150×50 terminal
    c = culture(w, h, ticks=60)

    small = shot(c, 100, 30)
    assert "½" in small
    assert "census" in small
    assert_unclipped(small, planned(c, (100, 30)), rows=30)

    home = shot(c, 150, 50)
    assert "½" not in home
    assert_unclipped(home, planned(c, (150, 50)), rows=50)
    lines = rows_of(home)
    log_top = next(i for i, ln in enumerate(lines) if "incubator log" in ln)
    assert lines[log_top + LOG_H - 1].startswith("╰")  # the nine-row log of the seeding terminal, unchanged


@pytest.mark.parametrize(
    "size", [(150, 50), (100, 30), (80, 24), (60, 20), (40, 12), (30, 14), (24, 10), (10, 4), (1, 1)]
)
def test_every_size_renders_and_is_unclipped(culture, size):
    c = culture(96, 35, ticks=60)
    fr = shot(c, *size)
    f = planned(c, size)
    if f is None:  # the frame rendered without raising; what it wrapped was the placeholder
        placeholder = build(c, size)
        assert isinstance(placeholder, Text) and "too small" in placeholder.plain
    else:
        assert_unclipped(fr, f, rows=size[1])
        assert (f.badge in fr) if f.badge else not any(b in fr for b in tui.BADGE.values())


@pytest.mark.parametrize("extra", [0, 5, 12])
@pytest.mark.parametrize(
    ("dish", "size"), [((96, 35), (100, 30)), ((96, 35), (150, 50)), ((40, 18), (80, 24)), ((72, 34), (80, 24))]
)
def test_census_closes_on_screen_and_counts_the_strains_it_cannot_list(culture, dish, size, extra):
    """The side panel is measured, not assumed: the census gets the rows the vitals leave beside the
    agar, lists as many strains as fit, and its last line says how many more there are. At the
    narrowest side panel (80×24 for the minimum dish) the vitals rows wrap and the census is that
    one line; the strain names here are as long as names get, and a row is still one row."""
    c = culture(*dish, ticks=60)
    living = strains(c, extra)
    assert living == extra + 1
    f = planned(c, size)
    assert f is not None and f.side
    fr = shot(c, *size)
    assert_unclipped(fr, f, rows=size[1], living=living)
    shown = living if living <= min(CENSUS_ROWS, f.census_rows) else min(CENSUS_ROWS, f.census_rows - 1)
    assert re.findall(r"… (\d+) more", fr) == ([str(living - shown)] if shown < living else [])
    # the founder is listed first; the long names are cut to the column rich leaves them, so match a prefix
    assert fr.count("strain_with") == max(0, shown - 1)


def test_census_rows_at_the_acceptance_sizes(culture):
    c = culture(96, 35, ticks=60)
    strains(c, 12)
    assert planned(c, (100, 30)).census_rows == 5  # 13 living: four strains and `… 9 more`
    assert planned(c, (150, 50)).census_rows == 24  # nine strains and `… 4 more`: the census is capped, not the rows
    assert re.search(r"… 9 more", shot(c, 100, 30)) and re.search(r"… 4 more", shot(c, 150, 50))
    c = culture(40, 18, ticks=60)
    strains(c, 3)
    f = planned(c, (80, 24))
    assert f == Fit(1, True, 0, 1, 40, 18)  # the wrapped vitals leave one row, which is the count
    assert re.search(r"… 4 more", shot(c, 80, 24))


def test_side_panel_folds_into_the_strip_when_the_vitals_do_not_fit_above_the_footer(culture):
    """At the narrowest side panel the wrapped vitals nearly fill the body. A mind error adds rows,
    and rather than push the census off the screen the side panel gives way to the strip, at the
    same scale; the agar keeps its resolution."""
    c = culture(40, 18, ticks=60)
    assert planned(c, (80, 24)) == Fit(1, True, 0, 1, 40, 18)
    c.mind.last_error = "the model returned nothing usable after three attempts"
    f = planned(c, (80, 24))
    assert f == Fit(1, False, 0, 0, 40, 18)
    fr = shot(c, 80, 24)
    assert " pop " in fr and "census" not in fr
    assert_unclipped(fr, f, rows=24)


def test_narrow_terminal_folds_vitals_into_a_strip(culture):
    c = culture(40, 18, ticks=60)
    strip = shot(c, 60, 40)
    assert " pop " in strip and "census" not in strip
    assert_unclipped(strip, planned(c, (60, 40)), rows=40)
    row = next(ln for ln in rows_of(strip) if ln.startswith(" pop "))
    assert len(row) == 60 and row.endswith("…")  # the strip is one row: cut, not wrapped into the log
    assert "census" in shot(c, 120, 40)
    classic = shot(c, 80, 24)  # the log goes before the agar or the side panel
    assert "census" in classic and "incubator log" not in classic and "½" not in classic
    assert_unclipped(classic, planned(c, (80, 24)), rows=24)


def test_tiny_terminal_gets_a_placeholder(culture):
    c = culture(40, 18)
    out = build(c, (12, 5))
    assert isinstance(out, Text) and "too small" in out.plain
    assert "40×18" in out.plain
    painted = paint(out, 12, 5)
    assert " ".join(painted.split()) == " ".join(out.plain.split())  # wraps to fit; every word survives


def test_frame_is_a_function_of_state_and_size(culture):
    a = culture(40, 18, ticks=30, seed="fixed")
    b = culture(40, 18, ticks=30, seed="fixed")
    assert a.dish.deaths.get("lysed", 0) == 0 and a.dish.cells
    for size in ((100, 30), (60, 20)):
        fa, fb = render_dish(a, fit(40, 18, *size).scale), render_dish(b, fit(40, 18, *size).scale)
        assert fa.plain == fb.plain and fa.spans == fb.spans


# --- the render thread: a resize settles within one frame, a failure is logged, not frozen ---


def test_frame_reads_the_terminal_size_on_every_call(culture):
    c = culture(96, 35, ticks=60)
    con = window(150, 50)
    home = frame(c, con)
    assert isinstance(home, Layout) and "½" not in paint(home, 150, 50)
    con.size = (100, 30)  # the resize; nothing else changes
    small = frame(c, con)
    assert "½" in paint(small, 100, 30)
    assert_unclipped(paint(small, 100, 30), planned(c, (100, 30)), rows=30)
    con.size = (24, 10)
    assert "too small" in frame(c, con).plain


def test_console_size_follows_the_tty_when_no_size_is_given(culture, monkeypatch):
    """`biotic live` builds Console() with no width or height, so rich asks the tty for the size on
    every access (os.get_terminal_size, then COLUMNS and LINES if exported). A rich release that
    cached it, or a Console(width=...) in observe(), would stop the eyepiece following the window:
    the frame after a resize would still be built for the old size."""
    size = {"now": (150, 50)}
    monkeypatch.setattr(os, "get_terminal_size", lambda fd=None: os.terminal_size(size["now"]))
    monkeypatch.delenv("COLUMNS", raising=False)
    monkeypatch.delenv("LINES", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")  # a dumb TERM would make rich answer 80×25 regardless
    con = Console(file=io.StringIO(), force_terminal=True)
    assert tuple(con.size) == (150, 50)
    c = culture(96, 35, ticks=60)
    assert "½" not in paint(frame(c, con), 150, 50)
    size["now"] = (100, 30)  # the resize; nothing else changes
    assert tuple(con.size) == (100, 30)
    small = paint(frame(c, con), 100, 30)
    assert "½" in small
    assert_unclipped(small, planned(c, (100, 30)), rows=30)


def test_redraw_settles_every_resize_by_the_next_frame(culture):
    """Acceptance criterion 2, without a tty: each frame after a resize is already the new layout."""
    c = culture(96, 35, ticks=60)
    con = window(150, 50)
    lens = watch(c, con, [(100, 30), (80, 24), (60, 20), (24, 10), (150, 50)])
    assert [size for _, size in lens.frames] == [(150, 50), (100, 30), (80, 24), (60, 20), (24, 10), (150, 50)]
    for renderable, size in lens.frames:
        f = planned(c, size)
        if f is None:
            assert isinstance(renderable, Text) and "too small" in renderable.plain
        else:
            fr = paint(renderable, *size)
            assert_unclipped(fr, f, rows=size[1])
            assert (f.badge in fr) if f.badge else not any(b in fr for b in tui.BADGE.values())
    (side, side_size), (strip, strip_size) = lens.frames[1], lens.frames[2]
    assert "census" in paint(side, *side_size) and " pop " in paint(strip, *strip_size)


def test_log_panel_survives_appends_from_other_threads(culture):
    """The dish and the mutagen append to the event deque from their own threads while the render
    thread reads it. Iterating the deque itself raised "deque mutated during iteration" whenever a
    switch landed mid-frame; events() copies it in one step, which the interpreter does not interrupt."""
    c = culture(24, 12)
    stop, appended = threading.Event(), [0]

    def chatter():
        while not stop.is_set():
            c.events.append({"t": 0.0, "tick": appended[0], "kind": "mind", "msg": f"note {appended[0]}"})
            appended[0] += 1

    was = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)  # switch threads as often as the interpreter will
    t = threading.Thread(target=chatter, daemon=True)
    t.start()
    try:
        for _ in range(1500):
            events(c, 7)
    finally:
        stop.set()
        t.join()
        sys.setswitchinterval(was)
    assert appended[0] > 1500  # the other thread really was appending throughout
    assert events(c, 7).plain.count("\n") == 7


def test_a_failed_frame_is_logged_once_and_the_loop_lives_on(culture, monkeypatch):
    c = culture(40, 18)
    con = window(100, 30)
    real, calls = tui.build, []

    def flaky(cult, size):
        calls.append(size)
        if len(calls) <= 2:
            raise RuntimeError("bad glyph")
        return real(cult, size)

    monkeypatch.setattr(tui, "build", flaky)
    lens = watch(c, con)
    assert len(calls) == 3 and len(lens.frames) == 1  # two failures, then the frame that stopped the loop
    assert not c.lock.locked()  # a failure inside build() released the culture's lock
    logged = [ev for ev in c.events if ev["kind"] == "eyepiece"]
    assert len(logged) == 1
    assert "RuntimeError: bad glyph" in logged[0]["msg"] and "flaky" in logged[0]["msg"]
    assert "bad glyph" in config.EVENTS.read_text()  # what `biotic log` reads


def test_a_frame_that_always_fails_is_logged_once_and_the_harness_does_not_hang(culture, monkeypatch):
    """redraw() swallows every failure by design, so a build() that raises on every call spins the
    loop until stop is set. The bounded stop event ends it; the log still says why, once."""
    c = culture(40, 18)
    con, stop = window(100, 30), Bounded(budget=50)

    def broken(cult, size):
        raise RuntimeError("no glyphs")

    monkeypatch.setattr(tui, "build", broken)
    lens = Lens(con, stop)
    redraw(c, con, lens, stop, period=0.001)
    assert stop.is_set() and stop.waits == stop.budget + 1 and lens.frames == []
    assert not c.lock.locked()
    logged = [ev for ev in c.events if ev["kind"] == "eyepiece"]
    assert len(logged) == 1 and "RuntimeError: no glyphs" in logged[0]["msg"]


def test_observe_is_the_only_painter(culture, monkeypatch):
    """rich's own refresh thread would repaint the previous frame at its own cadence after a resize,
    so Live must run without it, in the alternate screen, on the console it is given."""
    c = culture(40, 18)
    con = window(100, 30)
    made: dict = {}

    class FakeLive:
        def __init__(self, first, **kw):
            made.update(kw, first=first)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def update(self, renderable, refresh=False):
            pass

    monkeypatch.setattr(tui, "Live", FakeLive)
    monkeypatch.setattr(c, "run", lambda stop, tick_seconds: None)
    tui.observe(c, console=con)
    assert made["auto_refresh"] is False and made["screen"] is True and made["console"] is con
    assert isinstance(made["first"], Layout) and "census" in paint(made["first"], 100, 30)
    assert "incubating" in con.export_text()
