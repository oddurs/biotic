"""biotic — a culture of cells that write themselves, in a dish you can watch."""

from __future__ import annotations

import argparse
import json
import sys
import time

from . import config, freezer, naturalist
from .culture import Culture, incubating, sterilize
from .dish import Dish
from .mind import Dormant, Mind, MindError, fmt_budget, fmt_usd
from .strains import Registry


def cmd_seed(a):
    _not_running()
    mind = Mind()
    if not mind.awake:
        print(
            "no mind: set OPENROUTER_API_KEY in .env (the dish will still grow, with a default founder)",
            file=sys.stderr,
        )
    try:
        c = Culture.germinate(a.seed, mind, fresh=a.fresh, budget=a.budget)
    except (FileExistsError, RuntimeError) as e:
        sys.exit(str(e))
    s = next(iter(c.registry.strains.values()))
    print(f"seeded “{a.seed}” — founding strain {s.id} {s.name}: {s.note}")
    print(f"  {config.SOMA / (s.id + '_' + s.name + '.py')}")
    print(f"  budget {fmt_budget(mind.spent_usd, mind.budget_usd)}")
    print("  `biotic live` to watch it grow")


def cmd_live(a):
    from .tui import observe

    _not_running()
    c = _culture(a.budget)
    try:
        observe(c, tick_seconds=a.tick if a.tick else config.TICK_SECONDS)
    except RuntimeError as e:
        sys.exit(str(e))


def cmd_run(a):
    _not_running()
    c = _culture(a.budget)
    t0 = time.time()

    def progress():
        with c.lock:  # the dish steps on the main thread; a snapshot must not read it mid-tick
            s = c.snapshot()
        print(
            f"tick {s['tick']:>6}  pop {s['population']:>5}  strains {len(s['census']):>3}  "
            f"H {s['metrics']['shannon']:.2f}  agar {s['nutrient']:.2f}  {s['phase']}  {fmt_usd(s['mind']['spent_usd'])}",
            file=sys.stderr,
        )

    import threading

    stop = threading.Event()
    if not a.quiet:
        print(f"budget {fmt_budget(c.mind.spent_usd, c.mind.budget_usd)}", file=sys.stderr)

        def rep():
            while not stop.wait(5):
                progress()

        threading.Thread(target=rep, daemon=True).start()
    try:
        c.run(ticks=a.ticks, tick_seconds=a.tick if a.tick is not None else config.TICK_SECONDS)
    except KeyboardInterrupt:
        pass
    except RuntimeError as e:
        sys.exit(str(e))
    stop.set()
    progress()
    print(f"done in {time.time() - t0:.0f}s · growth curve in {config.CURVE}", file=sys.stderr)


def cmd_status(a):
    c = _culture()
    s = c.snapshot()
    print(f"seed        “{s['seed']}”")
    print(f"tick        {s['tick']}   phase {s['phase']}")
    print(f"population  {s['population']}  ({s['population'] / s['tiles']:.0%} of agar)")
    mt = s["metrics"]
    print(f"strains     {len(s['census'])} living / {mt['arisen']} arisen / {mt['extinct']} extinct")
    print(
        f"diversity   H {mt['shannon']:.3f} nats · dominance {mt['dominance']:.2f} · mean generation {mt['mean_gen']:.1f}"
    )
    print(f"agar        {s['nutrient']:.3f}")
    print(f"births      {s['births']}   deaths {s['deaths']}")
    m = s["mind"]
    print(f"mind        {m['model']}  {'awake' if m['awake'] else 'dormant'}")
    calls = f"{m['calls']} call{'s' if m['calls'] != 1 else ''}"
    exhausted = "  — exhausted" if m["awake"] and m["exhausted"] else ""  # a dormant mind is dormant, whatever its cap
    print(f"spent       {fmt_budget(m['spent_usd'], m['budget_usd'])}  ({calls}){exhausted}")
    ticks = freezer.dish_ticks()
    n = len(freezer.stems())
    if n:
        last = f" · last at tick {ticks[-1]}" if ticks else ""
        print(f"freezer     {n} sample{'s' if n != 1 else ''}{last}")
    else:
        print("freezer     empty")
    notes = naturalist.read_notes(config.FIELDNOTES)
    if notes:
        print(f"notes       {len(notes)} · last at tick {notes[-1].tick} ({notes[-1].when})")
    else:
        print("notes       none")
    pid = incubating()
    if pid is not None:
        print(f"incubator   running (pid {pid})")


