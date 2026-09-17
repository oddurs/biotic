"""Predation: the `lyse` feature (cairn 0012; docs/predation.md).

One acceptance criterion per section. Every test is deterministic (fixed dish seeds, or a
hand-seeded RNG for the sigmoid roll), runs on the main thread, and never touches the network
or a real mind. The membrane's SIGALRM budget only reaches the main thread, so `admit()` and
`dish.step()` are called here directly, never from a thread.
"""

from __future__ import annotations

import io
import json
import random

import pytest
from rich.console import Console

from bio import config, curve, plot, prompts
from bio.__main__ import main
from bio.culture import FALLBACK_GENESIS, Culture
from bio.dish import Dish
from bio.membrane import admit
from bio.mind import Mind

# A genome that lyses the most energetic non-kin neighbour when one is near (me.threat marks it),
# and otherwise divides, eats or rests. It reads me.threat, so admitting it proves the membrane's
# stand-in exposes the attribute (bio/membrane.py::_FakeMe).
LYSER = """\
def live(me):
    top = -1
    best = 0.0
    for d in range(8):
        if me.threat[d] > best:
            best = me.threat[d]
            top = d
    if top >= 0:
        return ("lyse", top)
    if me.energy > 1.0:
        return "divide"
    if me.here > 0.04:
        return "eat"
    return "rest"
"""

# A cell that never attacks: the built-in founder. Its energy is the prey the hunter reads as threat.
PREY = FALLBACK_GENESIS


def _render(renderable, width: int = 80) -> list[str]:
    console = Console(file=io.StringIO(), width=width, force_terminal=False)
    console.print(renderable)
    return console.file.getvalue().splitlines()


def _mixed_dish(seed: str, *, feature: bool = True) -> tuple[Dish, int]:
    """A dish of hunters and prey interleaved by parity near the centre, so every hunter has prey
    orthogonally adjacent. Hunters start rich (1.8), prey poor (0.3), so the sigmoid favours the
    burst. Returns the dish and the inoculum (cells actually placed)."""
    d = Dish(seed, width=24, height=12)
    d.features["lyse"] = feature
    d.register("hunter", LYSER)
    d.register("prey", PREY)
    cx, cy = d.center()
    inoculum = 0
    for dy in (-1, 0, 1):
        for dx in range(-3, 4):
            x, y = cx + dx, cy + dy
            if (x + y) % 2 == 0:
                cell = d.place(x, y, "hunter", energy=1.8)
            else:
                cell = d.place(x, y, "prey", energy=0.3)
            if cell is not None:
                inoculum += 1
    return d, inoculum


# --- criterion 1: a lyser is admitted and produces `predated` deaths in a mixed dish ----------


def test_a_lyse_reading_genome_is_admitted():
    """The membrane's stand-in must expose me.threat, or a genome that reads it is refused before
    it can live. admit() runs the static gate and forty smoke rounds against _FakeMe."""
    assert admit(LYSER), admit(LYSER).reasons


def test_a_mixed_dish_with_lyse_on_produces_predated_deaths():
    d, inoculum = _mixed_dish("prey-run")
    for _ in range(20):
        d.step()
    assert d.deaths["predated"] > 0, "hunters never burst a prey neighbour"


def test_the_death_ledger_closes_with_predated_included():
    """Population is founder cells plus births minus every death cause; predated must be one of
    them for the identity to hold once predation has killed."""
    d, inoculum = _mixed_dish("prey-run")
    for _ in range(20):
        d.step()
    m = d.metrics()
    assert m["predated"] > 0
    losses = m["starved"] + m["lysed"] + m["senescent"] + m["killed"] + m["predated"]
    assert m["births"] - losses == m["population"] - inoculum


# --- criterion 2: kin are never lysed ---------------------------------------------------------


def test_a_monoculture_of_lysers_never_predates():
    """In a monoculture me.threat is all zeros (every neighbour is kin), so the lyser never even
    attempts a burst — kin immunity, upstream of the roll."""
    d = Dish("mono", width=24, height=12)
    d.features["lyse"] = True
    d.register("h", LYSER)
    d.inoculate("h", n=5)
    for _ in range(30):
        d.step()
    assert d.deaths["predated"] == 0


def test_lyse_against_kin_is_a_free_no_op():
    """A cell told to lyse a neighbour of its own strain returns before the cost: both cells live,
    neither loses energy, and no roll is made."""
    d = Dish("kin", width=24, height=12)
    d.features["lyse"] = True
    d.register("a", FALLBACK_GENESIS)
    cx, cy = d.center()
    attacker = d.place(cx, cy, "a", energy=1.0)
    kin = d.place(cx + 1, cy, "a", energy=0.5)  # DIRS[2] is East
    before = d.rng.getstate()
    d._apply(attacker, ("lyse", 2))
    assert attacker.energy == 1.0 and kin.energy == 0.5
    assert (cx + 1, cy) in d.cells and d.deaths["predated"] == 0
    assert d.rng.getstate() == before, "a kin no-op must not consume the roll"


