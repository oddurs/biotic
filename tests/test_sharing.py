"""Sharing: the `give` feature (cairn 0013; docs/sharing.md).

One acceptance criterion per section. Every test is deterministic (fixed dish seeds, no roll is
ever made by a gift), runs on the main thread, and never touches the network or a real mind. The
membrane's SIGALRM budget only reaches the main thread, so `admit()` and `dish.step()` are called
here directly, never from a thread.
"""

from __future__ import annotations

import io
import random

import pytest
from rich.console import Console

from bio import config, curve, plot, prompts
from bio.__main__ import main
from bio.culture import Culture
from bio.dish import Dish, Me
from bio.membrane import _FakeMe, admit
from bio.mind import Mind

REST = "def live(me):\n    return 'rest'\n"

# A giver: hand energy to the hungriest kin neighbour when one is below 0.3 (me.kin marks kin,
# me.neighbor_energy reads its energy), otherwise rest. It reads me.neighbor_energy, so admitting
# it proves the membrane's stand-in exposes the attribute (bio/membrane.py::_FakeMe). It never
# eats, moves or divides: what it does to the dish is give, and nothing else.
GIVER = """\
def live(me):
    best = -1
    lo = 0.3
    for d in range(8):
        if me.kin[d] and 0.0 < me.neighbor_energy[d] < lo:
            lo = me.neighbor_energy[d]
            best = d
    if best >= 0:
        return ("give", best, 0.1)
    return "rest"
"""

# The same genome with the transfer removed: it scans exactly as the giver does and then rests.
# The one difference between the two dishes is the gift itself.
CONTROL = GIVER.replace('return ("give", best, 0.1)', 'return "rest"')


def _render(renderable, width: int = 80) -> list[str]:
    console = Console(file=io.StringIO(), width=width, force_terminal=False)
    console.print(renderable)
    return console.file.getvalue().splitlines()


def _dish(seed: str = "give", *, feature: bool = True) -> Dish:
    """A 24x12 dish with sharing on and two strains registered: `giver` and `other` (a stranger)."""
    d = Dish(seed, width=24, height=12)
    d.features["give"] = feature
    d.register("giver", REST)
    d.register("other", REST)
    return d


# --- criterion 1: energy is conserved minus the documented loss -------------------------------


def test_a_transfer_conserves_energy_minus_the_documented_heat():
    """The giver loses `amount`, the neighbour gains GIVE_EFFICIENCY × amount, and the gap is the
    heat: the only energy that leaves the pair. Both energies stay well below MAX_ENERGY so nothing
    is clamped inside the claim."""
    d = _dish()
    cx, cy = d.center()
    giver = d.place(cx, cy, "giver", energy=1.0)
    recip = d.place(cx + 1, cy, "other", energy=0.3)  # DIRS[2] is East
    before = giver.energy + recip.energy
    roll = d.rng.getstate()
    d._apply(giver, ("give", (2, 0.4)))
    assert giver.energy == pytest.approx(0.6)
    assert recip.energy == pytest.approx(0.3 + 0.4 * config.GIVE_EFFICIENCY)
    heat = 0.4 * (1 - config.GIVE_EFFICIENCY)
    assert giver.energy + recip.energy == pytest.approx(before - heat)
    assert d.given == pytest.approx(0.4)  # gross: what left the giver
    assert d.received == pytest.approx(0.4 * config.GIVE_EFFICIENCY)  # net: what reached the recipient
    assert d.given - d.received == pytest.approx(heat)  # the difference is exactly the heat
    assert d.rng.getstate() == roll, "a gift makes no roll"