def cmd_strains(a):
    c = _culture()
    rows = c.registry.living(c.dish.census())
    total = sum(n for _, n in rows) or 1
    print(f"{'id':<5} {'gen':>3} {'n':>5} {'share':>6}  name / note")
    for s, n in rows:
        print(f"{s.id:<5} {s.generation:>3} {n:>5} {n / total:>6.0%}  {s.name}")
        if s.note:
            print(f"{'':<23}{s.note}")
    if a.all:
        dead = [s for s in c.registry.strains.values() if s.extinct_at is not None]
        if dead:
            print(f"\nextinct ({len(dead)}):")
            for s in sorted(dead, key=lambda s: s.extinct_at):
                print(f"  {s.id} {s.name:<28} gen {s.generation} · lived {s.extinct_at - s.born} ticks · peak {s.peak}")


def cmd_genome(a):
    c = _culture()
    sid = a.id
    if sid == "top":
        rows = c.registry.living(c.dish.census())
        if not rows:
            sys.exit("dish is sterile")
        sid = rows[0][0].id
    s = c.registry.strains.get(sid)
    if not s:
        sys.exit(f"no strain {sid}")
    print(f"# {s.id} {s.name} — gen {s.generation}, born tick {s.born}")
    if s.note:
        print(f"# {s.note}")
    print("# lineage: " + " → ".join(x.name for x in c.registry.lineage_of(sid)))
    print()
    print(s.source)


def cmd_log(a):
    if not config.EVENTS.exists():
        return
    lines = config.EVENTS.read_text().splitlines()[-a.n :]
    for line in lines:
        ev = json.loads(line)
        print(f"{time.strftime('%H:%M:%S', time.localtime(ev['t']))} {ev['tick']:>6} {ev['kind']:<9} {ev['msg']}")


def cmd_curve(a):
    """Draw the growth curve. Reads curve.csv, events.jsonl and seed.txt and nothing else: no
    culture is built, no lock is taken, so it runs beside a live incubator."""
    import shutil
    from pathlib import Path

    from rich.console import Console

    from . import curve, plot

    try:
        cols = plot.parse_cols(a.cols)
    except ValueError as e:
        sys.exit(str(e))
    if not config.CURVE.exists():
        sys.exit("no growth curve yet — `biotic run` or `biotic live` writes vessel/curve.csv")
    try:
        rows = curve.read()
    except curve.ERRORS as e:
        sys.exit(f"could not read {config.CURVE}: {e}")
    try:
        seed = config.SEED_FILE.read_text().strip() if config.SEED_FILE.exists() else None
        evs = curve.events()
    except curve.ERRORS as e:
        sys.exit(f"could not read {config.VESSEL}: {e}")
    try:
        fig = plot.figure(rows, evs, cols, since=a.since, branch=a.branch, seed=seed)
    except ValueError as e:
        sys.exit(str(e))
    if a.png:
        try:
            print(f"wrote {plot.png(fig, Path(a.png))}")
        except plot.PlotUnavailable as e:
            sys.exit(str(e))
        except OSError as e:
            sys.exit(f"could not write {a.png}: {e}")
        return
    width = max(40, a.width or shutil.get_terminal_size((100, 30)).columns)
    Console(width=width).print(plot.render(fig, width, a.height), highlight=False, soft_wrap=False)


def cmd_notes(a):
    """The naturalist's notebook, last entries first in time order. Reads the file only: no dish
    is loaded, so it works beside a running incubator."""
    notes = naturalist.read_notes(config.FIELDNOTES)
    if not notes:
        print("no field notes yet")
        if not config.NOTES_EVERY:
            print("  BIOTIC_NOTES_EVERY=0 — the naturalist is off")
        else:
            print(f"  the naturalist writes one every {config.NOTES_EVERY} ticks while the mind is awake")
        return
    n = max(0, a.n)
    for note in notes[-n:] if n else notes:
        print(f"## tick {note.tick} · {note.when}")
        print()
        print(note.text)
        print()


