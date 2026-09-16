"""Constants and environment. The physics of the dish live here."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOMA = ROOT / "soma"
VESSEL = ROOT / "vessel"
INBOX = VESSEL / "inbox"

SEED_FILE = VESSEL / "seed.txt"
GENESIS = VESSEL / "genesis.py"
DISH_FILE = VESSEL / "dish.json"
STRAINS_FILE = VESSEL / "strains.json"
EVENTS = VESSEL / "events.jsonl"
CURVE = VESSEL / "curve.csv"
WHISPERS = VESSEL / "whispers.md"
PRICES_FILE = VESSEL / "prices.json"
FIELDNOTES = VESSEL / "fieldnotes.md"  # the naturalist's notebook
FREEZER = VESSEL / "freezer"  # frozen samples of the dish and of strains; sterilize keeps it
LOCK_FILE = VESSEL / "incubator.lock"  # held (flock) while a culture runs


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
CELL_TIME_BUDGET = 0.004  # seconds a single live() may take before lysis
GENOME_MAX_CHARS = 2400
MEMORY_MAX_CHARS = 2048  # a cell's memory as plain JSON, after every tick; more bursts the cell
MEMORY_MAX_DEPTH = 16  # how deep lists, tuples and dicts may nest inside it
INOCULUM = 5  # cells placed at seeding

# --- the freezer (bookkeeping, not physics) ------------------------------
FREEZE_EVERY = int(env("BIOTIC_FREEZE_EVERY", "2000"))  # ticks between automatic samples; 0 disables
REVIVE_WATCH = 300  # ticks a revived strain is watched before the log says whether it took

# --- the naturalist (an observer; bookkeeping, not physics) ---------------
NOTES_EVERY = int(env("BIOTIC_NOTES_EVERY", "600"))  # ticks between field notes; 0 turns the naturalist off
NOTES_MIN_SECONDS = 120.0  # wall-clock floor between looks; at --tick 0 the cadence alone would be one call per reply

PALETTE_SEED = 0.61803398875
