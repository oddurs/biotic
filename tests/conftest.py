"""Fixtures shared by the suite.

Every test runs against a vessel under tmp_path, with a dormant mind and the network
unreachable, so nothing a test does can touch the repository's culture or spend from a key.

Two more rules hold for every test in this directory:

1. Everything runs on pytest's main thread. The cell time budget is a SIGALRM timer and
   only the main thread receives it, so never step a dish or call `admit()` from a thread.
   `admit_isolated()` is the one membrane call that is safe anywhere: it runs in a child
   interpreter.
2. Nothing reads the real `soma/`. The membrane's positive control is the ten fossils in
   tests/fixtures/genomes/, copied verbatim from the first "tide" run (qwen/qwen3-coder,
   2026-09-08); `fixture_genomes()` below lists them.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from bio import config
from bio.culture import FALLBACK_GENESIS, Culture
from bio.dish import Dish
from bio.mind import Mind
from bio.strains import Registry

FIXTURES = Path(__file__).parent / "fixtures" / "genomes"


def _no_network(*args, **kwargs):
    raise AssertionError("a test reached for the network")


@pytest.fixture(autouse=True)
def vessel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every path the culture writes at tmp_path and put the mind to sleep.

    Modules read config.<NAME> at call time, so patching the module attributes is enough;
    the mtime assertion at teardown catches any future import-time binding that would
    write the repository's own growth curve.
    """
    v = tmp_path / "vessel"
    v.mkdir()
    paths = {
        "VESSEL": v,
        "INBOX": v / "inbox",
        "SEED_FILE": v / "seed.txt",
        "GENESIS": v / "genesis.py",
        "DISH_FILE": v / "dish.json",
        "STRAINS_FILE": v / "strains.json",
        "EVENTS": v / "events.jsonl",
        "CURVE": v / "curve.csv",
        "WHISPERS": v / "whispers.md",
        "SOMA": tmp_path / "soma",
    }
    for name, p in paths.items():
        monkeypatch.setattr(config, name, p)
    monkeypatch.setattr(config, "API_KEY", None)
    monkeypatch.setattr(config, "BASE_URL", "https://example.invalid/v1")  # Mind.awake -> False
    monkeypatch.setattr("urllib.request.urlopen", _no_network)
    real = config.ROOT / "vessel" / "curve.csv"
    before = real.stat().st_mtime_ns if real.exists() else None
    yield v
    after = real.stat().st_mtime_ns if real.exists() else None
    assert before == after, "a test wrote the repository's vessel/curve.csv"


@pytest.fixture(autouse=True)
def lenient_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """A quarter of a second per live() call instead of four milliseconds.

    A legitimate genome takes microseconds, so this costs nothing; what it removes is the
    one flake vector, a stalled runner lysing a founder cell mid-test, which would shift a
    trajectory and break determinism together. `Budget` reads the constant at call time,
    so patching it is enough. Tests about the budget itself set a tight one.
    """
    monkeypatch.setattr(config, "CELL_TIME_BUDGET", 0.25)


@pytest.fixture
def make_culture() -> Callable[..., Culture]:
    """A small culture founded on FALLBACK_GENESIS, inoculated, with seed.txt written so
    Culture.load() works after save(). Built directly, so the mutagen thread starts only in
    tests that go through Culture.run(); with the mind dormant it logs once and exits."""

    def _make(seed: str = "test", w: int = 24, h: int = 12) -> Culture:
        config.VESSEL.mkdir(exist_ok=True)
        config.SEED_FILE.write_text(seed + "\n")
        dish = Dish(seed, w, h)
        reg = Registry(seed)
        c = Culture(seed, dish, reg, Mind())
        s = reg.new(FALLBACK_GENESIS, None, 0, "founder", "")
        dish.register(s.id, FALLBACK_GENESIS)
        dish.inoculate(s.id)
        c.mutagen.know(s.id, s.name, s.source)
        return c

    return _make


def fixture_genomes() -> list[tuple[str, str]]:
    """(stem, source) for every fossil in tests/fixtures/genomes, sorted by name."""
    return [(p.stem, p.read_text()) for p in sorted(FIXTURES.glob("*.py"))]


def make_dish(
    seed: str = "test",
    w: int = 24,
    h: int = 12,
    replenish: float | None = None,
    genome: str = FALLBACK_GENESIS,
    n: int = config.INOCULUM,
) -> Dish:
    """A small dish inoculated with one strain, "f"."""
    d = Dish(seed, w, h)
    d.register("f", genome)
    d.inoculate("f", n)
    if replenish is not None:
        d.replenish = replenish
    return d


def dish_state(d: Dish) -> tuple:
    """Everything that determines the dish's future, as one comparable value."""
    cells = sorted(
        (c.x, c.y, c.strain, c.energy, c.age, c.born, tuple(sorted(c.memory.items()))) for c in d.cells.values()
    )
    return (
        d.tick,
        cells,
        d.nutrient,
        d.pheromone,
        d.rng.getstate(),
        d.births,
        dict(d.deaths),
        list(d.history),
        dict(d.genomes),
        d.replenish,
    )
