"""The eyepiece: a live view of the dish in the terminal."""

from __future__ import annotations

import threading
import time

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import config
from .culture import Culture

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
}
AGAR = [
    (0.02, " ", "grey23"),
    (0.12, "·", "grey27"),
    (0.28, "·", "dark_green"),
    (0.5, ":", "green4"),
    (0.75, "∷", "green4"),
    (1.01, "∷", "dark_sea_green4"),
]


def render_dish(c: Culture) -> Text:
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
            n = nut[y][x]
            for lim, ch, st in AGAR:
                if n < lim:
                    break
            if ph[y][x] > 0.12:
                st = "medium_purple4" if ph[y][x] < 0.4 else "medium_purple"
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
    t.add_row(
        "phase",
        Text(
            snap["phase"],
            style={
                "log": "bold green",
                "death": "bold red",
                "stationary": "yellow",
                "sterile": "dim",
                "lag": "cyan",
            }.get(snap["phase"], ""),
        ),
    )
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
        + (f" · {dd['killed']} killed" if dd.get("killed") else ""),
    )
    m, mind = snap["mutagen"], snap["mind"]
    state = {
        "thinking": ("◐ thinking", "bold magenta"),
        "idle": ("○ idle", "dim"),
        "dormant": ("· dormant", "dim red"),
        "error": ("! error", "red"),
    }.get(m["state"], (m["state"], ""))
    mut = Text(state[0], style=state[1])
    mut.append(f"  {m['ready']} ready · {m['pending']} queued", style="dim")
    if m["boosted"]:
        mut.append("  ×6", style="bold magenta")
    t.add_row("mutagen", mut)
    t.add_row("", Text(f"{m['produced']} viable · {m['nonviable']} nonviable", style="dim"))
    mind_line = Text(mind["model"].split("/")[-1], style="dim")
    if mind["calls"]:
        mind_line.append(
            f" · {mind['calls']} calls · {mind['tokens'] / 1000:.1f}k tok · {mind['latency']:.0f}s", style="dim"
        )
    t.add_row("mind", mind_line)
    if mind["error"]:
        t.add_row("", Text(mind["error"][:60], style="red"))
    return t


def census_table(c: Culture, snap: dict) -> Table:
    t = Table.grid(padding=(0, 1))
    t.add_column()
    t.add_column(style="dim")
    t.add_column()
    t.add_column(justify="right")
    t.add_column()
    rows = c.registry.living(snap["census"])
    top = rows[0][1] if rows else 1
    for s, n in rows[:9]:
        bar = "▇" * max(1, int(n / top * 12))
        t.add_row(
            Text("●", style=c.registry.color(s.id)),
            s.id,
            Text(s.name, style="bold"),
            str(n),
            Text(bar, style=c.registry.color(s.id)),
        )
    if len(rows) > 9:
        t.add_row("", "", Text(f"… {len(rows) - 9} more", style="dim"), "", "")
    return t


def events(c: Culture, n: int) -> Text:
    t = Text(no_wrap=True, overflow="ellipsis")
    shown = [ev for ev in c.events if ev["kind"] != "prepared"]
    for ev in shown[-n:]:
        icon, style = ICONS.get(ev["kind"], ("·", "dim"))
        t.append(time.strftime("%H:%M:%S ", time.localtime(ev["t"])), style="dim")
        t.append(f"{ev['tick']:>6} ", style="dim")
        t.append(f"{icon} ", style=style)
        t.append(
            ev["msg"] + "\n", style="" if ev["kind"] in ("arose", "extinct", "drop", "phase", "genesis") else "dim"
        )
    return t


def header(c: Culture, snap: dict) -> Text:
    up = int(snap["uptime"])
    t = Text()
    t.append(" biotic ", style="bold reverse")
    t.append("  seed ", style="dim")
    t.append(f"“{snap['seed']}”", style="bold italic")
    t.append(f"   tick {snap['tick']}", style="dim")
    t.append(f"   {up // 3600:d}h{(up % 3600) // 60:02d}m{up % 60:02d}s", style="dim")
    t.append("   ")
    beat = "♥" if (snap["tick"] // 2) % 2 == 0 else "♡"
    t.append(beat, style="red" if snap["population"] else "dim")
    return t


def footer() -> Text:
    t = Text(style="dim")
    t.append(
        '  biotic whisper "…"   biotic drop nutrient|antibiotic|mutagen   biotic strains   ctrl-c to incubate (state is saved)'
    )
    return t


def build(c: Culture) -> Layout:
    snap = c.snapshot()
    root = Layout()
    root.split_column(
        Layout(name="head", size=1), Layout(name="body"), Layout(name="log", size=9), Layout(name="foot", size=1)
    )
    root["head"].update(header(c, snap))
    root["body"].split_row(Layout(name="dish", size=c.dish.w + 4), Layout(name="side"))
    root["dish"].update(Panel(render_dish(c), title="[dim]agar[/]", border_style="grey35", padding=(0, 1)))
    side = Group(
        Panel(vitals(c, snap), title="[dim]vitals[/]", border_style="grey35"),
        Panel(census_table(c, snap), title="[dim]census[/]", border_style="grey35"),
    )
    root["side"].update(side)
    root["log"].update(Panel(events(c, 7), title="[dim]incubator log[/]", border_style="grey35"))
    root["foot"].update(footer())
    return root


def observe(c: Culture, tick_seconds: float = config.TICK_SECONDS) -> None:
    """The culture runs on the main thread (its time budgets are signal-based);
    the eyepiece redraws from a background thread."""
    console = Console()
    stop = threading.Event()

    def render(live: Live) -> None:
        while not stop.wait(1 / 6):
            try:
                with c.lock:
                    frame = build(c)
                live.update(frame)
            except Exception:  # noqa: BLE001 — a bad frame must never stop the dish
                pass

    with Live(build(c), console=console, screen=True, refresh_per_second=6, transient=False) as live:
        threading.Thread(target=render, args=(live,), daemon=True).start()
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
