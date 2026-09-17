"""The eyepiece: a live view of the dish in the terminal."""

from __future__ import annotations

import io
import os
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass

from rich.cells import cell_len
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import config
from .culture import HIDDEN, Culture  # HIDDEN: bookkeeping kinds, kept out of the incubator log
from .mind import fmt_budget
from .naturalist import first_sentence

SPARK = "▁▂▃▄▅▆▇█"
ICONS = {
    "genesis": ("◉", "bold green"),
    "arose": ("✚", "bold cyan"),
    "prepared": ("◌", "dim cyan"),
    "nonviable": ("✖", "dim red"),
    "extinct": ("†", "yellow"),
    "drop": ("⚗", "magenta"),
    "whisper": ("✎", "magenta"),
    "phase": ("◐", "bold white"),
    "mind": ("…", "dim"),
    "curve": ("≡", "dim"),
    "frozen": ("▫", "dim cyan"),
    "freezer": ("▫", "dim red"),
    "revived": ("↺", "bold cyan"),
    "eyepiece": ("!", "yellow"),
    "note": ("¶", "magenta"),
    "gap": ("⋯", "dim"),  # a resume after a wall-clock absence; matches plot.MARKERS["gap"]
}
AGAR = [
    (0.02, " ", "grey23"),
    (0.12, "·", "grey27"),
    (0.28, "·", "dark_green"),
    (0.5, ":", "green4"),
    (0.75, "∷", "green4"),
    (1.01, "∷", "dark_sea_green4"),
]
PHASE_STYLE = {
    "log": "bold green",
    "death": "bold red",
    "stationary": "yellow",
    "sterile": "dim",
    "lag": "cyan",
}
MUTAGEN_STYLE = {
    "thinking": ("◐ thinking", "bold magenta"),
    "idle": ("○ idle", "dim"),
    "dormant": ("· dormant", "dim red"),
    "error": ("! error", "red"),
    "exhausted": ("· exhausted", "yellow"),
}

# How the eyepiece fits a dish onto a terminal.
SIDE_MIN = 36  # narrowest side panel worth drawing; a 40-wide dish keeps it down to 80 columns
VITALS_H = 13  # the vitals panel with a dormant mind and no row wrapped: 11 rows and the border; build() measures it
CENSUS_ROWS = 9  # strains the census lists at most; the rest are one `… n more` line
LOG_H = 9  # incubator log height when there is room
LOG_MIN = 3  # one log line plus border; fewer rows and the log is dropped
CHROME_H = 2  # header + footer rows
MAX_SCALE = 4
BADGE = {2: "½", 3: "⅓", 4: "¼"}
FRAME_SECONDS = 1 / 6


@dataclass(frozen=True)
class Fit:
    """How the eyepiece maps a dish onto a terminal: k×k tiles per glyph, whether the
    side panel is drawn, how tall the log is and how many rows the census may list."""

    scale: int  # 1 = one tile per glyph; k = k×k tiles per glyph; up to MAX_SCALE
    side: bool  # vitals + census beside the dish; False → a one-line vitals strip above the log
    log_h: int  # 0 (dropped) or LOG_MIN..LOG_H
    census_rows: int  # rows inside the census panel's border: at least 1 beside the dish, 0 in strip mode
    view_w: int  # glyph columns of the rendered dish = ceil(w / scale)
    view_h: int  # glyph rows = ceil(h / scale)

    @property
    def panel_w(self) -> int:
        return self.view_w + 4  # border 2 + padding 2

    @property
    def panel_h(self) -> int:
        return self.view_h + 2

    @property
    def badge(self) -> str:
        return BADGE.get(self.scale, "")


