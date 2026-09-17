"""Horizontal gene transfer: the `hgt` feature (cairn 0014; docs/hgt.md).

One acceptance criterion per section. Every test is deterministic (fixed seeds, a hand-seeded
RNG for the hue draw, a scripted fake mind), runs on the main thread, and never touches the
network. The four criteria are exercised on the tick clock, where a division that rolls a
mutation and a splice calls the mind synchronously; the wall-clock `(recipient, donor)` pool is
tested through direct `Mutagen` calls on a hand clock, with the thread never started.
"""

from __future__ import annotations

import random

import pytest

from bio import config, curve, prompts
from bio.__main__ import main
from bio.culture import FALLBACK_GENESIS, Culture
from bio.dish import Dish
from bio.mind import Mind
from bio.mutagen import _split
from bio.strains import Registry, _mix_hue

from .conftest import DAUGHTER, FakeMind, state

# A donor genome distinct from the recipient (the built-in founder): it follows the richest scent
# instead of the richest agar. Admitted by the membrane; what the recipient does not do, so a
# splice has a real behaviour to borrow.
DONOR_GENOME = """\
def live(me):
    free = [d for d in range(8) if not me.crowd[d]]
    if me.energy > 1.0 and free:
        return "divide"
    if me.here > 0.04:
        return "eat"
    if free:
        best = max(free, key=lambda d: me.scent[d])
        if me.scent[best] > 0.0:
            return ("move", best)
    return "rest"
"""


def _two_strain_culture(seed: str, *, adjacent: bool, hgt: bool = True, mind: Mind | None = None):
    """A dish with a recipient cell at the centre and a donor cell of another strain either
    orthogonally adjacent (a splice can find it) or five tiles away (it cannot). Both strains are
    founders known to the mutagen. Returns (culture, recipient_strain, donor_strain, recipient_cell)."""
    config.VESSEL.mkdir(exist_ok=True)
    config.SEED_FILE.write_text(seed + "\n")
    dish = Dish(seed, 24, 12)
    dish.features["hgt"] = hgt
    reg = Registry(seed)
    rec = reg.new(FALLBACK_GENESIS, None, 0, "recipient", "the built-in founder")
    don = reg.new(DONOR_GENOME, None, 0, "donor", "an unrelated neighbour")
    dish.register(rec.id, FALLBACK_GENESIS)
    dish.register(don.id, DONOR_GENOME)
    c = Culture(seed, dish, reg, mind or Mind())  # __init__ knows both: both are in dish.genomes
    cx, cy = dish.center()
    rcell = dish.place(cx, cy, rec.id, energy=1.5)
    dish.place(cx + 1, cy, don.id, energy=1.0) if adjacent else dish.place(cx + 5, cy, don.id, energy=1.0)
    return c, rec, don, rcell


def _force_rolls(monkeypatch, c: Culture) -> None:
    """Every division rolls a mutation and, if hgt is on, a splice."""
    monkeypatch.setattr(config, "HGT_RATE", 1.0)
    c.mutation_rate = 1.0


# --- criterion 1: splices arise in a two-strain dish and the fossil names both -----------------


def test_a_division_next_to_a_non_kin_neighbour_splices_and_records_the_donor(monkeypatch, ticked, no_subprocess):
    c, rec, don, rcell = _two_strain_culture("splice", adjacent=True, mind=FakeMind(replies=[DAUGHTER]))
    ticked(c, every=1)
    _force_rolls(monkeypatch, c)
    got = c._on_divide(rcell)
    assert got is not None, "the division should have produced a daughter"
    sid, _ = got
    s = c.registry.strains[sid]
    assert s.donor == don.id, "the daughter must record the neighbour as its donor"
    assert s.parent == rec.id, "lineage still follows the recipient"


