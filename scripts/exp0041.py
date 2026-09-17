"""Metrics for experiment 0041 — the mutagen's identity, a model comparison.

Reads the flask vessels produced by a tick-clocked run (curve.csv, events.jsonl,
strains.json, dish.json) and reports, per condition, the columns the cairn item
0041 asks for: membrane pass rate, call latency, USD per viable variant, novelty
and its slope, end diversity, genome-length drift, and a rubric read of a sample
of mutations. It is analysis, not apparatus: it lives here so the numbers in the
write-up can be regenerated, and its pure helpers are tested in tests/test_exp0041.py.

    python scripts/exp0041.py <flasks-root> c30b=qwen/... coder=qwen/... ...
"""

from __future__ import annotations

import csv
import difflib
import json
import random
import statistics
import sys
from pathlib import Path


def pass_rate(viable: int, attempted: int) -> float | None:
    """Fraction of mutagen calls whose daughter passed the membrane; None if none were made."""
    if attempted <= 0:
        return None
    return viable / attempted


def slope_per_1000(points: list[tuple[float, float]]) -> float | None:
    """Least-squares slope of y against x, scaled to a per-1000-x rate. None if fewer than two
    distinct x values (a slope needs a run in x)."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    n = len(xs)
    if n < 2 or len(set(xs)) < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    return (num / den) * 1000.0


def diff_changed_lines(parent: str, child: str) -> int:
    """Lines that differ between two genomes: added plus removed in a unified diff, ignoring
    the +++/--- file headers. The rubric's size measure."""
    changed = 0
    for line in difflib.unified_diff(parent.splitlines(), child.splitlines(), lineterm=""):
        if line.startswith(("+++", "---", "@@")):
            continue
        if line and line[0] in "+-":
            changed += 1
    return changed


def classify_size(changed: int) -> str:
    """The item's rubric, on the diff line count: small (<4), medium (4-12), rewrite (>12)."""
    if changed < 4:
        return "small"
    if changed <= 12:
        return "medium"
    return "rewrite"


def _read_curve(path: Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for raw in csv.DictReader(f):
            row: dict = {}
            for k, v in raw.items():
                if v is None or v == "":
                    row[k] = None
                    continue
                try:
                    row[k] = int(v)
                except ValueError:
                    try:
                        row[k] = float(v)
                    except ValueError:
                        row[k] = v
            rows.append(row)
    rows.sort(key=lambda r: r.get("tick") or 0)
    return rows


def _read_events(path: Path) -> list[dict]:
    out: list[dict] = []
    if not path.exists():
        return out
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(ev, dict):
                out.append(ev)
    return out


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    idx = q * (len(s) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(s) - 1)
    frac = idx - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def flask_metrics(vessel: Path, tail_fraction: float = 0.5) -> dict:
    """Every per-flask metric from one vessel directory."""
    rows = _read_curve(vessel / "curve.csv")
    last = rows[-1]
    attempted = last.get("mutations_attempted") or 0
    viable = last.get("mutations_viable") or 0
    end_tick = last.get("tick") or 0

    events = _read_events(vessel / "events.jsonl")
    mut_calls = [e for e in events if e.get("kind") == "call" and e.get("role") == "mutagen"]
    latencies = [float(e["latency"]) for e in mut_calls if e.get("latency") is not None]
    usd_mutagen = sum(float(e.get("usd") or 0.0) for e in mut_calls)
    usd_naturalist = sum(
        float(e.get("usd") or 0.0) for e in events if e.get("kind") == "call" and e.get("role") == "naturalist"
    )

    cutoff = end_tick * tail_fraction
    tail = [
        (r["tick"], r["arisen"])
        for r in rows
        if r.get("tick") is not None and r["tick"] >= cutoff and r.get("arisen") is not None
    ]

    strains = json.loads((vessel / "strains.json").read_text())["strains"]
    founder = next((s for s in strains if s.get("parent") is None), None)
    founder_len = len(founder["source"]) if founder else 0
    living = [s for s in strains if s.get("extinct_at") is None]
    living_lens = [len(s["source"]) for s in living]
    len_drift = (statistics.fmean(living_lens) - founder_len) if living_lens else None

    dish = json.loads((vessel / "dish.json").read_text())
    ledger = dish.get("mind", {}) or {}

    return {
        "end_tick": end_tick,
        "attempted": attempted,
        "viable": viable,
        "pass_rate": pass_rate(viable, attempted),
        "latency_mean": statistics.fmean(latencies) if latencies else None,
        "latency_p95": _percentile(latencies, 0.95),
        "usd_mutagen": usd_mutagen,
        "usd_naturalist": usd_naturalist,
        "usd_per_viable": (usd_mutagen / viable) if viable else None,
        "arisen": last.get("arisen"),
        "arisen_slope": slope_per_1000(tail),
        "shannon_end": last.get("shannon"),
        "dominance_end": last.get("dominance"),
        "population_end": last.get("population"),
        "strains_end": last.get("strains"),
        "len_drift": len_drift,
        "ledger_spent": ledger.get("spent_usd"),
        "ledger_calls": ledger.get("calls"),
    }


def _agg(values: list[float | None]) -> dict | None:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return {"mean": statistics.fmean(vals), "min": min(vals), "max": max(vals), "n": len(vals)}


def condition_metrics(flask_dirs: list[Path]) -> dict:
    """Per-flask metrics plus mean/min/max over the flasks of a condition."""
    per = [flask_metrics(d) for d in flask_dirs]
    keys = [
        "pass_rate",
        "latency_mean",
        "latency_p95",
        "usd_mutagen",
        "usd_naturalist",
        "usd_per_viable",
        "attempted",
        "viable",
        "arisen",
        "arisen_slope",
        "shannon_end",
        "dominance_end",
        "len_drift",
        "ledger_spent",
    ]
    agg = {k: _agg([m[k] for m in per]) for k in keys}
    return {"flasks": per, "agg": agg}


def sample_mutations(flask_dirs: list[Path], arm: str, k: int, seed: str) -> list[dict]:
    """Up to `k` mutations of the given arm ('llm' or 'random'), sampled with a fixed seed,
    each rated by the rubric. Parent and child genomes are diffed by source."""
    pool: list[dict] = []
    for d in flask_dirs:
        strains = json.loads((d / "strains.json").read_text())["strains"]
        by_id = {s["id"]: s for s in strains}
        for s in strains:
            if s.get("mutagen") != arm or not s.get("parent"):
                continue
            parent = by_id.get(s["parent"])
            if not parent:
                continue
            changed = diff_changed_lines(parent["source"], s["source"])
            pool.append(
                {
                    "flask": d.name,
                    "id": s["id"],
                    "name": s["name"],
                    "parent": parent["id"],
                    "changed_lines": changed,
                    "size": classify_size(changed),
                }
            )
    rng = random.Random(f"{seed}::{arm}")
    rng.shuffle(pool)
    return pool[:k]


def main(argv: list[str]) -> int:
    root = Path(argv[1])
    models = dict(pair.split("=", 1) for pair in argv[2:])
    report: dict = {"conditions": {}, "samples": {}}
    for cond, model in models.items():
        dirs = sorted(p for p in (root / cond).iterdir() if p.is_dir() and (p / "curve.csv").exists())
        report["conditions"][cond] = {"model": model, **condition_metrics(dirs)}
    for cond in models:
        dirs = sorted(p for p in (root / cond).iterdir() if p.is_dir() and (p / "curve.csv").exists())
        arm = "random" if cond == "random" else "llm"
        report["samples"][cond] = sample_mutations(dirs, arm, 5, "tide")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