def test_a_gift_never_drops_the_giver_below_the_reserve():
    """Ask for more than the giver can spare and it gives only down to GIVE_RESERVE; the recipient
    gains the efficiency-scaled fraction of what was actually given, not of what was asked."""
    d = _dish()
    cx, cy = d.center()
    giver = d.place(cx, cy, "giver", energy=0.2)
    recip = d.place(cx + 1, cy, "other", energy=0.1)
    d._apply(giver, ("give", (2, 1.0)))  # asks a full unit; only 0.2 - reserve is sparable
    sparable = 0.2 - config.GIVE_RESERVE
    assert giver.energy == pytest.approx(config.GIVE_RESERVE)
    assert recip.energy == pytest.approx(0.1 + sparable * config.GIVE_EFFICIENCY)
    assert d.given == pytest.approx(sparable)


def test_a_giver_with_nothing_to_spare_is_a_free_no_op():
    """At or below the reserve there is nothing to give: the action does nothing, costs nothing,
    and makes no roll — neither cell moves an electron."""
    d = _dish()
    cx, cy = d.center()
    giver = d.place(cx, cy, "giver", energy=0.04)  # below GIVE_RESERVE (0.05)
    recip = d.place(cx + 1, cy, "other", energy=0.5)
    roll = d.rng.getstate()
    d._apply(giver, ("give", (2, 0.1)))
    assert giver.energy == 0.04 and recip.energy == 0.5
    assert d.given == 0.0 and d.received == 0.0
    assert d.rng.getstate() == roll


def test_the_counters_track_gross_given_and_net_received_over_many_gifts():
    """`given` accumulates the gross energy that leaves givers and `received` the net that arrives;
    their gap is the heat, and it grows with every gift."""
    d = _dish()
    cx, cy = d.center()
    giver = d.place(cx, cy, "giver", energy=2.0)
    recip = d.place(cx + 1, cy, "other", energy=0.0)
    for _ in range(5):
        d._apply(giver, ("give", (2, 0.1)))
    assert d.given == pytest.approx(0.5)
    assert d.received == pytest.approx(0.5 * config.GIVE_EFFICIENCY)
    assert d.given - d.received == pytest.approx(0.5 * (1 - config.GIVE_EFFICIENCY))
    assert recip.energy == pytest.approx(d.received)  # the whole net landed on the one recipient


# --- both kin and non-kin receive: giving to a stranger is what allows cheating ---------------


def test_both_kin_and_non_kin_receive_a_gift():
    """A gift crosses strain lines. There is no kin check on `give` (unlike `lyse`): a stranger
    receives exactly as a sister does, which is what makes a cheating strain possible."""
    for strain in ("giver", "other"):  # a sister, then a stranger
        d = _dish()
        cx, cy = d.center()
        giver = d.place(cx, cy, "giver", energy=1.0)
        recip = d.place(cx + 1, cy, strain, energy=0.2)
        d._apply(giver, ("give", (2, 0.3)))
        assert recip.energy == pytest.approx(0.2 + 0.3 * config.GIVE_EFFICIENCY), strain
        assert d.given == pytest.approx(0.3), strain


def test_giving_to_an_empty_tile_or_the_glass_wall_is_a_free_no_op():
    d = _dish()
    cx, cy = d.center()
    giver = d.place(cx, cy, "giver", energy=1.0)
    roll = d.rng.getstate()
    d._apply(giver, ("give", (0, 0.4)))  # north neighbour is empty
    assert giver.energy == 1.0 and d.given == 0.0
    assert d.rng.getstate() == roll
    # a cell against the glass: a direction that leaves the dish is inside() False, so target is None
    edge = next((x, y) for y in range(d.h) for x in range(d.w) if d.inside(x, y) and not d.inside(x, y - 1))
    ec = d.place(*edge, "giver", energy=1.0)
    d._apply(ec, ("give", (0, 0.4)))  # north is off the agar (glass)
    assert ec.energy == 1.0 and d.given == 0.0


# --- the perception: me.neighbor_energy includes kin, where me.threat does not -----------------


