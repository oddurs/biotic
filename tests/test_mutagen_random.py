"""The random mutagen — the control arm (cairn 0015).

The random mutagen rewrites a genome at the AST level with no mind, no thread and no
network, so a `--mutagen random` dish evolves offline and reproducibly; `mixed` sends a
fraction of rolls to it. These tests hold its three acceptance criteria — it evolves
with zero API calls, every strain carries its origin and the curve splits by it, and a
thousand mutations of the fallback founder all pass or fail the membrane and none crash
— plus the persistence and schema back-compat the feature rides on. Every mind here is
fake and deterministic; nothing reaches the network.
"""

from __future__ import annotations

import random

import pytest

from bio import config, curve
from bio.culture import FALLBACK_GENESIS, Culture
from bio.membrane import admit
from bio.mind import Mind
from bio.mutagen_random import RandomMutagen
from bio.strains import _NAME, _strain_from, check_record

from .conftest import Variator


def _steps(c: Culture, n: int) -> None:
    for _ in range(n):
        c.step()


def _origins(c: Culture) -> dict[str | None, int]:
    counts: dict[str | None, int] = {}
    for s in c.registry.strains.values():
        counts[s.mutagen] = counts.get(s.mutagen, 0) + 1
    return counts


# --- criterion 3: the membrane is respected (fuzz) ----------------------------


def test_a_thousand_mutations_all_admit_or_refuse_and_none_crash():
    """The safety net: 1,000 AST mutations of the fallback founder. None raises; every daughter
    that comes back is a well-formed (name, note, source) the membrane admitted, with a name the
    registry will take; and a non-trivial fraction fire, so the operators are shown to evolve the
    genome, not merely to never crash."""
    rm = RandomMutagen(random.Random(0))
    non_none = 0
    for _ in range(1000):
        got = rm.mutate(FALLBACK_GENESIS)  # never raises: a failure is None, not an exception
        if got is None:
            continue
        non_none += 1
        name, note, src = got
        assert _NAME.match(name), f"a name the registry refuses: {name!r}"
        assert isinstance(note, str) and note
        assert admit(src), f"the mutagen returned a genome the membrane refuses: {note}"
    assert non_none > 500, f"too few mutations fired ({non_none}/1000): the operators barely evolve"


def test_the_random_mutagen_never_returns_its_parent_unchanged():
    """A daughter identical to its parent is not a mutation: it is refused (None), so no strain is
    born for a change that made no difference."""
    rm = RandomMutagen(random.Random(1))
    for _ in range(200):
        got = rm.mutate(FALLBACK_GENESIS)
        if got is not None:
            assert got[2].strip() != FALLBACK_GENESIS.strip()


# --- criterion 1: it evolves offline, with zero API calls ---------------------


@pytest.mark.parametrize("clock", ["wall", "tick"])
def test_random_arm_evolves_with_zero_api_calls(make_culture, ticked, monkeypatch, clock):
    """A `--mutagen random` dish evolves — more than one strain after 5,000 ticks — and makes zero
    calls to the mind, even though the mind is awake and would answer. The wall-clock case is the
    proof of the thread gate: without it the LLM mutagen's spontaneous path would call the mind
    (last_call starts at 0, so the wall-clock interval is long past). The naturalist is off
    (NOTES_EVERY=0), because it calls the mind on its own cadence."""
    monkeypatch.setattr(config, "MUTAGEN_KIND", "random")
    mind = Variator()  # awake: any routing regression that reaches the LLM path would call it
    c = make_culture(mind=mind)
    if clock == "tick":
        ticked(c, every=40)
    c.run(ticks=5000, tick_seconds=0)
    assert mind.chat_requests == 0, "the random arm called the mind"
    assert len(c.registry.strains) > 1, "the random arm did not evolve"
    assert all(s.mutagen == "random" for s in c.registry.strains.values() if s.parent is not None)


# --- criterion 2: origin on every strain; the curve splits arisen -------------


def test_every_strain_carries_its_origin_and_the_curve_splits_it(make_culture, monkeypatch):
    """The founder has no origin; every strain the random arm produces is marked `random`. The
    metrics row splits `arisen` into `arisen_llm` and `arisen_random`, exactly matching the counts
    in the registry, and the growth curve carries the two columns with real values in fresh rows."""
    monkeypatch.setattr(config, "MUTAGEN_KIND", "random")
    c = make_culture()
    founder = next(iter(c.registry.strains.values()))
    assert founder.mutagen is None, "the founding cell has no mutagen"
    _steps(c, 3000)
    origins = _origins(c)
    assert origins.get("random", 0) > 0, "the random arm produced no strains"
    assert set(origins) <= {None, "random"}, "the random arm produced a non-random origin"

    row = c.metrics()
    n_random = sum(1 for s in c.registry.strains.values() if s.mutagen == "random")
    n_llm = sum(1 for s in c.registry.strains.values() if s.mutagen == "llm")
    assert row["arisen_random"] == n_random and row["arisen_llm"] == n_llm
    assert row["arisen_random"] + row["arisen_llm"] + 1 == row["arisen"]  # +1 for the origin-less founder

    rows = curve.read()
    assert rows, "no curve was written"
    last = rows[-1]
    assert last["arisen_random"] == n_random and last["arisen_llm"] == 0


def test_a_fossil_names_the_mutagen_that_made_it(make_culture, monkeypatch):
    """`fossilize` records the origin in the strain's header, so soma/ says which mutagen wrote
    each genome — `by the random mutagen`."""
    monkeypatch.setattr(config, "MUTAGEN_KIND", "random")
    c = make_culture()
    _steps(c, 3000)
    child = next(s for s in c.registry.strains.values() if s.mutagen == "random")
    fossil = (config.SOMA / f"{child.id}_{child.name}.py").read_text()
    assert "by the random mutagen" in fossil
    founder = next(s for s in c.registry.strains.values() if s.mutagen is None)
    assert "mutagen" not in (config.SOMA / f"{founder.id}_{founder.name}.py").read_text()