def fit(dish_w: int, dish_h: int, cols: int, rows: int, vitals_h: int | Callable[[int], int] = VITALS_H) -> Fit | None:
    """Smallest integer scale at which the agar panel fits between header and footer.
    The side panel is kept when SIDE_MIN columns remain beside the agar and the vitals
    panel fits above the footer with a census of at least one row under it; otherwise
    one row is reserved for the vitals strip, at the same scale. The log takes the rows
    left under the taller of the agar and the side panel, at most LOG_H; fewer than
    LOG_MIN and it is dropped. The census then has the rows beside the agar that the
    vitals leave. `vitals_h` is the vitals panel's height, border included: a number, or
    a function of the side column's width, because its rows wrap in a narrow one. None
    when even MAX_SCALE does not fit."""
    avail = rows - CHROME_H
    for k in range(1, MAX_SCALE + 1):
        vw, vh = -(-dish_w // k), -(-dish_h // k)
        pw, ph = vw + 4, vh + 2
        if pw > cols or ph > avail:
            continue
        side_w = cols - pw
        if side_w >= SIDE_MIN:
            vit = vitals_h(side_w) if callable(vitals_h) else vitals_h
            need = max(ph, vit + 3)  # the agar, or the vitals with the census border and one census row
            if need <= avail:
                spare = avail - need
                log_h = min(LOG_H, spare) if spare >= LOG_MIN else 0
                return Fit(k, True, log_h, avail - log_h - vit - 2, vw, vh)
        if ph + 1 <= avail:  # the strip row
            spare = avail - 1 - ph
            return Fit(k, False, min(LOG_H, spare) if spare >= LOG_MIN else 0, 0, vw, vh)
    return None


_RULER = Console(file=io.StringIO(), force_terminal=False, color_system=None, width=80, height=1000)


def height(renderable, width: int) -> int:
    """Rows `renderable` takes at `width`, found by rendering it off screen. The vitals
    rows wrap in a narrow side column, so the panel's height is measured, not assumed."""
    return len(_RULER.render_lines(renderable, _RULER.options.update_width(width)))


def _agar_glyph(nutrient: float, pheromone: float) -> tuple[str, str]:
    for lim, ch, st in AGAR:
        if nutrient < lim:
            break
    if pheromone > 0.12:
        st = "medium_purple4" if pheromone < 0.4 else "medium_purple"
    return ch, st


def render_dish(c: Culture, scale: int = 1) -> Text:
    """The agar as text: one glyph per tile, or per scale×scale block of tiles."""
    return _render_tiles(c) if scale <= 1 else _render_blocks(c, scale)


def _render_tiles(c: Culture) -> Text:
    d, reg = c.dish, c.registry
    out = Text(no_wrap=True)
    cells, nut, ph, mask = d.cells, d.nutrient, d.pheromone, d.mask
    for y in range(d.h):
        row = Text(no_wrap=True)
        for x in range(d.w):
            if not mask[y][x]:
                row.append(" ")
                continue
            cell = cells.get((x, y))
            if cell is not None:
                row.append("●", style=reg.color(cell.strain, cell.energy))
                continue
            ch, st = _agar_glyph(nut[y][x], ph[y][x])
            row.append(ch, style=st)
        out.append_text(row)
        out.append("\n")
    return out


def _render_blocks(c: Culture, k: int) -> Text:
    """k×k tiles per glyph. A block with cells shows its dominant strain (most cells;
    ties go to the smaller strain id, so the frame is a function of the state): `▪` for
    a lone cell, `●` for two or more, lit by that strain's mean energy in the block.
    A block with no cells shows its mean nutrient, violet when its mean pheromone is
    above the threshold. Only masked tiles count; a block with none is blank."""
    d, reg = c.dish, c.registry
    out = Text(no_wrap=True)
    cells, nut, ph, mask = d.cells, d.nutrient, d.pheromone, d.mask
    for by in range(0, d.h, k):
        row = Text(no_wrap=True)
        ys = range(by, min(by + k, d.h))
        for bx in range(0, d.w, k):
            tiles = [(x, y) for y in ys for x in range(bx, min(bx + k, d.w)) if mask[y][x]]
            if not tiles:
                row.append(" ")
                continue
            counts: dict[str, int] = {}
            energy: dict[str, float] = {}
            for xy in tiles:
                cell = cells.get(xy)
                if cell is not None:
                    counts[cell.strain] = counts.get(cell.strain, 0) + 1
                    energy[cell.strain] = energy.get(cell.strain, 0.0) + cell.energy
            if counts:
                top = min(counts, key=lambda s: (-counts[s], s))
                glyph = "▪" if sum(counts.values()) == 1 else "●"
                row.append(glyph, style=reg.color(top, energy[top] / counts[top]))
                continue
            n = len(tiles)
            ch, st = _agar_glyph(sum(nut[y][x] for x, y in tiles) / n, sum(ph[y][x] for x, y in tiles) / n)
            row.append(ch, style=st)
        out.append_text(row)
        out.append("\n")
    return out


def sparkline(hist: list[int], width: int) -> Text:
    if not hist:
        return Text("")
    step = max(1, len(hist) // width)
    pts = hist[::-1][::step][::-1][-width:]
    hi = max(pts) or 1
    t = Text()
    for p in pts:
        t.append(SPARK[min(7, int(p / hi * 7.999))], style="cyan" if p else "dim")
    return t


def vitals(c: Culture, snap: dict) -> Table:
    t = Table.grid(padding=(0, 1))
    t.add_column(style="dim", justify="right")
    t.add_column()
    pop = snap["population"] or 0
    t.add_row("population", Text(f"{pop}", style="bold") + Text(f"  {pop / snap['tiles']:.0%} of agar", style="dim"))
    t.add_row("", sparkline(snap["history"], 26))
    t.add_row("phase", Text(snap["phase"], style=PHASE_STYLE.get(snap["phase"], "")))
    living = len(snap["census"])
    mt = snap["metrics"]
    t.add_row(
        "strains",
        Text(f"{living}", style="bold") + Text(f"  {mt['arisen']} arisen  {mt['extinct']} extinct", style="dim"),
    )
    t.add_row(
        "diversity",
        Text(f"H {mt['shannon']:.2f}", style="bold")
        + Text(f"  dominance {mt['dominance']:.0%}  gen {mt['mean_gen']:.1f}", style="dim"),
    )
    nb = int(snap["nutrient"] * 20)
    t.add_row("agar", Text("█" * nb + "░" * (20 - nb), style="green4") + Text(f" {snap['nutrient']:.2f}", style="dim"))
    dd = snap["deaths"]
    t.add_row("births", f"{snap['births']}")
    t.add_row(
        "deaths",
        f"{dd.get('starved', 0)} starved · {dd.get('lysed', 0)} lysed · {dd.get('senescent', 0)} old"
        + (f" · {dd['killed']} killed" if dd.get("killed") else "")
        + (f" · {dd['predated']} predated" if dd.get("predated") else ""),
    )
    if snap.get("given"):  # only once a gift has been made; sharing is off on most dishes (docs/sharing.md)
        t.add_row("sharing", f"{snap['given']:.2f} given · {snap['received']:.2f} received")
    m, mind = snap["mutagen"], snap["mind"]
    state = MUTAGEN_STYLE.get(m["state"], (m["state"], ""))
    mut = Text(state[0], style=state[1])
    ticked = m.get("clock") == "tick"
    if ticked:  # no pool on the tick clock: the interval is the thing to know
        mut.append(f"  every {m['every_ticks']} ticks", style="dim")
    else:
        mut.append(f"  {m['ready']} ready · {m['pending']} queued", style="dim")
    if m["state"] == "error" and m.get("retry_in", 0) > 0:
        mut.append(f"  retry in {int(m['retry_in'])}{' ticks' if ticked else 's'}", style="dim")
    if m["boosted"]:
        mut.append("  ×6", style="bold magenta")
    t.add_row("mutagen", mut)
    # the clock in the label column, where it costs no width: the value column is as narrow as 23 cells
    t.add_row(m.get("clock") or "", Text(f"{m['viable']} viable · {m['nonviable']} nonviable", style="dim"))
    mind_line = Text(mind["model"].split("/")[-1], style="dim")
    if mind["calls"]:
        mind_line.append(
            f" · {mind['calls']} calls · {mind['tokens'] / 1000:.1f}k tok · {mind['latency']:.0f}s", style="dim"
        )
    t.add_row("mind", mind_line)
    if mind["awake"] or mind["calls"]:
        t.add_row("spent", Text(fmt_budget(mind["spent_usd"], mind["budget_usd"]), style="dim"))
    if mind["error"]:
        t.add_row("", Text(mind["error"][:60], style="red"))
    return t


def vitals_strip(c: Culture, snap: dict) -> Text:
    """One line of vitals, for when there is no room for the side panel. The most
    important come first, because a narrow terminal cuts the tail. The mind's error,
    if any, is in the log; the census is in `biotic strains`."""
    pop = snap["population"] or 0
    mt, m = snap["metrics"], snap["mutagen"]
    state, style = MUTAGEN_STYLE.get(m["state"], (m["state"], ""))
    t = Text(no_wrap=True, overflow="ellipsis")
    t.append(" pop ", style="dim")
    t.append(f"{pop}", style="bold")
    t.append(f" · {pop / snap['tiles']:.0%} · ", style="dim")
    t.append(snap["phase"], style=PHASE_STYLE.get(snap["phase"], ""))
    t.append(f" · agar {snap['nutrient']:.2f} · ", style="dim")
    t.append(state.split(" ", 1)[-1], style=style)  # the word without its glyph: "· · dormant" reads badly
    if m["boosted"]:
        t.append(" ×6", style="bold magenta")
    supply = "tick" if m.get("clock") == "tick" else f"{m['ready']} ready"  # no pool on the tick clock
    t.append(
        f" · {supply} · {len(snap['census'])} living · {mt['arisen']} arisen · H {mt['shannon']:.2f}",
        style="dim",
    )
    rows = c.registry.living(snap["census"])
    if rows:
        s, n = rows[0]
        t.append(" · top ", style="dim")
        t.append(s.name, style=c.registry.color(s.id))
        t.append(f" {n}", style="dim")
    return t


def census_table(c: Culture, snap: dict, avail: int = CENSUS_ROWS + 1) -> Table:
    """Living strains by population, largest first, in at most `avail` rows: CENSUS_ROWS
    strains, then one `… n more` line. When fewer rows fit, the last of them is that
    line, so a strain is never cut off the bottom without a count of what is missing.
    Every cell is a single word or kept on one line, so a row is never taller than one."""
    t = Table.grid(padding=(0, 1))
    t.add_column()
    t.add_column(style="dim")
    t.add_column()
    t.add_column(justify="right")
    t.add_column()
    rows = c.registry.living(snap["census"])
    top = rows[0][1] if rows else 1
    shown = len(rows) if len(rows) <= min(CENSUS_ROWS, avail) else max(0, min(CENSUS_ROWS, avail - 1))
    for s, n in rows[:shown]:
        bar = "▇" * max(1, int(n / top * 12))
        t.add_row(
            Text("●", style=c.registry.color(s.id)),
            s.id,
            Text(s.name, style="bold"),
            str(n),
            Text(bar, style=c.registry.color(s.id)),
        )
    if shown < len(rows):
        t.add_row("", "", Text(f"… {len(rows) - shown} more", style="dim", no_wrap=True), "", "")
    return t


def events(c: Culture, n: int) -> Text:
    t = Text(no_wrap=True, overflow="ellipsis")
    # list() copies the deque in one step. The dish and the mutagen append to it from their own
    # threads, and a Python-level iteration one of them interrupts raises "deque mutated during iteration".
    shown = [ev for ev in list(c.events) if ev["kind"] not in HIDDEN]
    for ev in shown[-n:]:
        icon, style = ICONS.get(ev["kind"], ("·", "dim"))
        t.append(time.strftime("%H:%M:%S ", time.localtime(ev["t"])), style="dim")
        t.append(f"{ev['tick']:>6} ", style="dim")
        t.append(f"{icon} ", style=style)
        t.append(
            ev["msg"] + "\n",
            style="" if ev["kind"] in ("arose", "extinct", "drop", "phase", "genesis", "revived", "note") else "dim",
        )
    return t


def header(c: Culture, snap: dict, cols: int) -> Text:
    """One row: the seed, the tick, the uptime of this sitting and the heartbeat. It never
    wraps, because the row under it is the agar's and a second line would be cropped with
    the heartbeat on it. When `cols` cannot hold everything, the seed is cut with an
    ellipsis, then dropped, then the uptime, then the tick. The heartbeat stays: it is
    what tells a stopped dish from a frozen eyepiece."""
    up = int(snap["uptime"])
    beat = "♥" if (snap["tick"] // 2) % 2 == 0 else "♡"
    tick = f"tick {snap['tick']}"
    uptime = f"{up // 3600:d}h{(up % 3600) // 60:02d}m{up % 60:02d}s"
    # after ` biotic ` every element costs its width and a three-cell gap; the first gap is two cells
    room = cols - cell_len(" biotic ") + 1 - (3 + cell_len(beat))
    keep = []
    for field in (tick, uptime):  # in order of importance; the seed comes last and takes what is left
        if 3 + cell_len(field) <= room:
            keep.append(field)
            room -= 3 + cell_len(field)
    seed = Text(snap["seed"])
    seed_room = room - 3 - cell_len("seed “”")
    if seed_room >= 4:
        seed.truncate(seed_room, overflow="ellipsis")
    t = Text(no_wrap=True, overflow="ellipsis")
    t.append(" biotic ", style="bold reverse")
    gap = "  "
    if seed_room >= 4:
        t.append(gap + "seed ", style="dim")
        t.append(f"“{seed.plain}”", style="bold italic")
        gap = "   "
    for field in keep:
        t.append(gap + field, style="dim")
        gap = "   "
    t.append(gap)
    t.append(beat, style="red" if snap["population"] else "dim")
    return t


FOOTER = (
    'biotic whisper "…"',
    "biotic drop nutrient|antibiotic|mutagen",
    "biotic strains",
    "ctrl-c to incubate (state is saved)",
)


def footer(cols: int, note: dict | None = None) -> Text:
    """The interventions you can make from another shell, then how to leave. One row,
    never wrapped: when `cols` cannot hold every command they are dropped from the left,
    and the ctrl-c hint is the last to go, cut with an ellipsis.

    Once the naturalist has written a note, its latest entry's first sentence takes the
    commands' place (`¶ tick  sentence`; the commands are in the README and `biotic --help`).
    Here the hint yields first and the note is cut with an ellipsis: the note is the point."""
    if note is None:
        parts = list(FOOTER)
        while len(parts) > 1 and cell_len("  " + "   ".join(parts)) > cols:
            parts.pop(0)
        t = Text(no_wrap=True, overflow="ellipsis", style="dim")
        t.append("  " + "   ".join(parts))
        return t
    t = Text(no_wrap=True, overflow="ellipsis")
    t.append("  ¶ ", style="magenta")
    t.append(f"{note['tick']}  ", style="dim")
    t.append(first_sentence(note["text"], 200))
    hint = FOOTER[-1]
    if cell_len(t.plain) + 3 + cell_len(hint) <= cols:
        t.append("   " + hint, style="dim")
    else:
        t.truncate(cols, overflow="ellipsis")
    return t


def vitals_panel(c: Culture, snap: dict) -> Panel:
    return Panel(vitals(c, snap), title="[dim]vitals[/]", border_style="grey35")


def plan(c: Culture, snap: dict, size: tuple[int, int]) -> Fit | None:
    """fit() for this culture on a terminal of `size`: the vitals panel is measured at each
    side-column width fit() considers, as it will be drawn, so the census under it is
    given the rows that are really left and never runs off the screen."""
    vit = vitals_panel(c, snap)
    return fit(c.dish.w, c.dish.h, *size, lambda side_w: height(vit, side_w))


def build(c: Culture, size: tuple[int, int]) -> Layout | Text:
    """One frame, as a function of the culture's state and the terminal size.

    When the terminal is too small, in order of priority: the agar at the highest
    resolution that fits, then the side panel, then the log with whatever rows remain,
    then the census with the rows beside the agar that the vitals leave, and below all
    of that a one-line notice. The agar is the observation; the vitals, the census and
    the log are also in `biotic status`, `biotic strains` and `biotic log`."""
    cols, rows = size
    snap = c.snapshot()
    f = plan(c, snap, size)
    if f is None:
        return Text(f" biotic · {cols}×{rows} is too small an eyepiece for a {c.dish.w}×{c.dish.h} dish", style="dim")
    root = Layout()
    parts = [Layout(name="head", size=1), Layout(name="body")]
    if not f.side:
        parts.append(Layout(name="strip", size=1))
    if f.log_h:
        parts.append(Layout(name="log", size=f.log_h))
    parts.append(Layout(name="foot", size=1))
    root.split_column(*parts)
    root["head"].update(header(c, snap, cols))
    title = Text.assemble(("agar", "dim"))  # a span, not a base style, so the frame at scale 1 is byte-identical
    if f.scale > 1:
        title.append("  " + f.badge, style="bold yellow")
    # expand=False: in strip mode the panel sits alone in the body and must not stretch to the terminal width
    agar = Panel(render_dish(c, f.scale), title=title, border_style="grey35", padding=(0, 1), expand=False)
    if f.side:
        root["body"].split_row(Layout(name="dish", size=f.panel_w), Layout(name="side"))
        root["dish"].update(agar)
        census = Panel(census_table(c, snap, f.census_rows), title="[dim]census[/]", border_style="grey35")
        root["side"].update(Group(vitals_panel(c, snap), census))
    else:
        root["body"].update(agar)
        root["strip"].update(vitals_strip(c, snap))
    if f.log_h:
        root["log"].update(Panel(events(c, f.log_h - 2), title="[dim]incubator log[/]", border_style="grey35"))
    root["foot"].update(footer(cols, snap.get("note")))
    return root


def frame(c: Culture, console: Console) -> Layout | Text:
    """One frame for the terminal as it is right now. `console.size` asks the tty on
    every access, so it is read afresh for every frame, and before the lock: that is
    what makes a resize settle by the next frame without a signal handler."""
    size = console.size
    with c.lock:
        return build(c, size)


def redraw(c: Culture, console: Console, live: Live, stop: threading.Event, period: float = FRAME_SECONDS) -> None:
    """The render thread: one frame per period until `stop` is set. A frame that raises
    is dropped and the dish runs on; the first failure is written to the incubator log,
    so `biotic log` can say why the eyepiece froze."""
    said = False
    while not stop.wait(period):
        try:
            fr = frame(c, console)
            if not stop.is_set():
                live.update(fr, refresh=True)
        except Exception as e:  # noqa: BLE001 — a bad frame must never stop the dish
            if not said:
                said = True
                _report(c, e)


def _report(c: Culture, e: BaseException) -> None:
    try:
        where = traceback.extract_tb(e.__traceback__)[-1]
        c.log(
            "eyepiece",
            f"frame failed: {type(e).__name__}: {e} in {where.name} "
            f"({os.path.basename(where.filename)}:{where.lineno}); the dish runs on",
        )
    except Exception:  # noqa: BLE001 — the log is best effort from this thread
        pass


def observe(c: Culture, tick_seconds: float = config.TICK_SECONDS, console: Console | None = None) -> None:
    """The culture runs on the main thread (its time budgets are signal-based); the
    eyepiece redraws from a background thread, six times a second.

    Every frame is built for the terminal size read at that moment (`frame`), and in
    alternate-screen mode `Live` repaints the whole screen from the home position, so
    a resize is on screen by the next frame. No SIGWINCH handler is installed: one
    could only live on the main thread, which runs the dish and already owns SIGALRM
    for the membrane's time budget. rich's own refresh thread is off (`auto_refresh`):
    it would repaint the previous frame, reflowed to the new size, until ours arrived."""
    if console is None:
        console = Console()
    stop = threading.Event()
    with Live(build(c, console.size), console=console, screen=True, auto_refresh=False, transient=False) as live:
        threading.Thread(target=redraw, args=(c, console, live, stop), daemon=True).start()
        try:
            c.run(stop=stop, tick_seconds=tick_seconds)
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()
    console.print(
        f"[dim]incubating. tick {c.dish.tick}, {len(c.dish.cells)} cells, "
        f"{len(c.dish.census())} strains living. `biotic live` to resume.[/]"
    )