def test_me_neighbor_energy_includes_kin_and_zeroes_empty():
    """The reason sharing adds a perception rather than reusing me.threat: threat zeroes a kin
    neighbour (it is only for predation), so it cannot tell a giver its sister is starving.
    me.neighbor_energy carries every occupied neighbour's energy, kin included, 0.0 for empty."""
    d = _dish()
    cx, cy = d.center()
    center = d.place(cx, cy, "giver", energy=1.0)
    d.place(cx, cy - 1, "giver", energy=0.7)  # N (DIRS[0]): kin
    d.place(cx + 1, cy, "other", energy=0.4)  # E (DIRS[2]): a stranger
    me = Me(center, d)
    assert me.kin[0] is True
    assert me.neighbor_energy[0] == 0.7  # kin energy is visible …
    assert me.threat[0] == 0.0  # … where threat hides it
    assert me.neighbor_energy[2] == 0.4  # a stranger's energy, on both
    assert me.threat[2] == 0.4
    assert me.neighbor_energy[4] == 0.0  # S is empty


def test_the_smoke_stand_in_presents_neighbor_energy_on_the_energy_scale():
    """me.neighbor_energy holds a neighbour cell's energy (0..MAX_ENERGY), kin included. The
    stand-in must span that interval and light up kin tiles, or a genome whose give branch is
    gated on an energy-scale threshold over a kin neighbour is admitted but never exercised.
    Pooled over 200 seeds so the claim does not depend on any one stand-in's random tiles."""
    hi = 0.0
    over = 0
    kin_nonzero = 0
    for seed in range(200):
        me = _FakeMe(random.Random(seed), 0)
        hi = max(hi, max(me.neighbor_energy))
        over += sum(1 for v in me.neighbor_energy if v > config.MAX_ENERGY)
        kin_nonzero += sum(1 for d in range(8) if me.kin[d] and me.neighbor_energy[d] > 0.0)
    assert hi > 1.0, "fake neighbour energy never clears the nutrient ceiling; it is not on the energy scale"
    assert over == 0, "fake neighbour energy exceeds a live neighbour's ceiling"
    assert kin_nonzero >= 1, "no kin tile ever carries energy; a kin-giving branch is never exercised"


def test_a_give_reading_genome_is_admitted():
    """A genome that reads me.neighbor_energy and returns ("give", d, x) passes the static gate
    and forty smoke rounds. If the stand-in lacked the attribute, the genome would throw and be
    refused before it could live."""
    assert admit(GIVER), admit(GIVER).reasons


# --- criterion 2: give-to-hungry-kin keeps a starving cluster alive longer than a control ------


def _starving_cluster(genome: str) -> tuple[Dish, int]:
    """A closed dish (no replenishment) with a single-strain line at the centre: rich cells at
    1.5 alternating with poor kin at 0.12, so every poor cell has a rich sister beside it. The
    poor cells cannot feed themselves — nothing eats — so without help they starve on basal cost
    alone. Returns the dish and the inoculum."""
    d = Dish("cluster", width=24, height=12)
    d.replenish = 0.0
    d.features["give"] = True
    d.register("s", genome)
    cx, cy = d.center()
    layout = [(-3, 1.5), (-2, 0.12), (-1, 1.5), (0, 0.12), (1, 1.5), (2, 0.12), (3, 1.5)]
    n = 0
    for dx, e in layout:
        assert d.place(cx + dx, cy, "s", energy=e) is not None
        n += 1
    return d, n


def test_giving_to_hungry_kin_outlasts_a_control():
    """Criterion 2. Two dishes from one seed: in the giver dish rich cells feed their hungry
    kin; the control scans identically and rests. K is pinned inside the redistribution window —
    after the control's poor cells have starved (they die by tick 13 on basal cost from 0.12) and
    well before any giver cell nears the reserve (the poorest giver cell holds ~0.33 at K=15).
    Both dishes shuffle their cells with the same seeded RNG and no gift touches it, so the two
    trajectories are comparable tick for tick; the only difference is the transfer."""
    K = 15
    giver, ng = _starving_cluster(GIVER)
    control, nc = _starving_cluster(CONTROL)
    assert ng == nc == 7
    for _ in range(K):
        giver.step()
        control.step()
    assert control.deaths["starved"] >= 1, "the control's poor cells should have starved by now"
    assert giver.deaths["starved"] == 0, "sharing should have kept every cell alive"
    assert len(giver.cells) > len(control.cells), "the fed cluster outlives the unfed one"
    assert giver.given > 0.0 and giver.received > 0.0
    assert control.given == 0.0, "the control never gives"


