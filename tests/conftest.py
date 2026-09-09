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

A scripted mind (FakeMind), a real HTTPError, and a clock the mutagen can be turned by
live here too.
"""

from __future__ import annotations

import email.message
import io
import urllib.error
from collections.abc import Callable
from pathlib import Path

import pytest

import bio.culture
import bio.mutagen
from bio import config
from bio.culture import FALLBACK_GENESIS, Culture
from bio.dish import Dish
from bio.membrane import admit
from bio.mind import Mind
from bio.mutagen import Mutagen
from bio.strains import Registry

FIXTURES = Path(__file__).parent / "fixtures" / "genomes"

# A daughter of the built-in founder that passes the membrane and differs from its parent.
DAUGHTER = "NAME: bud\nNOTE: divides a little sooner\n---\n" + FALLBACK_GENESIS.replace("1.0", "0.9")


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
        "PRICES_FILE": v / "prices.json",
        "SOMA": tmp_path / "soma",
    }
    for name, p in paths.items():
        monkeypatch.setattr(config, name, p)
    monkeypatch.setattr(config, "API_KEY", None)
    monkeypatch.setattr(config, "BASE_URL", "https://example.invalid/v1")  # Mind.awake -> False
    monkeypatch.setattr(config, "BUDGET_USD", 2.0)  # whatever .env says, a test's default budget is $2.00
    monkeypatch.setattr(config, "MUTAGEN_INTERVAL", 12.0)
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
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """The membrane in-process instead of in a fresh interpreter: faster, and deterministic.

    Only for tests that stay on the main thread, where Budget's alarm works. A test that
    starts the mutagen thread must not use it.
    """
    monkeypatch.setattr(bio.mutagen, "admit_isolated", admit)
    monkeypatch.setattr(bio.culture, "admit_isolated", admit)


@pytest.fixture
def make_culture() -> Callable[..., Culture]:
    """A small culture founded on FALLBACK_GENESIS, inoculated, with seed.txt written so
    Culture.load() works after save(). Built directly, so the mutagen thread starts only in
    tests that go through Culture.run(); with the mind dormant it logs once and exits. `mind`
    defaults to a dormant Mind()."""

    def _make(seed: str = "test", w: int = 24, h: int = 12, mind: Mind | None = None) -> Culture:
        config.VESSEL.mkdir(exist_ok=True)
        config.SEED_FILE.write_text(seed + "\n")
        dish = Dish(seed, w, h)
        reg = Registry(seed)
        c = Culture(seed, dish, reg, mind or Mind())
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


class FakeMind(Mind):
    """A mind with a scripted endpoint. Only `_request` is overridden; everything above it is real.

    Replies are served in order and the last one repeats; an exception instance is raised as
    urlopen would raise it. Each chat reply carries `usage` and, when `cost` is given, the
    endpoint's own figure. `/models` serves `models` verbatim, or one priced row for this model.
    """

    def __init__(
        self,
        replies: list | None = None,
        price: tuple[str, str] = ("0.000005", "0.000005"),
        usage: tuple[int, int] = (1000, 1000),
        budget_usd: float | None = 2.0,
        cost=None,
        models: list[dict] | None = None,
    ):
        super().__init__(model="test/model", budget_usd=budget_usd)
        self.key = "test"
        self.base = "https://mind.invalid/v1"
        self.replies = list(replies or [])
        self.price_rows = price
        self.usage = usage
        self.cost = cost
        self.models_payload = models
        self.chat_requests = 0
        self.models_requests = 0
        self.events: list[dict] = []
        self.log = self._record

    def _record(self, kind: str, msg: str, **data) -> None:
        self.events.append({"kind": kind, "msg": msg, **data})

    def _request(self, path: str, body: dict | None = None, timeout: float = 120) -> dict:
        if path == "/models":
            self.models_requests += 1
            if self.models_payload is not None:
                return {"data": self.models_payload}
            p, c = self.price_rows
            return {"data": [{"id": self.model, "pricing": {"prompt": p, "completion": c}}]}
        if path == "/chat/completions":
            self.chat_requests += 1
            reply = self.replies.pop(0) if len(self.replies) > 1 else (self.replies[0] if self.replies else DAUGHTER)
            if isinstance(reply, BaseException):
                raise reply
            pt, ct = self.usage
            usage: dict = {"prompt_tokens": pt, "completion_tokens": ct}
            if self.cost is not None:
                usage["cost"] = self.cost
            return {"choices": [{"message": {"content": reply}}], "usage": usage}
        raise AssertionError(f"unexpected request: {path}")


def http_error(code: int, retry_after: str | None = None, body: bytes = b'{"error":"x"}') -> urllib.error.HTTPError:
    """A real HTTPError, with headers and a body, as urlopen would raise it."""
    hdrs = email.message.Message()
    if retry_after is not None:
        hdrs["Retry-After"] = retry_after
    return urllib.error.HTTPError("https://mind.invalid/v1/chat/completions", code, "error", hdrs, io.BytesIO(body))


class Clock:
    """A clock a test turns by hand. Installed as Mutagen.clock."""

    def __init__(self, now: float = 0.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def mutagen(clock: Clock) -> Callable[[Mind], Mutagen]:
    """A factory: a mutagen on the given mind, run by `clock`, that knows one strain `f` and is
    never started as a thread. Its events land in mind.events."""

    def make(mind: Mind) -> Mutagen:
        m = Mutagen(mind, "test", mind.log)
        m.clock = clock
        m.know("f", "founder", FALLBACK_GENESIS)
        m.context = {"census": {"f": 5}}
        return m

    return make