def test_a_splices_fossil_header_names_both_the_parent_and_the_donor(monkeypatch, ticked, no_subprocess):
    c, rec, don, rcell = _two_strain_culture("fossil", adjacent=True, mind=FakeMind(replies=[DAUGHTER]))
    ticked(c, every=1)
    _force_rolls(monkeypatch, c)
    sid, _ = c._on_divide(rcell)
    s = c.registry.strains[sid]
    fossil = (config.SOMA / f"{s.id}_{s.name}.py").read_text()
    assert "with a gene from" in fossil
    assert f"({don.id})" in fossil and f"({rec.id})" in fossil


def test_a_splice_is_logged_as_a_spliced_event_not_arose(monkeypatch, ticked, no_subprocess):
    c, rec, don, rcell = _two_strain_culture("event", adjacent=True, mind=FakeMind(replies=[DAUGHTER]))
    ticked(c, every=1)
    _force_rolls(monkeypatch, c)
    c._on_divide(rcell)
    spliced = [e for e in c.events if e["kind"] == "spliced"]
    assert spliced and spliced[-1]["donor"] == don.id and spliced[-1]["parent"] == rec.id
    assert not [e for e in c.events if e["kind"] == "arose"], "a splice must not also log an arose event"


# --- criterion 2: strains that never touch never splice ----------------------------------------


def test_a_division_with_no_non_kin_neighbour_is_an_ordinary_mutation(monkeypatch, ticked, no_subprocess):
    c, rec, don, rcell = _two_strain_culture("apart", adjacent=False, mind=FakeMind(replies=[DAUGHTER]))
    ticked(c, every=1)
    _force_rolls(monkeypatch, c)
    assert c._pick_donor(rcell) is None, "a cell with no non-kin neighbour has no donor to splice from"
    got = c._on_divide(rcell)
    assert got is not None, "an ordinary mutation still happens"
    sid, _ = got
    assert c.registry.strains[sid].donor is None, "with no contact the daughter is not a splice"
    assert [e for e in c.events if e["kind"] == "arose"] and not [e for e in c.events if e["kind"] == "spliced"]


def test_the_divide_hook_draws_the_mutation_roll_alone_off_and_the_splice_roll_and_pick_on(monkeypatch):
    """The draw order is fixed — mutation roll, then splice roll, then donor pick — and the two
    extra draws sit behind the feature gate. So an hgt-off dish draws exactly what it always did,
    and an hgt-on dish's stream is a stable, reproducible extension of it (docs/hgt.md)."""
    off, _, _, offcell = _two_strain_culture("drawoff", adjacent=True, hgt=False)
    off.mutation_rate = 1.0  # the roll passes; on the wall clock nothing is pooled, so it returns
    before = off.rng.getstate()
    off._on_divide(offcell)
    ref = random.Random()
    ref.setstate(before)
    ref.random()  # one draw: the mutation roll, and nothing more
    assert off.rng.getstate() == ref.getstate(), "hgt off draws exactly the mutation roll"

    on, _, _, oncell = _two_strain_culture("drawon", adjacent=True, hgt=True)
    on.mutation_rate = 1.0
    monkeypatch.setattr(config, "HGT_RATE", 1.0)
    before = on.rng.getstate()
    on._on_divide(oncell)
    ref = random.Random()
    ref.setstate(before)
    ref.random(), ref.random(), ref.random()  # mutation roll, splice roll, donor pick (one non-kin neighbour)
    assert on.rng.getstate() == ref.getstate(), "hgt on draws the mutation roll, the splice roll, and the donor pick"


def test_non_kin_neighbours_is_empty_when_surrounded_by_kin_and_empty():
    d = Dish("kin", width=24, height=12)
    d.register("a", FALLBACK_GENESIS)
    cx, cy = d.center()
    cell = d.place(cx, cy, "a", energy=1.0)
    d.place(cx + 1, cy, "a", energy=1.0)  # kin to the east; the rest of the ring is empty
    d.place(cx - 1, cy, "a", energy=1.0)  # kin to the west
    assert d.non_kin_neighbours(cell) == []