def cmd_whisper(a):
    _intervene({"whisper": " ".join(a.text)})
    print("pinned to the incubator")


def cmd_drop(a):
    req = {"drop": a.what}
    if a.at:
        x, y = a.at.split(",")
        req["at"] = [int(x), int(y)]
    if a.r:
        req["r"] = a.r
    _intervene(req)
    print(f"{a.what} dropped")


def cmd_minds(a):
    m = Mind()
    try:
        models = m.models()
    except Exception as e:  # noqa: BLE001
        sys.exit(f"could not list models: {e}")
    q = (a.query or "").lower()
    for md in models:
        mid = md.get("id", "")
        if q and q not in mid.lower():
            continue
        pr = md.get("pricing") or {}
        try:
            cost = f"${float(pr.get('prompt', 0)) * 1e6:.2f}/{float(pr.get('completion', 0)) * 1e6:.2f} per M"
        except (TypeError, ValueError):
            cost = ""
        print(f"{mid:<50} {cost}")


def cmd_probe(a):
    """Ask the mind one question, to check the wiring. Not a dish call: no budget applies."""
    m = Mind(budget_usd=float("inf"))
    try:
        print(m.think("Reply in five words or fewer.", "Are you there?", max_tokens=20, role="probe"))
        print(f"ok · {m.model} · {m.last_latency:.1f}s · {fmt_usd(m.last_usd)}")
    except (Dormant, MindError) as e:
        sys.exit(f"mind error: {e}")


def cmd_sterilize(a):
    _not_running()
    if not a.yes:
        what = "the freezer too" if a.freezer else "the freezer is kept; --freezer empties it"
        ans = input(f"autoclave the dish? this destroys the culture and the fossil record in soma/ ({what}) [y/N] ")
        if ans.strip().lower() != "y":
            return
    try:
        sterilize(freezer=a.freezer)
    except RuntimeError as e:
        sys.exit(str(e))
    print("sterile" + (" — the freezer is empty too" if a.freezer else " — the freezer is kept"))


# --- the freezer ------------------------------------------------------------
def cmd_freeze(a):
    if a.label is not None:
        try:
            a.label = freezer.clean_label(a.label)
        except ValueError as e:
            sys.exit(str(e))
    if a.strain:
        req = {"freeze_strain": a.strain, "label": a.label}
    else:
        req = {"freeze": a.label or "manual"}
    if _queue_if_running(req, "freeze"):
        return
    c = _culture()
    try:
        path = c.freeze_strain(a.strain, a.label) if a.strain else c.freeze(a.label or "manual")
    except KeyError:
        sys.exit(f"no strain {a.strain}")
    except ValueError as e:
        sys.exit(str(e))
    except OSError as e:
        sys.exit(f"freezer not writable: {e}")
    print(f"frozen as {freezer.stem_of(path)}")
    print(f"  {path}")


