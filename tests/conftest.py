"""Fixtures shared by the suite.

Every test runs against a vessel under tmp_path, with a dormant mind and the network
unreachable, so nothing a test does can touch the repository's culture or spend from a key.
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