def test_non_kin_neighbours_lists_each_adjacent_stranger_once_per_contact():
    d = Dish("mix", width=24, height=12)
    d.register("a", FALLBACK_GENESIS)
    d.register("b", DONOR_GENOME)
    cx, cy = d.center()
    cell = d.place(cx, cy, "a", energy=1.0)
    d.place(cx + 1, cy, "b", energy=1.0)  # east
    d.place(cx, cy + 1, "b", energy=1.0)  # south, same strain: contact-weighted, so it appears twice
    d.place(cx - 1, cy, "a", energy=1.0)  # kin: never listed
    assert d.non_kin_neighbours(cell) == ["b", "b"]


# --- criterion 3: the census colour of a splice is between the parents' hues -------------------


def test_mix_hue_takes_the_shortest_arc_across_the_wrap():
    assert _mix_hue(0.9, 0.1) == 0.0  # the short way is through 1.0/0.0, not the 0.5 midpoint
    assert _mix_hue(0.1, 0.9) == pytest.approx(0.0, abs=1e-9)  # symmetric (up to float dust at the wrap)
    assert _mix_hue(0.2, 0.4) == pytest.approx(0.3)  # the interior case is the ordinary midpoint


def test_a_splices_hue_is_the_parents_midpoint_plus_the_same_jitter_a_mutation_draws():
    """Pin the exact deterministic hue: the splice's base is the shortest-arc midpoint of the
    recipient's and donor's hues, and the one gauss jitter drawn is the same the ordinary path
    would draw — so hgt does not shift any seeded trajectory (docs/hgt.md)."""
    reg = Registry("hue")
    p = reg.new("def live(me):\n    return 'rest'\n", None, 0, "p", "")
    d = reg.new("def live(me):\n    return 'eat'\n", None, 0, "d", "")
    parallel = random.Random()
    parallel.setstate(reg._rng.getstate())  # the state right before the splice's single gauss draw
    expected_jitter = parallel.gauss(0, 0.07)
    s = reg.new("def live(me):\n    return 'divide'\n", p.id, 5, "s", "", donor=d.id)
    assert s.donor == d.id
    assert s.hue == (_mix_hue(p.hue, d.hue) + expected_jitter) % 1.0


def test_an_ordinary_mutation_still_draws_exactly_one_gauss_jitter():
    """The parity claim from the other side: with no donor the hue is the parent's plus one gauss
    draw, the same draw a splice makes — so turning hgt on or off never changes the hue RNG."""
    reg = Registry("hue")
    p = reg.new("def live(me):\n    return 'rest'\n", None, 0, "p", "")
    parallel = random.Random()
    parallel.setstate(reg._rng.getstate())
    expected_jitter = parallel.gauss(0, 0.07)
    s = reg.new("def live(me):\n    return 'eat'\n", p.id, 5, "s", "")
    assert s.donor is None
    assert s.hue == (p.hue + expected_jitter) % 1.0


def test_biotic_strains_and_genome_print_the_donor(make_culture, capsys):
    """`biotic strains` shows the donor under a living splice's note, and `biotic genome` prints a
    `# donor:` line beside the lineage — the donor lineage the criterion asks for."""
    c = make_culture()
    rec_id = next(iter(c.registry.strains))
    don = c.registry.new(DONOR_GENOME, None, 0, "donor", "a neighbour")
    c.dish.register(don.id, DONOR_GENOME)
    splice = c.registry.new(
        FALLBACK_GENESIS.replace("1.0", "0.9"), rec_id, 5, "hybrid", "borrowed the scent-follow", donor=don.id
    )
    c.dish.register(splice.id, splice.source)
    cx, cy = c.dish.center()
    c.dish.place(cx + 4, cy, don.id, energy=1.0)
    c.dish.place(cx - 4, cy, splice.id, energy=1.0)
    c.save()
    main(["strains"])
    assert f"⇄ gene from donor ({don.id})" in capsys.readouterr().out
    main(["genome", splice.id])
    assert f"# donor: donor ({don.id})" in capsys.readouterr().out