def cmd_revive(a):
    if bool(a.key) == bool(a.strain):
        sys.exit("say what to revive: a tick or sample name, or --strain ID")
    if not a.strain and (a.into or a.n is not None or a.at):
        sys.exit("--into, --n and --at go with --strain")
    if a.strain and a.label:
        sys.exit("--label picks one of several dish samples at a tick; it does not go with --strain")
    if a.at and (a.into or "fresh") == "fresh":
        sys.exit("--at goes with --into current; a fresh dish is inoculated at the centre")
    if a.label is not None:
        try:
            a.label = freezer.clean_label(a.label)  # as `freeze --label` stored it
        except ValueError as e:
            sys.exit(str(e))
    try:
        path = freezer.resolve(a.strain or a.key, label=a.label, kind="strain" if a.strain else "dish")
        doc = freezer.read(path)
    except (LookupError, ValueError) as e:
        sys.exit(str(e))
    stem = freezer.stem_of(path)
    had_dish = config.DISH_FILE.exists()
    at = None
    if a.at:
        try:
            x, y = a.at.split(",")
            at = (int(x), int(y))
        except ValueError:
            sys.exit("--at wants x,y")
    if a.strain:
        if doc["kind"] != "strain":
            sys.exit(f"{stem} is a dish sample — `biotic revive {stem}`")
        n = config.INOCULUM if a.n is None else a.n
        if (a.into or "fresh") == "fresh":
            _revive_fresh(a, path, doc, had_dish, n)
            return
        if not had_dish:
            sys.exit("nothing in the dish to revive into — leave out --into for a fresh dish")
        req = {"revive_strain": stem, "n": n, "at": list(at) if at else None}
    else:
        if doc["kind"] != "dish":
            sys.exit(f"{stem} is a strain sample — `biotic revive --strain {stem}`")
        if had_dish and not a.yes:
            about = "about " if incubating() else ""  # dish.json trails a running incubator by up to 150 ticks
            q = f"replace the dish at {about}tick {_dish_tick()} with the sample from tick {doc['tick']}? "
            if not _confirm(q + "it is frozen first as pre-revive"):
                return
        req = {"revive": stem}
    if _queue_if_running(req, "revive"):
        return
    if had_dish:
        c = _culture()
    else:
        seed, w, h = doc["seed"], doc["dish"]["w"], doc["dish"]["h"]
        c = Culture(seed, Dish(seed, int(w), int(h)), Registry(seed), Mind())
    try:
        if a.strain:
            c.revive_strain(path, n=n, at=at)
        else:
            c.revive(path)
    except (ValueError, KeyError) as e:
        sys.exit(str(e))
    except OSError as e:
        sys.exit(f"freezer not writable: {e}")  # the pre-revive freeze; nothing has changed
    print(c.events[-1]["msg"])


def _revive_fresh(a, path, doc, had_dish: bool, n: int) -> None:
    """A fresh dish of a frozen strain is a germination with a given founder: it autoclaves the
    vessel, so it needs a stopped incubator. germinate() passes the sample through the membrane,
    then freezes the dish that is there as pre-revive, then autoclaves — in that order, so a
    refused sample leaves nothing behind."""
    pid = incubating()
    if pid is not None:
        sys.exit(f"the incubator is running (pid {pid}); stop it (ctrl-c) before reviving into a fresh dish")
    s = doc["strain"]
    if had_dish and not a.yes:
        q = f"autoclave the dish at tick {_dish_tick()} and inoculate {s['name']} ({s['id']}) into fresh agar? "
        if not _confirm(q + "it is frozen first as pre-revive"):
            return
    try:
        c = Culture.germinate(doc["seed"], Mind(), fresh=True, thaw=path, n=n)
    except (ValueError, KeyError, RuntimeError) as e:
        sys.exit(str(e))
    except OSError as e:
        sys.exit(f"freezer not writable: {e}")  # the pre-revive freeze comes before the autoclave
    print(next(e["msg"] for e in reversed(c.events) if e["kind"] == "revived"))
    print(f"  seed “{c.seed}”, {c.dish.w}×{c.dish.h} — `biotic live` to watch it grow")