# --- criterion: determinism and persistence -----------------------------------


def test_a_random_run_reproduces_across_a_save_and_reload(make_culture, monkeypatch):
    """A random run split by a save and reload walks the same path as one uninterrupted run of the
    same seed: same tick, same census, same strains (id, genome and origin). This is what the
    persisted `rng_mut` buys — the random mutation stream survives a save."""
    monkeypatch.setattr(config, "MUTAGEN_KIND", "random")

    def signature(c: Culture) -> tuple:
        strains = sorted((sid, s.source, s.mutagen) for sid, s in c.registry.strains.items())
        return c.dish.tick, sorted(c.dish.census().items()), strains

    whole = make_culture()
    _steps(whole, 400)

    split = make_culture()
    _steps(split, 150)
    split.save()
    reloaded = Culture.load(mind=Mind())
    _steps(reloaded, 250)

    assert signature(reloaded) == signature(whole)
    assert len(whole.registry.strains) > 1, "non-vacuous: the run actually mutated"


def test_a_freezer_sample_preserves_origin_and_the_mutation_rng(make_culture, monkeypatch, vessel):
    """A dish sample carries every strain's origin and the random mutagen's RNG, so a revive from a
    sample written by this apparatus reproduces the random stream cross-machine."""
    monkeypatch.setattr(config, "MUTAGEN_KIND", "random")
    c = make_culture()
    _steps(c, 1500)
    before = sum(1 for s in c.registry.strains.values() if s.mutagen == "random")
    assert before > 0
    c.save()
    rng_mut_state = c.rng_mut.getstate()
    sample = c.freeze("t")

    revived = make_culture()  # a fresh culture (its own founder), then the sample replaces its dish
    revived.revive(sample)
    after = sum(1 for s in revived.registry.strains.values() if s.mutagen == "random")
    assert after == before, "the sample lost the strains' origin"
    assert revived.rng_mut.getstate() == rng_mut_state, "the sample lost the mutation RNG"


# --- mixed mode: an exact partition, no fallback ------------------------------


def test_mixed_with_full_random_share_never_calls_the_mind(make_culture, ticked, monkeypatch):
    """`mixed` with RANDOM_SHARE=1 sends every roll to the random arm: an awake mind is never
    called and every new strain is `random`. On the tick clock the LLM mutagen makes calls only
    from the division, so a share of 1 is a clean zero-call proof."""
    monkeypatch.setattr(config, "MUTAGEN_KIND", "mixed")
    monkeypatch.setattr(config, "RANDOM_SHARE", 1.0)
    mind = Variator()
    c = make_culture(mind=mind)
    ticked(c, every=20)
    c.run(ticks=3000, tick_seconds=0)
    assert mind.chat_requests == 0
    children = [s for s in c.registry.strains.values() if s.parent is not None]
    assert children and all(s.mutagen == "random" for s in children)


def test_mixed_with_zero_random_share_is_all_llm(make_culture, ticked, monkeypatch):
    """`mixed` with RANDOM_SHARE=0 sends every roll to the LLM: the mind is called, and every new
    strain is `llm`. Confirms the partition is exact and there is no fallback to random."""
    monkeypatch.setattr(config, "MUTAGEN_KIND", "mixed")
    monkeypatch.setattr(config, "RANDOM_SHARE", 0.0)
    mind = Variator()
    c = make_culture(mind=mind)
    ticked(c, every=20)
    c.run(ticks=3000, tick_seconds=0)
    assert mind.chat_requests > 0, "the LLM arm made no calls"
    children = [s for s in c.registry.strains.values() if s.parent is not None]
    assert children and all(s.mutagen == "llm" for s in children)


# --- schema back-compat -------------------------------------------------------


def test_a_record_without_an_origin_loads_as_none():
    """A strain record from before this feature has no `mutagen` key: it still validates, and the
    strain it yields has no origin (null), so an old strains.json and old samples load."""
    record = {
        "id": "00ab",
        "parent": None,
        "name": "old_founder",
        "note": "from before origins",
        "source": FALLBACK_GENESIS,
        "born": 0,
        "hue": 0.5,
        "extinct_at": None,
        "peak": 3,
        "generation": 0,
    }
    check_record(record)  # does not raise
    assert _strain_from(record).mutagen is None


def test_an_unknown_origin_is_refused_by_name():
    """A hand-written record with an origin the apparatus does not know is refused, and the refusal
    names the field — the schema admits only llm, random, hgt or null."""
    record = {
        "id": "00ab",
        "parent": None,
        "name": "cosmic",
        "note": "",
        "source": FALLBACK_GENESIS,
        "born": 0,
        "hue": 0.5,
        "mutagen": "cosmic",
    }
    with pytest.raises(ValueError, match="mutagen"):
        check_record(record)


# --- routing / settling -------------------------------------------------------


def test_use_mutagen_settles_the_arm_and_refuses_a_bad_one(make_culture):
    """use_mutagen validates and remembers the arm, parallel to use_clock: a flag wins, is
    remembered, and a value that is not an arm is refused with a message that names it."""
    c = make_culture()
    assert c.use_mutagen("random") == "random" and c.mutagen_choice == "random"
    assert c.use_mutagen(None) == "random", "the flag is remembered"
    with pytest.raises(ValueError, match="llm, random or mixed"):
        c.use_mutagen("cosmic")