# --- criterion 4: the curve gets a `spliced` cumulative column ---------------------------------


def test_spliced_is_an_int_column_appended_after_predated():
    assert "spliced" in curve.COLUMNS
    assert curve.COLUMNS.index("spliced") == curve.COLUMNS.index("predated") + 1
    assert "spliced" in curve._INT and "spliced" not in curve.DECIMALS


def test_the_spliced_metric_counts_donor_bearing_strains_and_round_trips_through_the_curve(
    monkeypatch, ticked, no_subprocess
):
    c, rec, don, rcell = _two_strain_culture("count", adjacent=True, mind=FakeMind(replies=[DAUGHTER]))
    ticked(c, every=1)
    _force_rolls(monkeypatch, c)
    c._on_divide(rcell)
    row = c.metrics()
    assert row["spliced"] == 1, "one strain now carries a donor"
    assert row["mutations_taken"] == 1, "a splice is also a mutation, so it counts in both"
    curve.append(config.CURVE, list(curve.COLUMNS), row)
    read = curve.read()[0]
    assert read["spliced"] == 1 and isinstance(read["spliced"], int)


def test_an_hgt_on_dish_resumes_on_exactly_the_same_trajectory(make_culture, fake_mutagen):
    """Enabling hgt adds a draw — the splice roll — to every division that rolls a mutation. That
    draw must land in the same order after a reload, or `biotic reproduce` (0037) would drift; a
    saved hgt dish resumes bit-for-bit, like any other. The single strain has no non-kin
    neighbour, so the donor pick never fires and the mutations stay ordinary — exactly the point:
    the extra roll is in the stream whether or not it finds a donor."""
    c = make_culture()
    c.dish.features["hgt"] = True
    for _ in range(60):
        c.step()
    assert len(c.registry.strains) > 1, "the fake mutagen should have produced mutations"
    c.save()
    c2 = Culture.load(Mind())
    assert c2.dish.features["hgt"] is True
    assert state(c2) == state(c)
    for _ in range(100):
        c.step()
        c2.step()
        assert state(c2) == state(c), f"diverged at tick {c.dish.tick}"


def test_a_run_with_no_splices_reads_zero_spliced(make_culture, fake_mutagen):
    """A single-strain dish (no non-kin neighbours, hgt off) mutates but never splices: mutations
    accrue while `spliced` stays 0, so the two columns are genuinely distinct."""
    c = make_culture()
    for _ in range(60):
        c.step()
    row = c.metrics()
    assert row["mutations_taken"] > 0, "the fake mutagen should have produced ordinary mutations"
    assert row["spliced"] == 0


# --- criterion 5 support: the splice prompt tracks the feature clauses, off by default ----------


def test_the_hgt_prompt_gains_the_lyse_clause_only_when_lyse_is_on():
    assert prompts.hgt_system({}) == prompts.HGT_SYSTEM
    assert prompts.hgt_system(None) == prompts.HGT_SYSTEM
    assert "me.threat" not in prompts.HGT_SYSTEM
    assert "me.threat" in prompts.hgt_system({"lyse": True})


def test_the_hgt_user_prompt_labels_the_recipient_and_the_donor():
    user = prompts.hgt_user(
        seed="tide",
        recipient_source="def live(me):\n    return 'rest'\n",
        recipient_name="recipient",
        donor_source="def live(me):\n    return 'eat'\n",
        donor_name="donor",
        tick=10,
        phase="log",
        population=8,
        share=0.5,
        nutrient=0.4,
        strains=2,
        whispers=[],
        rejections=[],
    )
    assert "Recipient genome (recipient):" in user
    assert "Donor genome (donor), an unrelated neighbour:" in user
    assert user.rstrip().endswith("one behaviour borrowed from the donor.")


# --- criterion for the design: an hgt-only dish leaves the cell API and mutation prompt untouched


