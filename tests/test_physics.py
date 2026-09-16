"""The dish's physics under the founder: growth phases, carrying capacity, determinism.

Everything runs on a 24×12 dish (232 tiles) with seed "test". These are regression pins
on one seeded trajectory, not statistical estimates; the only analytic claims are the
carrying-capacity ceiling and the death ledger. A seeded trajectory is exact, so the bands
sit close around the measured values, and what they guard was measured by retuning one
constant at a time and re-evaluating the assertions:

- The stationary mean is pinned to 0.52 K within 12%. That is the basal share of the
  founder's intake, so it moves with MOVE_COST (0.0125: 0.74 K; 0.02: 0.60 K; 0.03:
  0.45 K; 0.05: 0.42 K) and with BASAL_COST (0.015: 0.60 K), and with little else.
- The min/max bands and the modal phase pin the flatness of the tail. They trip when the
  founder can no longer keep up with itself: EAT_RATE at 0.045 or below, BASAL_COST at
  0.012 or above (and at 0.007), a founder that eats a barer tile or divides later.
- The two-replenish ratio pins linear scaling with the feed, within 10%.

They do not see NECROMASS, CORPSE_NUTRIENT or DIFFUSION at any value tried (0 to twice the
default), EAT_RATE above 0.06, or BASAL_COST at 0.008: the founder eats its tile bare
before the rate limits it, and the corpse and diffusion terms move less energy per tick
than one cell's basal cost. A retune of those constants is not covered here.
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
    the rest leaves with corpses, so it holds about half of K: mean 30.2 = 0.52 K, the
    lowest sample 0.76 and the highest 1.16 of the mean, and 687 of the 1000 ticks reading
    stationary. K is the ceiling, not the centre; the bands are that measurement with room
    for nothing but a deliberate retune (see the module docstring for which ones they see)."""
    tail, phases = _stationary_tail(0.0025)
    K = 0.0025 * Dish("test", 24, 12).tiles / config.BASAL_COST  # 58
    mean = sum(tail) / len(tail)
    assert 0.46 * K <= mean <= 0.58 * K
    assert min(tail) >= 0.7 * mean
    assert max(tail) <= 1.3 * mean
    assert all(tail)
    assert max(phases, key=phases.get) == "stationary"  # the curve reads as stationary most of the time


def test_carrying_capacity_scales_with_replenish():
    """Twice the feed, twice the population: 2.01 measured."""
    a, _ = _stationary_tail(0.0025)
    b, _ = _stationary_tail(0.005)
    ratio = (sum(b) / len(b)) / (sum(a) / len(a))
    assert 1.8 <= ratio <= 2.2


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