def cmd_freezer(a):
    es = freezer.entries()
    if a.json:
        from dataclasses import asdict

        print(json.dumps([asdict(e) for e in es], indent=1))
        return
    if not es:
        print("nothing in the freezer")
        return
    seed = config.SEED_FILE.read_text().strip() if config.SEED_FILE.exists() else None
    size = sum(e.size for e in es) / 1e6
    where = config.FREEZER
    try:
        where = where.relative_to(config.ROOT)
    except ValueError:
        pass
    head = f"freezer for “{seed}”" if seed else "freezer"
    print(f"{head} — {len(es)} sample{'s' if len(es) != 1 else ''}, {size:.1f} MB, {where}")
    dishes = [e for e in es if e.kind == "dish"]
    strains = [e for e in es if e.kind == "strain"]
    if dishes:
        print(f"{'tick':>7}  {'label':<12} {'frozen':<16} {'pop':>5}  {'strains':<8} from")
        for e in dishes:
            branch = f"← {e.revived_from}" if e.revived_from is not None else ""  # the last hop of the revival chain
            foreign = f"  seed “{e.seed}”" if seed and e.seed != seed else ""
            strains_col = f"{e.strains_living}/{e.strains_total}"
            print(
                f"{e.tick:>7}  {e.label or '':<12} {freezer.when(e.frozen_at):<16} "
                f"{e.population if e.population is not None else '?':>5}  {strains_col:<8} {branch}{foreign}"
            )
    if strains:
        print("strains")
        for e in strains:
            foreign = f"  seed “{e.seed}”" if seed and e.seed != seed else ""
            print(
                f"{e.strain_id or '':>7}  {e.strain_name or '':<12} gen {e.generation if e.generation is not None else '?':<3} "
                f"from tick {e.tick:<7} {freezer.when(e.frozen_at):<16} {e.stem}{foreign}"
            )


def _confirm(question: str) -> bool:
    return input(question + " [y/N] ").strip().lower() == "y"


def _dish_tick() -> int:
    try:
        return int(json.loads(config.DISH_FILE.read_text())["tick"])
    except (OSError, ValueError, KeyError):
        return 0


def _not_running() -> None:
    pid = incubating()
    if pid is not None:
        sys.exit(f"the incubator is already running (pid {pid})")


def _queue_if_running(req: dict, verb: str) -> bool:
    """Hand a freezer request to the running incubator. It is stamped with that incubator's pid:
    a freeze or a revive queued for a run that has since stopped is dropped by the next one, not
    applied days later unannounced (a whisper or a drop is kept; those are notes on the bench)."""
    pid = incubating()
    if pid is None:
        return False
    _intervene({**req, "pid": pid})
    print(f"the incubator is running (pid {pid}); {verb} queued — taken within 3 ticks. `biotic log` shows the result")
    return True


def _culture(budget: float | None = None) -> Culture:
    try:
        return Culture.load(budget=budget)
    except FileNotFoundError as e:
        sys.exit(str(e))


def _cells(v: str) -> int:
    n = int(v)
    if n < 1:
        raise argparse.ArgumentTypeError(f"an inoculum is at least 1 cell, not {n}")
    return n


def _intervene(req: dict) -> None:
    if not config.DISH_FILE.exists():
        sys.exit("nothing in the dish")
    config.INBOX.mkdir(parents=True, exist_ok=True)
    (config.INBOX / f"{time.time_ns()}.json").write_text(json.dumps(req))


