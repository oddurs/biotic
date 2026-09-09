"""biotic — a culture of cells that write themselves, in a dish you can watch."""

from __future__ import annotations

import argparse
import json
import sys
import time

from . import config
from .culture import Culture, sterilize
from .mind import Mind, MindError


def cmd_seed(a):
    mind = Mind()
    if not mind.awake:
        print(
            "no mind: set OPENROUTER_API_KEY in .env (the dish will still grow, with a default founder)",
            file=sys.stderr,
        )
    try:
        c = Culture.germinate(a.seed, mind, fresh=a.fresh)
    except FileExistsError as e:
        sys.exit(str(e))
    s = next(iter(c.registry.strains.values()))
    print(f"seeded “{a.seed}” — founding strain {s.id} {s.name}: {s.note}")
    print(f"  {config.SOMA / (s.id + '_' + s.name + '.py')}")
    print("  `biotic live` to watch it grow")


def cmd_live(a):
    from .tui import observe

    c = _culture()
    observe(c, tick_seconds=a.tick if a.tick else config.TICK_SECONDS)


def cmd_run(a):
    c = _culture()
    t0 = time.time()

    def progress():
        s = c.snapshot()
        print(
            f"tick {s['tick']:>6}  pop {s['population']:>5}  strains {len(s['census']):>3}  "
            f"agar {s['nutrient']:.2f}  {s['phase']}",
            file=sys.stderr,
        )

    import threading

    stop = threading.Event()
    if not a.quiet:

        def rep():
            while not stop.wait(5):
                progress()

        threading.Thread(target=rep, daemon=True).start()
    try:
        c.run(ticks=a.ticks, tick_seconds=a.tick if a.tick is not None else config.TICK_SECONDS)
    except KeyboardInterrupt:
        pass
    stop.set()
    progress()
    print(f"done in {time.time() - t0:.0f}s · growth curve in {config.CURVE}", file=sys.stderr)


def cmd_status(a):
    c = _culture()
    s = c.snapshot()
    print(f"seed        “{s['seed']}”")
    print(f"tick        {s['tick']}   phase {s['phase']}")
    print(f"population  {s['population']}  ({s['population'] / s['tiles']:.0%} of agar)")
    print(f"strains     {len(s['census'])} living / {s['strains_total']} arisen / generation {s['generation']}")
    print(f"agar        {s['nutrient']:.3f}")
    print(f"births      {s['births']}   deaths {s['deaths']}")
    print(f"mind        {s['mind']['model']}  {'awake' if s['mind']['awake'] else 'dormant'}")


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
    """Ask the mind one question, to check the wiring."""
    m = Mind()
    try:
        print(m.think("Reply in five words or fewer.", "Are you there?", max_tokens=20))
        print(f"ok · {m.model} · {m.last_latency:.1f}s")
    except MindError as e:
        sys.exit(f"mind error: {e}")


def cmd_sterilize(a):
    if not a.yes:
        ans = input("autoclave the dish? this destroys the culture and the fossil record in soma/ [y/N] ")
        if ans.strip().lower() != "y":
            return
    sterilize()
    print("sterile")


def _culture() -> Culture:
    try:
        return Culture.load()
    except FileNotFoundError as e:
        sys.exit(str(e))


def _intervene(req: dict) -> None:
    if not config.DISH_FILE.exists():
        sys.exit("nothing in the dish")
    config.INBOX.mkdir(parents=True, exist_ok=True)
    (config.INBOX / f"{time.time_ns()}.json").write_text(json.dumps(req))


def main(argv=None):
    p = argparse.ArgumentParser(prog="biotic", description=__doc__)
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("seed", help="inoculate a fresh dish from a word, phrase, or question")
    s.add_argument("seed")
    s.add_argument("--fresh", action="store_true", help="autoclave first if a culture exists")
    s.set_defaults(f=cmd_seed)

    s = sub.add_parser("live", help="watch the dish (default)")
    s.add_argument("--tick", type=float, help="seconds per tick")
    s.set_defaults(f=cmd_live)

    s = sub.add_parser("run", help="run headless, e.g. for an experiment")
    s.add_argument("--ticks", type=int)
    s.add_argument("--tick", type=float, help="seconds per tick (0 = as fast as possible)")
    s.add_argument("--quiet", action="store_true")
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
    s = sub.add_parser("sterilize", help="autoclave everything")
    s.add_argument("--yes", "-y", action="store_true")
    s.set_defaults(f=cmd_sterilize)

    a = p.parse_args(argv)
    if not a.cmd:
        if config.DISH_FILE.exists():
            return cmd_live(argparse.Namespace(tick=None))
        p.print_help()
        return
    return a.f(a)


if __name__ == "__main__":
    main()
