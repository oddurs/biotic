"""Replicate flasks: many dishes from one install.

The whole methodology of the field is replication. Lenski has twelve flasks; the citrate result
means something *because* eleven flasks did not do it. A flask here is one self-contained vessel
directory. `new` founds one ancestor and pours it into N flasks that share a seed — so their agar
is byte-for-byte identical — but each carry a distinct flask id salted into the dynamics RNGs, so
their trajectories diverge, exactly as replicate cultures of one clone do. `run` runs every flask
headless, one subprocess each, dormant and spending nothing. `curve_figure` overlays their curves.

Flasks are separate PROCESSES, never threads: the cell budget is a main-thread-only SIGALRM and
`config.*` is process-global, so two vessels in one process on different threads would corrupt
each other. `flasks run` therefore spawns one child per flask. See docs/flasks.md.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import config, curve, freezer, plot
from .culture import Culture, _fit_dish
from .mind import Mind


def flask_root(root: str | Path | None = None) -> Path:
    """Where a set of flasks lives: `root`, else $BIOTIC_FLASKS, else ./flasks. Relative to the
    working directory, not the checkout — ROOT is read-only once biotic is `uv tool install`ed."""
    return Path(root or os.environ.get("BIOTIC_FLASKS") or "flasks")


def flask_ids(n: int) -> list[str]:
    """Zero-padded ids 01…NN, wide enough for n (at least two digits, like Lenski's Ara-1…Ara-6)."""
    width = max(2, len(str(n)))
    return [str(i).zfill(width) for i in range(1, n + 1)]


def manifest_path(name: str, root: str | Path | None = None) -> Path:
    return flask_root(root) / name / "flasks.json"


def load_manifest(name: str, root: str | Path | None = None) -> dict:
    p = manifest_path(name, root)
    if not p.exists():
        raise FileNotFoundError(
            f"no flask set named “{name}” under {flask_root(root)} — `biotic flasks new {name} …` first"
        )
    return json.loads(p.read_text())


def flask_dirs(name: str, root: str | Path | None = None) -> list[Path]:
    """The flask vessels of a set, in manifest order."""
    base = flask_root(root) / name
    return [base / fid for fid in load_manifest(name, root)["flasks"]]


def _dormant() -> Mind:
    """A mind guaranteed asleep whatever the environment holds: no key, no local endpoint. Flasks
    default to this, so founding an ancestor spends nothing — item 0006 authorizes no spend, and
    awake replicate runs belong to a later item."""
    m = Mind()
    m.key = None
    m.base = ""
    return m


def new(
    name: str,
    seed: str,
    n: int = 12,
    root: str | Path | None = None,
    mind: Mind | None = None,
    size: tuple[int, int] | None = None,
    mutagen: str | None = None,
) -> dict:
    """Create `<root>/<name>/{01..NN}`, each a vessel of the SAME seed and SAME founder, each with
    a distinct flask id so the trajectories diverge. Refuses an existing, populated set.

    The ancestor is founded ONCE, in flask 01, from `mind` (default: a dormant mind, so the
    built-in fallback founder — no network, no spend); flasks 02..NN reuse that genome via
    `germinate(founder=...)`. One founding, ever. The dish geometry is fixed once (`size`, else
    fitted to the terminal) so every replicate shares its agar geometry. Writes flasks.json and
    returns the manifest."""
    if n < 1:
        raise ValueError(f"a set has at least 1 flask, not {n}")
    base = flask_root(root) / name
    ids = flask_ids(n)
    if base.exists() and any(base.iterdir()):
        raise FileExistsError(f"{base} already holds a set of flasks — pick another name, or remove it first")
    base.mkdir(parents=True, exist_ok=True)  # germinate's own VESSEL.mkdir is not parents=True
    w, h = size if size is not None else _fit_dish()
    mind = mind if mind is not None else _dormant()
    with config.vessel_scope(base / ids[0]):
        c = Culture.germinate(seed, mind, flask=ids[0], size=(w, h), mutagen=mutagen)
        (s,) = c.registry.strains.values()  # exactly one at the founding
        founder = (s.name, s.note, s.source)
        ancestor = {"id": s.id, "name": s.name, "note": s.note}
    for fid in ids[1:]:
        with config.vessel_scope(base / fid):
            Culture.germinate(seed, _dormant(), flask=fid, founder=founder, size=(w, h), mutagen=mutagen)
    man = {
        "name": name,
        "seed": seed,
        "n": n,
        "w": w,
        "h": h,
        "flasks": ids,
        "created": time.time(),
        "biotic": freezer.version(),
        "model": mind.model if mind.awake else None,  # null when the ancestor is the built-in fallback
        "mutagen": mutagen or config.MUTAGEN_KIND,  # the arm every flask of the set runs under
        "founder": ancestor,
    }
    manifest_path(name, root).write_text(json.dumps(man, indent=1))
    return man


def _argv(vessel: Path, ticks: int, tick: float) -> list[str]:
    return [
        sys.executable,
        "-m",
        "bio",
        "run",
        "--vessel",
        str(vessel),
        "--tick",
        str(tick),
        "--ticks",
        str(ticks),
        "--quiet",
    ]


def _child_env() -> dict[str, str]:
    """The environment a flask subprocess runs in, with the mind turned off so no replicate can
    spend from the project balance (item 0006 authorizes no spend; awake replicate runs are a
    later item). The keys are set to empty rather than removed: the child's own `_load_dotenv`
    would `setdefault` them back from `.env`, but a present (empty) value is left alone, and an
    empty key with an empty base URL makes `Mind.awake` false."""
    env = dict(os.environ)
    env["OPENROUTER_API_KEY"] = ""
    env["BIOTIC_API_KEY"] = ""
    env["BIOTIC_BASE_URL"] = ""
    return env


def run(
    name: str,
    ticks: int | None,
    tick: float = 0.0,
    parallel: int = 1,
    root: str | Path | None = None,
    runner=None,
) -> list[tuple[str, int]]:
    """Run every flask headless for `ticks` ticks. `ticks` is required — a replicate run is bounded.

    The default runner spawns one subprocess per flask (`biotic run --vessel <dir>`), at most
    `parallel` at once, with the mind DISABLED in the child environment so nothing spends. Returns
    `[(flask_id, returncode)]` in flask order. `runner` is injectable for tests: it is handed
    `[(flask_id, vessel_dir), …]` and returns the same result shape, in process and on the main
    thread."""
    if ticks is None:
        raise ValueError("flasks run is a bounded run — say how many ticks (--ticks)")
    ids = load_manifest(name, root)["flasks"]
    base = flask_root(root) / name
    jobs = [(fid, base / fid) for fid in ids]
    if runner is not None:
        return runner(jobs)
    env = _child_env()
    parallel = max(1, int(parallel))
    pending = list(jobs)
    running: dict[str, subprocess.Popen] = {}
    codes: dict[str, int] = {}
    while pending or running:
        while pending and len(running) < parallel:
            fid, d = pending.pop(0)
            running[fid] = subprocess.Popen(_argv(d, ticks, tick), cwd=Path.cwd(), env=env)
        # block on one, then reap every child that has finished
        next(iter(running.values())).wait()
        for fid in [f for f, p in running.items() if p.poll() is not None]:
            codes[fid] = running.pop(fid).returncode
    return [(fid, codes[fid]) for fid in ids]


def curve_figure(
    name: str,
    cols: tuple[str, ...] = ("population",),
    root: str | Path | None = None,
    since: int | None = None,
) -> plot.Figure:
    """Overlay every flask's growth curve on one figure: one Trace per flask, per column. Reads
    each flask's curve.csv (sorted by tick, Nones dropped inside `plot.overlay`) and nothing
    else."""
    base = flask_root(root) / name
    man = load_manifest(name, root)
    series: list[tuple[str, list[dict]]] = []
    for fid in man["flasks"]:
        rows = [r for r in curve.read(base / fid / "curve.csv") if r.get("tick") is not None]
        rows.sort(key=lambda r: r["tick"])
        series.append((fid, rows))
    return plot.overlay(man["seed"], series, list(cols), since=since)