def test_lyse_against_an_empty_tile_is_a_free_no_op():
    d = Dish("empty", width=24, height=12)
    d.features["lyse"] = True
    d.register("a", FALLBACK_GENESIS)
    cx, cy = d.center()
    attacker = d.place(cx, cy, "a", energy=1.0)
    before = d.rng.getstate()
    d._apply(attacker, ("lyse", 0))  # north neighbour is empty
    assert attacker.energy == 1.0 and d.deaths["predated"] == 0
    assert d.rng.getstate() == before


# --- the sigmoid: the win and the loss branch, with the roll pinned ---------------------------


def test_a_richer_attacker_bursts_a_weaker_non_kin_neighbour():
    d = Dish("win", width=24, height=12)
    d.features["lyse"] = True
    d.register("a", FALLBACK_GENESIS)
    d.register("b", FALLBACK_GENESIS)
    d.rng = random.Random(1)  # first draw 0.1344, below p ≈ 0.98
    cx, cy = d.center()
    attacker = d.place(cx, cy, "a", energy=1.8)
    d.place(cx + 1, cy, "b", energy=0.2)
    d._apply(attacker, ("lyse", 2))
    assert (cx + 1, cy) not in d.cells, "the weaker neighbour should have burst"
    assert d.deaths["predated"] == 1
    assert attacker.energy == pytest.approx(1.8 - config.LYSE_COST + config.LYSE_YIELD * 0.2)


def test_a_failed_attack_costs_the_cost_and_the_recoil():
    d = Dish("loss", width=24, height=12)
    d.features["lyse"] = True
    d.register("a", FALLBACK_GENESIS)
    d.register("b", FALLBACK_GENESIS)
    d.rng = random.Random(0)  # first draw 0.8444, above p ≈ 0.039 for a weak attacker
    cx, cy = d.center()
    attacker = d.place(cx, cy, "a", energy=0.2)
    d.place(cx + 1, cy, "b", energy=1.8)
    d._apply(attacker, ("lyse", 2))
    assert (cx + 1, cy) in d.cells, "the stronger neighbour should have survived"
    assert d.deaths["predated"] == 0
    assert attacker.energy == pytest.approx(0.2 - config.LYSE_COST - config.LYSE_RECOIL)


# --- feature off: old dishes are byte-identical -----------------------------------------------


def test_lyse_with_the_feature_off_is_a_no_op_that_does_not_touch_the_rng():
    """A dish that never enabled predation runs a lyse action as an inert no-op, and its RNG stream
    is untouched — so a dish that predates this feature follows the exact trajectory it always did."""
    d = Dish("off", width=24, height=12)  # feature off by default
    assert d.features == {"lyse": False}
    d.register("a", FALLBACK_GENESIS)
    d.register("b", FALLBACK_GENESIS)
    cx, cy = d.center()
    attacker = d.place(cx, cy, "a", energy=1.5)
    victim = d.place(cx + 1, cy, "b", energy=0.3)
    before = d.rng.getstate()
    d._apply(attacker, ("lyse", 2))
    assert attacker.energy == 1.5 and victim.energy == 0.3
    assert (cx + 1, cy) in d.cells and d.deaths["predated"] == 0
    assert d.rng.getstate() == before


def test_a_lyse_returning_dish_with_the_feature_off_never_predates():
    d, _ = _mixed_dish("prey-run", feature=False)
    for _ in range(20):
        d.step()
    assert d.deaths["predated"] == 0


# --- criterion 3: enabling mid-run is logged and marked on the curve ---------------------------


def test_enabling_lyse_mid_run_is_logged_and_marked_on_the_curve(make_culture):
    c = make_culture()
    for _ in range(10):
        c.step()
    tick = c.dish.tick
    msg = c.drop("feature", name="lyse")
    assert msg == "predation (lyse) enabled"
    assert c.dish.features["lyse"] is True
    drops = [e for e in c.events if e["kind"] == "drop" and e.get("what") == "feature lyse"]
    assert drops and drops[-1]["tick"] == tick and drops[-1]["feature"] == "lyse"
    marks = plot.markers(curve.events())  # reads vessel/events.jsonl, written by log()
    lyse_marks = [m for m in marks if m.kind == "drop" and m.label == "feature lyse"]
    assert lyse_marks and lyse_marks[-1].tick == tick


def test_enabling_lyse_twice_is_an_idempotent_no_op(make_culture):
    c = make_culture()
    c.drop("feature", name="lyse")
    msg = c.drop("feature", name="lyse")
    assert msg == "predation (lyse) was already enabled"
    already = [e for e in c.events if e["kind"] == "drop" and e.get("already")]
    assert already and already[-1]["feature"] == "lyse"