def test_the_control_starves_only_because_it_does_not_share():
    """A guard on the criterion-2 setup: with sharing turned OFF, the giver genome is inert, so
    the giver dish starves exactly as the control does. The survival is the gift, not the layout."""
    off, _ = _starving_cluster(GIVER)
    off.features["give"] = False
    for _ in range(15):
        off.step()
    assert off.deaths["starved"] >= 1 and off.given == 0.0


# --- criterion 3: given/received appear in the curve columns -----------------------------------


def test_given_and_received_are_curve_columns_after_predated():
    assert curve.COLUMNS[-2:] == ("given", "received")
    assert curve.COLUMNS.index("given") == curve.COLUMNS.index("predated") + 1
    assert curve.DECIMALS["given"] == 4 and curve.DECIMALS["received"] == 4  # floats, not the int default
    assert "given" not in curve._INT and "received" not in curve._INT
    assert plot.LABELS["given"] == "energy given (cumulative)"
    assert plot.LABELS["received"] == "energy received (cumulative)"
    assert set(plot.LABELS) == set(plot.PLOTTABLE)  # every plottable column has a label


def test_a_sharing_dish_writes_given_and_received_to_the_curve(make_culture):
    """Criterion 3, end to end. A culture whose cells give writes the two columns every CADENCE
    ticks; the last row carries the running gross and net, net below gross by the heat."""
    c = make_culture()
    d = c.dish
    d.cells.clear()  # replace the founder inoculum with a giving cluster
    d.replenish = 0.0
    d.features["give"] = True
    d.register("giver", GIVER)
    cx, cy = d.center()
    for dx, e in [(-3, 1.5), (-2, 0.12), (-1, 1.5), (0, 0.12), (1, 1.5), (2, 0.12), (3, 1.5)]:
        d.place(cx + dx, cy, "giver", energy=e)
    for _ in range(curve.CADENCE):
        c.step()
    header = config.CURVE.read_text().splitlines()[0].split(",")
    assert header[-2:] == ["given", "received"]
    row = curve.read()[-1]
    assert row["tick"] == curve.CADENCE
    assert isinstance(row["given"], float) and isinstance(row["received"], float)
    assert row["given"] > 0.0
    assert 0.0 < row["received"] < row["given"]  # net below gross: the heat shows in the columns
    assert row["given"] == pytest.approx(d.given) and row["received"] == pytest.approx(d.received)


# --- feature off: a dish that never enabled sharing is untouched -------------------------------


def test_give_with_the_feature_off_is_an_inert_no_op():
    """A dish that never enabled sharing runs a give action as an inert no-op: no energy moves, no
    counter changes, and the RNG stream is untouched — so a dish that predates this feature follows
    the exact trajectory it always did."""
    d = _dish(feature=False)
    assert d.features == {"lyse": False, "give": False}
    cx, cy = d.center()
    giver = d.place(cx, cy, "giver", energy=1.0)
    recip = d.place(cx + 1, cy, "other", energy=0.3)
    roll = d.rng.getstate()
    d._apply(giver, ("give", (2, 0.4)))
    assert giver.energy == 1.0 and recip.energy == 0.3
    assert d.given == 0.0 and d.received == 0.0
    assert d.rng.getstate() == roll


# --- the prompt clause: present only when sharing is on ----------------------------------------


