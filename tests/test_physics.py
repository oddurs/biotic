"""The dish's physics under the founder: growth phases, carrying capacity, determinism.

Everything runs on a 24×12 dish (232 tiles) with seed "test". These are regression
pins on one seeded trajectory, not statistical estimates; the only analytic claims are
the carrying-capacity ceiling and the death ledger. The numeric bands are a deliberate
floor: retuning BASAL_COST, MOVE_COST, EAT_RATE, NECROMASS, CORPSE_NUTRIENT, DIFFUSION
or the founder will move them, and the point of these tests is to say so when it happens.
"""

from __future__ import annotations

import functools

from conftest import dish_state, make_dish

from bio import config
from bio.dish import Dish


def test_founding_strain_grows_from_the_inoculum():
    d = make_dish()
    assert len(d.cells) == config.INOCULUM
    for _ in range(80):
        d.step()
    assert d.tick == 80
    assert d.births > 0
    assert len(d.cells) > config.INOCULUM
    assert d.census() == {"f": len(d.cells)}


def test_closed_dish_runs_lag_log_death_to_sterile():
    """With replenish=0 the founder blooms, exhausts the agar and starves out;
    every death is starvation and every cell that ever lived is accounted for."""
    d = make_dish(replenish=0.0)
    first: dict[str, int] = {}
    while d.tick < 600:
        d.step()
        first.setdefault(d.phase(), d.tick)
        if not d.cells:
            break
    assert first["lag"] < first["log"] < first["death"]
    assert d.phase() == "sterile"
    assert not d.cells
    assert d.tick < 600
    assert d.deaths["starved"] == d.births + config.INOCULUM
    assert d.deaths["lysed"] == 0
    assert d.deaths["senescent"] == 0


@functools.cache
def _stationary_tail(replenish: float) -> tuple[tuple[int, ...], dict[str, int]]:
    """Ticks 1500 to 2500 of a replenished dish: the population every 10 ticks,
    and how many ticks the curve read as each phase."""
    d = make_dish(replenish=replenish)
    tail: list[int] = []
    phases: dict[str, int] = {}
    while d.tick < 2500:
        d.step()
        phase = d.phase()
        assert d.tick <= 100 or phase != "sterile"
        if d.tick > 1500:
            phases[phase] = phases.get(phase, 0) + 1
        if d.tick >= 1500 and d.tick % 10 == 0:
            tail.append(len(d.cells))
    return tuple(tail), phases


def test_replenished_dish_holds_a_stationary_population():
    """Energy conservation puts a ceiling on the population: K = replenish × tiles / BASAL_COST
    is what the agar can feed if every unit of energy went to staying alive. Measured over
    the tail, the founder spends 51% of its intake on basal cost and 46% on moving, and
    the rest leaves with corpses, so it holds about half of K (0.53 K). The band below is
    that measurement with room to breathe, not an estimate."""
    tail, phases = _stationary_tail(0.0025)
    K = 0.0025 * Dish("test", 24, 12).tiles / config.BASAL_COST  # 58
    mean = sum(tail) / len(tail)
    assert 0.35 * K <= mean <= K
    assert min(tail) >= 0.6 * mean
    assert max(tail) <= 1.4 * mean
    assert all(tail)
    assert max(phases, key=phases.get) == "stationary"  # the curve reads as stationary most of the time


def test_carrying_capacity_scales_with_replenish():
    a, _ = _stationary_tail(0.0025)
    b, _ = _stationary_tail(0.005)
    ratio = (sum(b) / len(b)) / (sum(a) / len(a))
    assert 1.5 <= ratio <= 2.5


def test_dish_is_deterministic_under_a_seed():
    a, b = make_dish(), make_dish()
    for _ in range(500):
        a.step()
        b.step()
    assert dish_state(a) == dish_state(b)
    # and the comparison is not vacuous: another seed gives another dish
    c = make_dish(seed="test2")
    for _ in range(500):
        c.step()
    assert (c.census(), c.nutrient) != (a.census(), a.nutrient)
