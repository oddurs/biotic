"""Constants and environment. The physics of the dish live here."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the checkout; the bio package lives under it


def _load_dotenv() -> None:
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


# --- the vessel ----------------------------------------------------------
# One install can hold many dishes (replicate flasks; docs/flasks.md). Every path a culture
# reads or writes hangs off one vessel directory, and `_paths` is the single source of truth
# for the whole set. `use_vessel` repoints every vessel-derived global at another directory;
# `vessel_scope` does it for the length of a `with` and restores the globals afterward. Modules
# read `config.<NAME>` at call time, so reassigning these globals is enough. ROOT stays anchored
# to the checkout (the membrane runs a subprocess with cwd=ROOT) — only vessel-derived names move.
def _paths(vessel: Path) -> dict[str, Path]:
    return {
        "VESSEL": vessel,
        "INBOX": vessel / "inbox",
        "SEED_FILE": vessel / "seed.txt",
        "GENESIS": vessel / "genesis.py",
        "DISH_FILE": vessel / "dish.json",
        "STRAINS_FILE": vessel / "strains.json",
        "EVENTS": vessel / "events.jsonl",
        "CURVE": vessel / "curve.csv",
        "WHISPERS": vessel / "whispers.md",
        "PRICES_FILE": vessel / "prices.json",
        "FIELDNOTES": vessel / "fieldnotes.md",  # the naturalist's notebook
        "FREEZER": vessel / "freezer",  # frozen samples of the dish and of strains; sterilize keeps it
        "LOCK_FILE": vessel / "incubator.lock",  # held (flock) while a culture runs
        "SOMA": vessel / "soma",  # the fossil record; one per flask, inside the vessel
        "FLASK_FILE": vessel / "flask.txt",  # the flask id, when this vessel is one replicate of many
    }


def use_vessel(path) -> Path:
    """Point every vessel-derived global at `path` and return it. The one way to change vessels."""
    g = globals()
    v = Path(path).expanduser()
    for k, p in _paths(v).items():
        g[k] = p
    return v


@contextmanager
def vessel_scope(path):
    """Act on another vessel for the length of the block, then restore the globals exactly.

    Single-process only: the globals are process-wide, so two vessels must never be scoped at
    once from different threads (docs/flasks.md). Replicates run as separate processes."""
    saved = {k: globals()[k] for k in _paths(VESSEL)}
    try:
        use_vessel(path)
        yield globals()["VESSEL"]
    finally:
        globals().update(saved)


VESSEL = Path(env("BIOTIC_VESSEL") or (ROOT / "vessel"))
use_vessel(VESSEL)  # sets VESSEL, INBOX, SEED_FILE, … from the one source of truth above


# --- the mind (mutagen) -------------------------------------------------
# Any OpenAI-compatible endpoint. Ollama works with
#   BIOTIC_BASE_URL=http://localhost:11434/v1  (no key needed)
BASE_URL = env("BIOTIC_BASE_URL", "https://openrouter.ai/api/v1")
API_KEY = env("OPENROUTER_API_KEY") or env("BIOTIC_API_KEY")
MODEL = env("BIOTIC_MODEL", "qwen/qwen3-coder")
MUTAGEN_INTERVAL = float(env("BIOTIC_MUTAGEN_INTERVAL", "12"))  # min seconds between LLM calls
MUTAGEN_TEMP = float(env("BIOTIC_MUTAGEN_TEMP", "1.0"))
BUDGET_USD = max(0.0, float(env("BIOTIC_BUDGET_USD", "2.00")))  # dollars a dish may spend on the mind; inf = no cap
MUTAGEN_BACKOFF = 15.0  # seconds after the first failed call; doubles per consecutive failure
MUTAGEN_BACKOFF_MAX = 600.0  # cap on the doubling
RETRY_AFTER_MAX = 3600.0  # the most a Retry-After header is honoured for
# The mutagen's clock. wall: the thread calls the mind at most every MUTAGEN_INTERVAL seconds and the
# dish never waits (biotic live's default). tick: the dish itself calls at most every MUTAGEN_EVERY_TICKS
# ticks and waits for the reply (biotic run's default), so the supply of variants is a function of ticks
# and budget, not of the machine. docs/experiments.md
MUTAGEN_CLOCK = env("BIOTIC_MUTAGEN_CLOCK")  # "wall" | "tick" | None (None: by command); checked in Culture.use_clock
MUTAGEN_EVERY_TICKS = max(1, int(env("BIOTIC_MUTAGEN_EVERY_TICKS", "40")))  # tick clock: min ticks between calls
MUTAGEN_BACKOFF_INTERVALS = 2  # tick clock: intervals closed after the first failed call; doubles per failure
MUTAGEN_BACKOFF_INTERVALS_MAX = 50  # cap on that doubling, in intervals

# --- the dish ------------------------------------------------------------
WIDTH = int(env("BIOTIC_WIDTH") or 72)  # defaults; `biotic seed` fits the dish to the terminal
HEIGHT = int(env("BIOTIC_HEIGHT") or 34)
TICK_SECONDS = float(env("BIOTIC_TICK", "0.5"))

# --- energetics ----------------------------------------------------------
BASAL_COST = 0.010  # what it costs to be alive, per tick
MOVE_COST = 0.025
EMIT_COST = 0.006
EAT_RATE = 0.06  # max nutrient converted per eat
DIVIDE_THRESHOLD = 1.0  # energy needed to divide
INITIAL_ENERGY = 0.6
MAX_ENERGY = 2.0
MAX_AGE = 600  # ticks; senescence
NECROMASS = 0.35  # fraction of a dead cell's energy returned to agar, plus a fixed bit
CORPSE_NUTRIENT = 0.12

# --- agar ----------------------------------------------------------------
AGAR_MEAN = 0.45  # initial nutrient richness
AGAR_PATCHINESS = 0.35  # how lumpy the agar is
DIFFUSION = 0.04  # nutrient diffusion per tick
REPLENISH = float(env("BIOTIC_REPLENISH", "0.0025"))  # 0 = a truly closed dish
PHEROMONE_DECAY = 0.06
PHEROMONE_DIFFUSION = 0.10

# --- mutation ------------------------------------------------------------
MUTATION_RATE = float(env("BIOTIC_MUTATION_RATE", "0.06"))  # per division
# Which mutagen a division rolls: the semantic one (the mind), the offline random control arm
# (bio/mutagen_random.py), or a mix. In `mixed`, RANDOM_SHARE of rolls go to the random mutagen.
# A bad BIOTIC_MUTAGEN is not raised at import (mirrors MUTAGEN_CLOCK); Culture.use_mutagen names
# it at settle time, before the dish runs. docs/mutagen.md
MUTAGEN_KINDS = ("llm", "random", "mixed")
MUTAGEN_KIND = (env("BIOTIC_MUTAGEN", "mixed") or "mixed").strip().lower()  # the default arm
RANDOM_SHARE = min(1.0, max(0.0, float(env("BIOTIC_RANDOM_SHARE", "0.25"))))  # mixed: fraction to the random arm
CELL_TIME_BUDGET = 0.004  # seconds a single live() may take before lysis
GENOME_MAX_CHARS = 2400
MEMORY_MAX_CHARS = 2048  # a cell's memory as plain JSON, after every tick; more bursts the cell
MEMORY_MAX_DEPTH = 16  # how deep lists, tuples and dicts may nest inside it
INOCULUM = 5  # cells placed at seeding

# --- features (opt-in dish rules; docs/predation.md) ---------------------
# Rules a dish keeps off unless it is seeded `--with <name>` or `drop feature <name>` turns it
# on mid-run. Off by default, so no dish that predates this alters.
FEATURES = ("lyse", "give")

# --- predation (bio/dish.py; the `lyse` feature) -------------------------
LYSE_COST = 0.05  # what an attack costs the attacker, win or lose
LYSE_YIELD = 0.6  # fraction of the defender's energy the attacker gains on a kill
LYSE_RECOIL = 0.03  # extra cost when the attack fails
LYSE_K = 2.0  # sigmoid steepness; energies are 0..MAX_ENERGY (2.0), so the arg is ±4, p ≈ 0.02..0.98, no overflow

# --- sharing (bio/dish.py; the `give` feature; docs/sharing.md) ----------
GIVE_EFFICIENCY = 0.9  # fraction of the given energy the neighbour receives; the rest is lost as heat
GIVE_RESERVE = 0.05  # energy a giver always keeps; it never gives itself below this

# --- the freezer (bookkeeping, not physics) ------------------------------
FREEZE_EVERY = int(env("BIOTIC_FREEZE_EVERY", "2000"))  # ticks between automatic samples; 0 disables
REVIVE_WATCH = 300  # ticks a revived strain is watched before the log says whether it took

# --- the naturalist (an observer; bookkeeping, not physics) ---------------
NOTES_EVERY = int(env("BIOTIC_NOTES_EVERY", "600"))  # ticks between field notes; 0 turns the naturalist off
NOTES_MIN_SECONDS = 120.0  # wall-clock floor between looks; at --tick 0 the cadence alone would be one call per reply

# --- incubation gaps (bookkeeping, not physics) --------------------------
INCUBATION_GAP = float(env("BIOTIC_INCUBATION_GAP", "600"))  # seconds away before a resume logs a gap

PALETTE_SEED = 0.61803398875