def test_the_give_clause_is_present_only_when_give_is_on():
    base = prompts.cell_api({"give": False})
    assert base == prompts.CELL_API
    assert "me.neighbor_energy" not in base and '("give", d, x)' not in base
    on = prompts.cell_api({"give": True})
    assert "me.neighbor_energy" in on and '("give", d, x)' in on
    assert f"{config.GIVE_RESERVE:g}" in on and f"{config.GIVE_EFFICIENCY:g}" in on
    assert prompts.mutagen_system({"give": True}) != prompts.MUTAGEN_SYSTEM
    assert "me.neighbor_energy" in prompts.mutagen_system({"give": True})
    assert "me.neighbor_energy" in prompts.genesis_system({"give": True})


def test_the_two_feature_clauses_are_independent():
    """lyse and give each add only their own clause; both on adds both, neither leaks into the
    no-feature constants."""
    lyse_only = prompts.cell_api({"lyse": True})
    assert "me.threat" in lyse_only and "me.neighbor_energy" not in lyse_only
    give_only = prompts.cell_api({"give": True})
    assert "me.neighbor_energy" in give_only and "me.threat" not in give_only
    both = prompts.cell_api({"lyse": True, "give": True})
    assert "me.threat" in both and "me.neighbor_energy" in both


# --- persistence: the counters round-trip -----------------------------------------------------


def test_given_and_received_round_trip_through_to_dict():
    d = _dish()
    d.given = 3.5
    d.received = 3.15
    clone = Dish.from_dict(d.to_dict())
    assert clone.given == 3.5 and clone.received == 3.15


def test_a_dish_without_the_sharing_keys_thaws_to_zero():
    d = _dish()
    d.given = 1.0
    d.received = 0.9
    blob = d.to_dict()
    del blob["given"]
    del blob["received"]
    clone = Dish.from_dict(blob)
    assert clone.given == 0.0 and clone.received == 0.0


# --- turning it on: seeding and mid-run --------------------------------------------------------


def test_germinate_with_give_turns_it_on_and_marks_tick_zero(vessel):
    c = Culture.germinate("microbe", Mind(), features=["give"])
    assert c.dish.features["give"] is True
    drops = [e for e in c.events if e["kind"] == "drop" and e.get("what") == "feature give"]
    assert drops and drops[0]["tick"] == 0
    reloaded = Culture.load(Mind())
    assert reloaded.dish.features["give"] is True


def test_cli_seed_with_give_enables_the_feature(vessel, capsys):
    main(["seed", "microbe", "--with", "give"])
    capsys.readouterr()
    c = Culture.load(Mind())
    assert c.dish.features["give"] is True


def test_enabling_give_mid_run_is_logged_as_sharing(make_culture):
    c = make_culture()
    for _ in range(10):
        c.step()
    tick = c.dish.tick
    msg = c.drop("feature", name="give")
    assert msg == "sharing (give) enabled"
    assert c.dish.features["give"] is True
    drops = [e for e in c.events if e["kind"] == "drop" and e.get("what") == "feature give"]
    assert drops and drops[-1]["tick"] == tick and drops[-1]["feature"] == "give"
    marks = plot.markers(curve.events())
    give_marks = [m for m in marks if m.kind == "drop" and m.label == "feature give"]
    assert give_marks and give_marks[-1].tick == tick


# --- the eyepiece: the sharing row appears once a gift has been made ---------------------------


def test_vitals_show_sharing_once_a_gift_has_been_made(make_culture):
    c = make_culture()
    snap = c.snapshot()
    snap["given"] = 1.25
    snap["received"] = 1.125
    lines = _render(_vitals(c, snap))
    row = next(ln for ln in lines if "sharing" in ln)
    assert "1.25 given" in row and "1.12 received" in row


def test_vitals_omit_sharing_before_any_gift(make_culture):
    """The row is hidden until the first gift, so a non-sharing dish (the common case) shows no
    empty sharing line — the same omit-when-none rule predation's deaths clause follows."""
    c = make_culture()
    snap = c.snapshot()
    assert snap["given"] == 0.0
    lines = _render(_vitals(c, snap))
    assert not any("sharing" in ln for ln in lines)


def _vitals(c, snap):
    from bio.tui import vitals

    return vitals(c, snap)