def main(argv=None):
    p = argparse.ArgumentParser(prog="biotic", description=__doc__)
    sub = p.add_subparsers(dest="cmd")
    budget_help = (
        "dollars this dish may spend on the mind "
        "(default: what the dish remembers, else BIOTIC_BUDGET_USD, else 2.00; inf for no cap)"
    )

    s = sub.add_parser("seed", help="inoculate a fresh dish from a word, phrase, or question")
    s.add_argument("seed")
    s.add_argument("--fresh", action="store_true", help="autoclave first if a culture exists")
    s.add_argument("--budget", type=float, help=budget_help)
    s.set_defaults(f=cmd_seed)

    s = sub.add_parser("live", help="watch the dish (default)")
    s.add_argument("--tick", type=float, help="seconds per tick")
    s.add_argument("--budget", type=float, help=budget_help)
    s.set_defaults(f=cmd_live)

    s = sub.add_parser("run", help="run headless, e.g. for an experiment")
    s.add_argument("--ticks", type=int)
    s.add_argument("--tick", type=float, help="seconds per tick (0 = as fast as possible)")
    s.add_argument(
        "--quiet", action="store_true", help="no budget line or progress reports; the summary at the end still prints"
    )
    s.add_argument("--budget", type=float, help=budget_help)
    s.set_defaults(f=cmd_run)

    sub.add_parser("status").set_defaults(f=cmd_status)
    s = sub.add_parser("strains", help="census of living strains")
    s.add_argument("--all", action="store_true", help="include extinct")
    s.set_defaults(f=cmd_strains)
    s = sub.add_parser("genome", help="print a strain's code (`top` for the dominant one)")
    s.add_argument("id")
    s.set_defaults(f=cmd_genome)
    s = sub.add_parser("log")
    s.add_argument("-n", type=int, default=30)
    s.set_defaults(f=cmd_log)
    s = sub.add_parser(
        "curve", help="plot the growth curve: population and strains by tick, with phase and drop markers"
    )
    s.add_argument(
        "--cols",
        default="population,strains",
        metavar="COLS",
        help="comma-separated columns of curve.csv; the first is the main panel, the rest are drawn under it",
    )
    s.add_argument("--since", type=int, metavar="TICK", help="rows from this tick on")
    s.add_argument("--branch", type=int, metavar="N", help="which timeline after a revive (default: the last)")
    s.add_argument("--png", metavar="OUT", help="write a PNG with matplotlib instead of printing (the plot extra)")
    s.add_argument("--width", type=int, help="columns (default: the terminal's)")
    s.add_argument("--height", type=int, default=12, help="rows of the main panel; the others get half")
    s.set_defaults(f=cmd_curve)
    s = sub.add_parser("notes", help="the naturalist's field notes")
    s.add_argument("-n", type=int, default=5, help="the last N entries (0 for the whole notebook)")
    s.set_defaults(f=cmd_notes)
    s = sub.add_parser("whisper", help="pin a note the mutagen will see")
    s.add_argument("text", nargs="+")
    s.set_defaults(f=cmd_whisper)
    s = sub.add_parser("drop", help="intervene in the dish")
    s.add_argument("what", choices=["nutrient", "antibiotic", "mutagen"])
    s.add_argument("--at", help="x,y")
    s.add_argument("--r", type=float, help="radius")
    s.set_defaults(f=cmd_drop)
    s = sub.add_parser("minds", help="list models available to the mind")
    s.add_argument("query", nargs="?")
    s.set_defaults(f=cmd_minds)
    sub.add_parser("probe", help="check the mind answers").set_defaults(f=cmd_probe)
    s = sub.add_parser("sterilize", help="autoclave everything (the freezer is kept unless --freezer)")
    s.add_argument("--yes", "-y", action="store_true")
    s.add_argument("--freezer", action="store_true", help="empty the freezer too")
    s.set_defaults(f=cmd_sterilize)

    s = sub.add_parser("freeze", help="put the dish, or one strain, in the freezer")
    s.add_argument("--label", help="a-z, 0-9, _ and -; default `manual`")
    s.add_argument("--strain", metavar="ID", help="freeze one strain's genome and a cell's memory instead")
    s.set_defaults(f=cmd_freeze)
    s = sub.add_parser("revive", help="replace the dish with a frozen sample, or inoculate a frozen strain")
    s.add_argument("key", nargs="?", metavar="TICK|SAMPLE", help="a tick, or a sample name from `biotic freezer`")
    s.add_argument("--label", help="with a tick: which of the samples at that tick")
    s.add_argument("--strain", metavar="ID|SAMPLE", help="a strain sample instead of a dish sample")
    s.add_argument(
        "--into",
        choices=["fresh", "current"],
        help="a fresh dish (default; the incubator must be stopped) or the current one",
    )
    s.add_argument("--n", type=_cells, help=f"cells to inoculate, fresh or current (default {config.INOCULUM})")
    s.add_argument("--at", help="x,y — where in the current dish (default: the centre); --into current only")
    s.add_argument("--yes", "-y", action="store_true", help="do not ask before replacing the dish")
    s.set_defaults(f=cmd_revive)
    s = sub.add_parser("freezer", help="what is in the freezer")
    s.add_argument("--json", action="store_true")
    s.set_defaults(f=cmd_freezer)

    a = p.parse_args(argv)
    if not a.cmd:
        if config.DISH_FILE.exists():
            return cmd_live(argparse.Namespace(tick=None, budget=None))
        p.print_help()
        return
    return a.f(a)


if __name__ == "__main__":
    main()