def test_hgt_alone_does_not_change_the_cell_api_or_the_mutation_prompt():
    assert prompts.cell_api({"hgt": True}) == prompts.CELL_API
    assert prompts.mutagen_system({"hgt": True}) == prompts.MUTAGEN_SYSTEM
    assert prompts.genesis_system({"hgt": True}) == prompts.GENESIS_SYSTEM


# --- criterion 6: the wall-clock (recipient, donor) pool, on a hand clock, thread never started -


def _splice_mutagen(mutagen_factory, clock):
    """A mutagen that knows a recipient `f` and a donor `d`, on the hand clock, never started."""
    m = mutagen_factory(FakeMind(replies=[DAUGHTER]))
    m.know("d", "donor", DONOR_GENOME)
    m.context = {"census": {"f": 5, "d": 3}, "tick": 0}
    return m


def test_split_reads_a_key_as_recipient_and_donor():
    assert _split("f") == ("f", None)
    assert _split(("f", "d")) == ("f", "d")


def test_a_splice_request_is_picked_prepared_taken_under_its_pair_key(mutagen, clock, no_subprocess):
    m = _splice_mutagen(mutagen, clock)
    m.request("f", donor="d")
    assert m._pick() == ("f", "d"), "the splice key is picked while both strains are known"
    m._mutate(("f", "d"))
    assert m.ready() == 1, "the prepared splice sits in the pool"
    assert m.take("f") is None, "a bare mutation take must not draw the prepared splice"
    assert m.take("f", donor="d") is not None, "the pair's take draws it"
    assert m.take("f", donor="d") is None, "and only once"
    prepared = [e for e in m.mind.events if e["kind"] == "prepared"]
    assert prepared and "splice of f × d" in prepared[-1]["msg"]


def test_a_splice_request_whose_donor_leaves_the_pool_is_pruned_by_pick(mutagen, clock):
    m = _splice_mutagen(mutagen, clock)
    m.request("f", donor="d")
    m.genomes.pop("d")  # the donor went extinct between the request and the pick
    assert m._pick() is None, "a splice whose donor is gone is not picked"
    assert ("f", "d") not in m.requests and ("f", "d") not in m.splice_at


def test_forget_drops_composite_keys_for_a_recipient_and_for_a_donor(mutagen, clock, no_subprocess):
    m = _splice_mutagen(mutagen, clock)
    m.request("f", donor="d")
    m._mutate(("f", "d"))
    m.forget("d")  # the donor goes extinct
    assert ("f", "d") not in m.requests and ("f", "d") not in m.pool and ("f", "d") not in m.splice_at
    assert "d" not in m.genomes
    # and the mirror: forgetting the recipient drops the same key
    m2 = _splice_mutagen(mutagen, clock)
    m2.request("f", donor="d")
    m2.forget("f")
    assert ("f", "d") not in m2.requests and ("f", "d") not in m2.splice_at


def test_reset_clears_the_splice_clock(mutagen, clock):
    m = _splice_mutagen(mutagen, clock)
    m.request("f", donor="d")
    assert m.splice_at
    m.reset({"f": ("founder", FALLBACK_GENESIS)})
    assert m.splice_at == {} and m.requests == {} and m.pool == {}


def test_a_prepared_splice_lapses_after_the_expiry_when_its_pair_never_touches(mutagen, clock, no_subprocess):
    m = _splice_mutagen(mutagen, clock)
    m.request("f", donor="d")
    m._mutate(("f", "d"))  # prepared at context tick 0
    assert m.take("f", donor="d") is not None  # would be there if taken before expiry
    m._mutate(("f", "d"))  # prepare another
    m.context = {"census": {"f": 5, "d": 3}, "tick": config.HGT_EXPIRY_TICKS + 1}
    assert m.take("f", donor="d") is None, "past HGT_EXPIRY_TICKS the prepared splice has lapsed"
    assert ("f", "d") not in m.pool and ("f", "d") not in m.splice_at