def test_the_inbox_enables_a_feature_from_a_drop_request(make_culture):
    """`biotic drop feature lyse` queues a request the next run drains; the inbox route must pass
    the feature name through to enable_feature."""
    c = make_culture()
    config.INBOX.mkdir(parents=True, exist_ok=True)
    (config.INBOX / "1.json").write_text(json.dumps({"drop": "feature", "feature": "lyse"}))
    c._inbox()
    assert c.dish.features["lyse"] is True


# --- criterion 4: vitals show predation deaths; the census format is untouched -----------------


def test_vitals_show_predation_deaths_when_present(make_culture):
    c = make_culture()
    snap = c.snapshot()
    snap["deaths"] = {"starved": 2, "lysed": 1, "senescent": 0, "killed": 3, "predated": 4}
    lines = _render(vitals_line(c, snap))
    deaths = next(ln for ln in lines if "starved" in ln)
    assert "4 predated" in deaths and "3 killed" in deaths


def test_vitals_omit_the_predation_clause_when_there_are_none(make_culture):
    c = make_culture()
    snap = c.snapshot()
    snap["deaths"] = {"starved": 2, "lysed": 1, "senescent": 0, "killed": 0, "predated": 0}
    lines = _render(vitals_line(c, snap))
    deaths = next(ln for ln in lines if "starved" in ln)
    assert "predated" not in deaths and "killed" not in deaths


def vitals_line(c, snap):
    from bio.tui import vitals

    return vitals(c, snap)


def test_status_shows_predated_in_the_deaths_dict(make_culture, capsys):
    c = make_culture()
    c.dish.deaths["predated"] = 5
    c.save()
    main(["status"])
    out = capsys.readouterr().out
    assert "'predated': 5" in out


# --- prompt builders: the clause appears only when the feature is on --------------------------


def test_prompt_builders_equal_the_constants_with_no_features():
    assert prompts.genesis_system({}) == prompts.GENESIS_SYSTEM
    assert prompts.mutagen_system({}) == prompts.MUTAGEN_SYSTEM
    assert prompts.genesis_system() == prompts.GENESIS_SYSTEM
    assert prompts.mutagen_system(None) == prompts.MUTAGEN_SYSTEM
    assert prompts.cell_api({}) == prompts.CELL_API
    assert prompts.cell_api(None) == prompts.CELL_API


def test_the_lyse_clause_is_present_only_when_lyse_is_on():
    base = prompts.cell_api({"lyse": False})
    assert base == prompts.CELL_API
    assert "me.threat" not in base and "lyse" not in base and "predated" not in base
    on = prompts.cell_api({"lyse": True})
    assert "me.threat" in on and '("lyse", d)' in on and "predated" in on
    assert prompts.mutagen_system({"lyse": True}) != prompts.MUTAGEN_SYSTEM
    assert "me.threat" in prompts.mutagen_system({"lyse": True})
    assert "me.threat" in prompts.genesis_system({"lyse": True})


# --- persistence: features round-trip, and an old dish thaws to all-off ------------------------


def test_features_round_trip_through_to_dict():
    d = Dish("rt", width=24, height=12)
    d.features["lyse"] = True
    clone = Dish.from_dict(d.to_dict())
    assert clone.features == {"lyse": True}


def test_a_dish_without_a_features_key_thaws_to_all_off():
    d = Dish("rt", width=24, height=12)
    d.features["lyse"] = True
    blob = d.to_dict()
    del blob["features"]
    clone = Dish.from_dict(blob)
    assert clone.features == {"lyse": False}


# --- seeding a dish with the feature on --------------------------------------------------------


def test_germinate_with_a_feature_turns_it_on_and_marks_tick_zero(vessel):
    c = Culture.germinate("microbe", Mind(), features=["lyse"])
    assert c.dish.features["lyse"] is True
    drops = [e for e in c.events if e["kind"] == "drop" and e.get("what") == "feature lyse"]
    assert drops and drops[0]["tick"] == 0
    reloaded = Culture.load(Mind())
    assert reloaded.dish.features["lyse"] is True


def test_germinate_rejects_an_unknown_feature_before_autoclaving(culture):
    """Validation runs before sterilize(), so a typo never destroys an existing dish."""
    assert config.DISH_FILE.exists()
    with pytest.raises(ValueError, match="unknown feature: bogus"):
        Culture.germinate("test", Mind(), fresh=True, features=["bogus"])
    assert config.DISH_FILE.exists(), "the existing dish was autoclaved on a bad feature name"


def test_cli_seed_with_lyse_enables_the_feature(vessel, capsys):
    main(["seed", "microbe", "--with", "lyse"])
    capsys.readouterr()
    c = Culture.load(Mind())
    assert c.dish.features["lyse"] is True


def test_cli_seed_with_an_unknown_feature_exits(vessel):
    with pytest.raises(SystemExit):
        main(["seed", "microbe", "--with", "nope"])
    assert not config.DISH_FILE.exists()
