"""The freezer: samples appear on cadence and the listing shows them; a revived dish replays the
run it was taken from, tick for tick; a revived strain is watched and the log says whether it
took; a revive is recorded as an event and as a new branch in the curve; and nothing frozen is
ever overwritten."""

from __future__ import annotations

import fcntl
import gzip
import json
import os
import re
import threading
import time

import pytest

from bio import config, curve, freezer
from bio.__main__ import main
from bio.culture import Culture, incubating, sterilize
from bio.dish import Dish
from bio.mind import Mind
from bio.strains import Registry

from .conftest import VARIANT, WANDERER, state

RESTER = "def live(me):\n    return 'rest'\n"


def step(c: Culture, n: int) -> None:
    for _ in range(n):
        c.step()


def events(kind: str | None = None) -> list[dict]:
    evs = [json.loads(ln) for ln in config.EVENTS.read_text().splitlines()]
    return [e for e in evs if kind is None or e["kind"] == kind]


def ticks() -> list[int]:
    return [r["tick"] for r in curve.read()]


def edit(path, fn) -> None:
    """Edit a sample in place, the way a person with a text editor would."""
    if path.name.endswith(".gz"):
        with gzip.open(path, "rt") as f:
            doc = json.load(f)
        fn(doc)
        with gzip.open(path, "wt") as f:
            json.dump(doc, f)
    else:
        doc = json.loads(path.read_text())
        fn(doc)
        path.write_text(json.dumps(doc))


def strain_sample(sid: str, source: str, name: str = "guest", seed: str = "test", memory: dict | None = None):
    doc = {
        "format": 1,
        "kind": "strain",
        "biotic": "0",
        "seed": seed,
        "w": 24,
        "h": 12,
        "tick": 0,
        "frozen_at": 0.0,
        "label": None,
        "strain": {
            "id": sid,
            "parent": None,
            "name": name,
            "note": "",
            "source": source,
            "born": 0,
            "hue": 0.3,
            "extinct_at": None,
            "peak": 0,
            "generation": 2,
        },
        "lineage": [name],
        "memory": memory or {},
        "living": 0,
    }
    return freezer.write(doc, config.FREEZER / f"strain-{sid}.json")


# --- criterion 1: automatic samples on cadence, and the listing --------------------------------
def test_automatic_samples_appear_on_cadence_and_the_listing_shows_them(culture, monkeypatch, capsys):
    monkeypatch.setattr(config, "FREEZE_EVERY", 50)
    pops = {}
    for _ in range(120):
        culture.step()
        pops[culture.dish.tick] = len(culture.dish.cells)
    es = [e for e in freezer.entries() if e.kind == "dish"]
    assert [e.tick for e in es] == [0, 50, 100]
    assert [e.label for e in es] == ["genesis", "auto", "auto"]
    # a sample is the live state at the end of that tick, not the tick before
    assert [e.population for e in es] == [5, pops[50], pops[100]]
    assert [(e.strains_living, e.strains_total) for e in es] == [(1, 1)] * 3
    assert freezer.stems() == ["00000000-genesis", "00000050-auto", "00000100-auto"]
    assert freezer.dish_ticks() == [0, 50, 100]
    frozen = events("frozen")
    assert [(e["tick"], e["label"], e["sample"]) for e in frozen] == [
        (0, "genesis", "00000000-genesis"),
        (50, "auto", "00000050-auto"),
        (100, "auto", "00000100-auto"),
    ]
    main(["freezer"])
    out = capsys.readouterr().out
    assert out.startswith("freezer for “test” — 3 samples")
    assert re.search(rf"^\s+50\s+auto\s+.*\s{pops[50]}\s+1/1", out, re.M)
    assert re.search(r"^\s+0\s+genesis\s", out, re.M)
    main(["freezer", "--json"])
    js = json.loads(capsys.readouterr().out)
    assert [(e["tick"], e["label"], e["population"]) for e in js] == [
        (0, "genesis", 5),
        (50, "auto", pops[50]),
        (100, "auto", pops[100]),
    ]
    main(["status"])
    assert re.search(r"^freezer\s+3 samples · last at tick 100$", capsys.readouterr().out, re.M)


def test_freeze_every_zero_disables_automatic_samples(culture):
    step(culture, 60)
    assert freezer.stems() == ["00000000-genesis"]


def test_freezing_does_not_change_the_trajectory(make_culture, monkeypatch):
    """A freeze draws no random numbers and touches nothing in the dish: a culture frozen every
    ten ticks, by hand in between, and strain-sampled, walks the same path as one never frozen."""
    frozen = make_culture(genome=WANDERER)
    (fid,) = list(frozen.registry.strains)
    monkeypatch.setattr(config, "FREEZE_EVERY", 10)
    step(frozen, 30)
    frozen.freeze("bench")
    frozen.freeze_strain(fid)
    step(frozen, 30)
    monkeypatch.setattr(config, "FREEZE_EVERY", 0)
    plain = make_culture(genome=WANDERER)
    step(plain, 60)
    assert state(frozen) == state(plain)
    assert len(frozen.dish.cells) > 5
    assert freezer.dish_ticks() == [10, 20, 30, 30, 40, 50, 60]


# --- criterion 2: revive <tick> replays the run that never left ---------------------------------
def test_revive_restores_a_dish_whose_next_100_ticks_match_the_run_that_never_left(make_culture, fake_mutagen):
    """WANDERER draws from the dish RNG and keeps a list in memory; the fake mutagen makes the
    culture's own RNG and the registry load-bearing. Everything must come back."""
    c = make_culture(genome=WANDERER)
    step(c, 40)
    p = c.freeze("check")
    assert p.name == "00000040-check.json.gz"
    states = []
    for _ in range(100):
        c.step()
        states.append(state(c))
    assert len(c.registry.strains) > 1, "the fake mutagen should have made the culture RNG load-bearing"
    c.save()
    c2 = Culture.load(Mind())
    assert state(c2) == states[-1]
    c2.revive(p)
    assert c2.dish.tick == 40
    assert c2.revivals == [{"from": 40, "was": 140, "at": c2.revivals[0]["at"], "sample": "00000040-check"}]
    assert set(c2.mutagen.genomes) == set(c2.dish.genomes)
    assert [e.tick for e in freezer.entries() if e.label == "pre-revive"] == [140]
    # the revived dish is on disk, and reading it back gives the same dish
    assert state(Culture.load(Mind())) == state(c2)
    for i in range(100):
        c2.step()
        assert state(c2) == states[i], f"diverged at tick {c2.dish.tick}"
    assert c2.dish.tick == 140


def test_a_saved_culture_resumes_on_exactly_the_same_trajectory(culture, fake_mutagen):
    """dish.json carries the culture's own state too: the mutation-roll RNG, the phase detector
    and a running mutagen boost all decide the next tick and all come back from a save."""
    c = culture
    step(c, 60)
    c.drop("mutagen")
    assert c.mutagen.boost_until == 360
    c.save()
    c2 = Culture.load(Mind())
    assert (c2.mutagen.boost, c2.mutagen.boost_until) == (6.0, 360)
    assert state(c2) == state(c)
    for _ in range(100):
        c.step()
        c2.step()
        assert state(c2) == state(c)
    assert len(c.registry.strains) > 1


def test_revive_through_the_inbox_is_taken_within_three_ticks(make_culture, fake_mutagen):
    c = make_culture(genome=WANDERER)
    step(c, 40)
    p = c.freeze("check")
    states = []
    for _ in range(100):
        c.step()
        states.append(state(c))
    (config.INBOX / "0001.json").write_text(json.dumps({"revive": "00000040-check"}))
    for _ in range(3):  # the inbox is read on ticks divisible by 3
        c.step()
        if c.dish.tick == 40:
            break
    assert c.dish.tick == 40, "the revive replaced the dish and that step returned without touching it"
    assert [e.tick for e in freezer.entries() if e.label == "pre-revive"] == [141]
    for i in range(100):
        c.step()
        assert state(c) == states[i]
    assert p.exists()


# --- criterion 4: the event, and the curve's branch column ---------------------------------------
def test_reviving_records_the_event_and_opens_a_new_curve_branch(make_culture):
    """The event carries from, was and the branch it opens; the rows that follow carry that branch,
    so (branch, tick) names a row uniquely although tick has stepped back."""
    c = make_culture()
    step(c, 40)
    p = c.freeze("t")
    step(c, 100)
    c.revive(p)
    ev = events("revived")[-1]
    assert (ev["from"], ev["was"], ev["sample"], ev["tick"], ev["branch"]) == (40, 140, "00000040-t", 40, 1)
    assert ev["msg"].startswith("revived from tick 40 (the dish was at 140) — ")
    assert [e["sample"] for e in events("frozen")] == ["00000040-t", "00000140-pre-revive"]
    step(c, 20)
    rows = curve.read()
    assert ticks() == list(range(10, 150, 10)) + [50, 60], "no row is written for the revive itself"
    assert [r["branch"] for r in rows] == [0] * 14 + [1, 1]
    assert rows[-1]["population"] == len(c.dish.cells)
    again = Culture.load(Mind())
    assert (again.revivals, again.branch) == (c.revivals, 1)


def test_a_forward_revive_is_a_new_branch_too(make_culture):
    """A revive to a later tick than the dish was at leaves the tick column monotone: nothing in
    `tick` marks that seam, which is why the seam is a column of its own. The branch is the
    vessel's count, not the sample's, so reviving a sample taken on an earlier branch does not
    reuse its number."""
    c = make_culture()
    step(c, 40)
    early = c.freeze("t")
    step(c, 100)
    late = c.freeze("t")
    c.revive(early)  # back: the dish was at 140, is at 40
    step(c, 20)
    mid = c.freeze("t")  # a sample of branch 1, at tick 60
    c.revive(late)  # forward: from 60 to 140; tick keeps climbing
    step(c, 20)
    c.revive(mid)  # back into a branch-1 sample: a new branch, not branch 1 again
    step(c, 20)
    rows = curve.read()
    assert ticks() == list(range(10, 150, 10)) + [50, 60] + [150, 160] + [70, 80]
    assert [r["branch"] for r in rows] == [0] * 14 + [1, 1] + [2, 2] + [3, 3]
    keys = [(r["branch"], r["tick"]) for r in rows]
    assert len(set(keys)) == len(keys), "(branch, tick) names a row uniquely"
    revived = [e for e in events("revived") if "from" in e]
    assert [(e["from"], e["was"], e["branch"]) for e in revived] == [(40, 140, 1), (140, 60, 2), (60, 160, 3)]
    for e in revived:  # the join the docs promise: branch k is exactly the rows after the k-th revived event
        seg = [r["tick"] for r in rows if r["branch"] == e["branch"]]
        assert seg and seg[0] > e["from"] and seg == sorted(seg)
    assert (c.branch, len(c.revivals)) == (3, 2), "the chain is the dish's lineage; the branch is the vessel's count"
    assert freezer.read(mid)["culture"]["branch"] == 1, "a sample carries the branch it was taken on"
    assert Culture.load(Mind()).branch == 3


def test_a_dish_revive_carries_the_samples_watch_list(culture):
    """A watch belongs to the state it was started in: revive a sample taken during one and the
    observation concludes in the revived timeline."""
    c = culture
    step(c, 30)
    c.revive_strain(strain_sample("abcd", VARIANT), n=3, at=(2, 6))
    assert c.watching == [{"strain": "abcd", "since": 30, "until": 130}]
    step(c, 10)
    p = c.freeze("mid")
    step(c, 100)
    assert c.watching == [] and events("revived")[-1]["took"] is True
    c.revive(p)
    assert c.dish.tick == 40 and c.watching == [{"strain": "abcd", "since": 30, "until": 130}]
    step(c, 90)
    outcomes = [e for e in events("revived") if "took" in e]
    assert [(e["tick"], e["took"]) for e in outcomes] == [(130, True), (130, True)]
    assert c.watching == []


# --- criterion 3: revive --strain into a fresh dish, and the log says whether it took -----------
def test_revived_strain_into_a_fresh_dish_grows_and_the_log_says_it_took(culture):
    c = culture
    (fid,) = list(c.registry.strains)
    p = c.freeze_strain(fid)
    assert p.name == f"strain-{fid}.json"
    doc = freezer.read(p)
    assert (doc["living"], doc["lineage"], doc["seed"], doc["w"], doc["h"]) == (5, ["founder"], "test", 24, 12)
    step(c, 30)
    c.save()  # germinate(thaw=) freezes the dish on disk as pre-revive before it autoclaves the vessel
    c2 = Culture.germinate("test", Mind(), fresh=True, thaw=p)
    assert c2.dish.tick == 0
    assert c2.dish.census() == {fid: 5}
    assert c2.dish.nutrient == Dish("test", 24, 12).nutrient, "same seed and size: the same agar"
    assert c2.watching == [{"strain": fid, "since": 0, "until": 100}]
    assert config.GENESIS.read_text() == c2.registry.strains[fid].source
    assert config.SEED_FILE.read_text().strip() == "test"
    assert freezer.stems() == ["00000000-genesis", "00000000-genesis-2", "00000030-pre-revive", f"strain-{fid}"]
    ev = events("revived")[0]
    assert ev["msg"] == f"revived founder ({fid}) into a fresh dish — 5 cells"
    assert (ev["into"], ev["n"], ev["at"], ev["sample"], ev["tick"]) == ("fresh", 5, None, f"strain-{fid}", 0)
    step(c2, 101)
    (outcome,) = [e for e in events("revived") if "took" in e]
    assert outcome["took"] is True
    assert outcome["cells"] > 5 and outcome["ticks"] == 100 and outcome["tick"] == 100
    assert outcome["msg"] == f"revived founder took — {outcome['cells']} cells after 100 ticks"
    assert c2.watching == []
    c2.save()
    assert (Culture.load(Mind()).dish.tick, Culture.load(Mind()).watching) == (101, [])


def test_revived_strain_that_starves_is_reported_as_not_taking(culture):
    c = culture
    s = c.registry.new(RESTER, None, c.dish.tick, "rester", "sits still")
    c.dish.register(s.id, RESTER)
    c.dish.inoculate(s.id, 3, at=(4, 6))
    p = c.freeze_strain(s.id)
    c2 = Culture.germinate("test", Mind(), fresh=True, thaw=p)
    assert c2.dish.census() == {s.id: 5}
    step(c2, 101)
    (outcome,) = [e for e in events("revived") if "took" in e]
    assert outcome["took"] is False and outcome["cells"] == 0
    assert 0 < outcome["ticks"] < 100
    assert outcome["msg"] == f"revived rester did not take — extinct after {outcome['ticks']} ticks"
    assert c2.dish.cells == {} and c2.watching == []
    assert any(e["strain"] == s.id for e in events("extinct"))


def test_the_same_strain_sample_into_a_fresh_dish_gives_the_same_trajectory(culture, fake_mutagen):
    (fid,) = list(culture.registry.strains)
    p = culture.freeze_strain(fid)
    a = Culture.germinate("test", Mind(), fresh=True, thaw=p)
    first = []
    for _ in range(80):
        a.step()
        first.append(state(a))
    b = Culture.germinate("test", Mind(), fresh=True, thaw=p)
    assert b.dish.tick == 0 and len(b.dish.cells) == 5
    for i in range(80):
        b.step()
        assert state(b) == first[i]


def test_revived_strain_into_the_current_dish_is_registered_placed_and_lives(culture):
    c = culture
    step(c, 30)
    p = strain_sample("abcd", VARIANT, memory={"n": 7, "trail": [1, 2]})
    tick, before = c.dish.tick, set(c.dish.cells)
    rng = c.dish.rng.getstate()
    c.revive_strain(p, n=3, at=(2, 6))
    assert c.dish.tick == tick and c.dish.rng.getstate() == rng
    new = set(c.dish.cells) - before
    assert new == {(2, 6), (1, 6), (3, 6)}
    assert c.dish.genomes["abcd"] == VARIANT, "the genome must be registered with the dish, not only the registry"
    assert c.registry.strains["abcd"].born == tick and c.registry.strains["abcd"].generation == 2
    assert c.mutagen.genomes["abcd"] == ("guest", VARIANT)
    assert all(c.dish.cells[t].memory == {"n": 7, "trail": [1, 2]} for t in new)
    assert len({id(c.dish.cells[t].memory["trail"]) for t in new}) == 3
    assert c.watching == [{"strain": "abcd", "since": tick, "until": tick + 100}]
    ev = events("revived")[-1]
    assert ev["msg"] == "revived guest (abcd) into the dish at (2,6) — 3 cells"
    assert (ev["into"], ev["n"], ev["at"], ev["sample"]) == ("current", 3, [2, 6], "strain-abcd")
    assert [e.tick for e in freezer.entries() if e.label == "pre-revive"] == [tick]
    step(c, 20)
    assert c.dish.census()["abcd"] >= 3
    assert c.dish.deaths["lysed"] == 0


def test_revive_strain_at_must_be_inside_the_dish(culture):
    """inoculate(at=) takes the free tiles nearest the point, so a point off the dish would land
    on the rim while the log reported the point; it is refused instead, before the pre-revive
    freeze, from the library, the CLI and the inbox alike."""
    c = culture
    p = strain_sample("abcd", VARIANT)
    before = freezer.stems()
    for at in ((24, 6), (0, 12), (-1, 0), (999, 999)):
        with pytest.raises(ValueError, match=rf"\({at[0]},{at[1]}\) is outside the dish \(24×12\)"):
            c.revive_strain(p, n=2, at=at)
    with pytest.raises(SystemExit, match=r"\(999,999\) is outside the dish"):
        main(["revive", "--strain", "abcd", "--into", "current", "--at", "999,999"])
    (config.INBOX / "0001.json").write_text(json.dumps({"revive_strain": "abcd", "n": 1, "at": [24, 6]}))
    step(c, 3)
    assert any("bad intervention" in e["msg"] and "(24,6) is outside the dish" in e["msg"] for e in events("mind"))
    assert "abcd" not in c.dish.census() and "abcd" not in c.registry.strains
    assert freezer.stems() == before, "a point outside the dish is refused before anything is frozen"
    c.revive_strain(p, n=2, at=(23, 6))  # the last column is inside the bounds; the nearest free tiles take it
    assert c.dish.census()["abcd"] == 2


def test_a_dish_revive_between_pick_and_mutate_does_not_kill_the_mutagen(culture):
    """The mutagen thread picks a strain, waits out the interval, then mutates it. A revive through
    the inbox in that window resets the genome map (an extinction forgets one strain); _mutate
    must find the strain gone and return, not raise on the thread and end it for the run."""
    m = culture.mutagen
    for gone in (lambda: m.reset({}), lambda: m.forget("abcd")):
        m.know("abcd", "guest", VARIANT)
        m.request("abcd")
        assert m._pick() == "abcd"
        gone()
        m._mutate("abcd")  # Mind.think is patched to fail loudly, so returning here is the whole point
        assert m.pool == {} and m.requests == {} and m.produced == 0
    m.know("abcd", "guest", VARIANT)
    assert m._pick() is None, "nothing is requested; a strain known again is not mutated on its own"


def test_a_strain_id_already_taken_by_another_genome_is_refused(culture):
    c = culture
    (fid,) = list(c.registry.strains)
    p = strain_sample(fid, RESTER, name="impostor")
    before = freezer.stems()
    with pytest.raises(ValueError, match="already taken by a different genome"):
        c.revive_strain(p)
    assert c.dish.genomes[fid] != RESTER
    assert freezer.stems() == before, "a refused revive changes nothing: the id check comes before the freeze"
    assert [e["label"] for e in events("frozen")] == ["genesis"]


def test_revive_into_the_current_dish_needs_a_dish(vessel):
    p = strain_sample("abcd", VARIANT)
    empty = Culture("test", Dish("test", 24, 12), Registry("test"), Mind())
    with pytest.raises(ValueError, match="nothing in the dish"):
        empty.revive_strain(p)
    c = Culture.germinate("test", Mind(), thaw=p)
    assert c.dish.census() == {"abcd": 5}
    assert config.SEED_FILE.read_text().strip() == "test"
    assert not any(e.label == "pre-revive" for e in freezer.entries())


# --- the membrane, the seed rule, the freezer's housekeeping -------------------------------------
def test_a_revived_genome_passes_the_membrane_again(culture):
    c = culture
    (fid,) = list(c.registry.strains)
    sp = c.freeze_strain(fid)
    dp = c.freeze("t")
    step(c, 5)
    c.save()
    n, tick = len(freezer.files()), c.dish.tick
    edit(sp, lambda d: d["strain"].__setitem__("source", "import os\n" + d["strain"]["source"]))
    with pytest.raises(ValueError, match=f"founder \\({fid}\\) does not pass the membrane: .*[Ii]mport"):
        c.revive_strain(sp)
    with pytest.raises(ValueError, match=f"founder \\({fid}\\) does not pass the membrane: .*[Ii]mport"):
        Culture.germinate("test", Mind(), fresh=True, thaw=sp)
    assert Culture.load(Mind()).dish.tick == tick, "the gate comes before the autoclave"
    with pytest.raises(SystemExit, match=f"founder \\({fid}\\) does not pass the membrane"):
        main(["revive", "--strain", fid, "--yes"])
    with pytest.raises(SystemExit, match=f"founder \\({fid}\\) does not pass the membrane"):
        main(["revive", "--strain", fid, "--into", "current"])
    assert Culture.load(Mind()).dish.tick == tick
    assert len(freezer.files()) == n, "from the CLI too, the gate comes before the pre-revive freeze"
    edit(dp, lambda d: d["dish"]["genomes"].__setitem__(fid, "import os\n" + d["dish"]["genomes"][fid]))
    with pytest.raises(ValueError, match=f"genome of strain {fid} in 00000000-t fails the membrane: .*[Ii]mport"):
        c.revive(dp)
    assert c.dish.tick == tick
    assert len(freezer.files()) == n, "the gate comes before the pre-revive freeze"


def test_a_dish_sample_from_another_seed_needs_an_empty_vessel(culture):
    c = culture
    p = c.freeze("t")
    edit(p, lambda d: d.__setitem__("seed", "other"))
    with pytest.raises(ValueError, match="from “other”; this vessel is “test” — sterilize first"):
        c.revive(p)
    assert c.seed == "test" and c.dish.tick == 0
    sterilize()
    assert not config.DISH_FILE.exists() and p.exists()
    empty = Culture("other", Dish("other", 24, 12), Registry("other"), Mind())
    empty.revive(p)
    assert config.SEED_FILE.read_text().strip() == "other"
    assert empty.dish.census() == c.dish.census()
    assert Culture.load(Mind()).seed == "other"
    assert not any(e.label == "pre-revive" for e in freezer.entries())
    assert events("revived")[-1]["msg"].startswith("revived from tick 0 (into an empty vessel)")


def test_a_strain_sample_founds_a_fresh_dish_of_its_own_seed(culture):
    """A fresh dish autoclaves the vessel, so the seed rule does not apply: the dish takes the
    sample's seed and size, and the caller has to name that seed."""
    sp = strain_sample("abcd", VARIANT, seed="other")
    with pytest.raises(ValueError, match="from “other”; a fresh dish for it has that seed"):
        Culture.germinate("test", Mind(), fresh=True, thaw=sp)
    assert Culture.load(Mind()).seed == "test"
    c = Culture.germinate("other", Mind(), fresh=True, thaw=sp)
    assert (c.seed, c.dish.w, c.dish.h, c.dish.census()) == ("other", 24, 12, {"abcd": 5})
    assert c.dish.nutrient == Dish("other", 24, 12).nutrient
    assert config.SEED_FILE.read_text().strip() == "other"


def test_sterilize_keeps_the_freezer_unless_told_otherwise(culture):
    genesis = config.FREEZER / "00000000-genesis.json.gz"
    assert genesis.exists()
    sterilize()
    assert genesis.exists()
    assert not config.DISH_FILE.exists() and not config.EVENTS.exists() and config.INBOX.is_dir()
    sterilize(freezer=True)
    assert not config.FREEZER.exists() and config.INBOX.is_dir()


def test_samples_are_never_overwritten_and_keys_resolve_to_one_sample(culture):
    c = culture
    step(c, 60)
    a = c.freeze("x")
    b = c.freeze("x")
    assert (a.name, b.name) == ("00000060-x.json.gz", "00000060-x-2.json.gz")
    assert freezer.read(a)["tick"] == freezer.read(b)["tick"] == 60
    with pytest.raises(LookupError, match="say which: 00000060-x, 00000060-x-2"):
        freezer.resolve("60")
    with pytest.raises(LookupError, match="say which: 00000060-x, 00000060-x-2"):
        freezer.resolve("60", label="x")
    y = c.freeze("y")
    assert freezer.resolve("60", label="y") == y
    with pytest.raises(LookupError, match="nothing frozen at tick 60 with label z"):
        freezer.resolve("60", label="z")
    assert freezer.resolve("00000060-x-2") == b
    assert freezer.resolve("00000060-x-2.json.gz") == b
    assert freezer.resolve(str(b)) == b
    assert freezer.resolve(os.path.relpath(b)).resolve() == b.resolve(), "a relative path is a path too"
    with pytest.raises(LookupError, match="no such file nowhere/00000060-x.json.gz"):
        freezer.resolve("nowhere/00000060-x.json.gz")
    genesis = config.FREEZER / "00000000-genesis.json.gz"
    assert freezer.resolve("0") == freezer.resolve("0", kind="dish") == genesis
    with pytest.raises(LookupError, match="nothing frozen at tick 7"):
        freezer.resolve("7")
    with pytest.raises(LookupError, match="no strain sample zzzz"):
        freezer.resolve("zzzz")
    with pytest.raises(LookupError, match="no dish sample zzzz"):
        freezer.resolve("zzzz", kind="dish")
    # a label may itself end in -<digits>; it is matched by what the sample stores, not by parsing
    # the name, where run-2 and the -2 a second sample of `run` gets look the same
    r2, r = c.freeze("run-2"), c.freeze("run")
    assert (r2.name, r.name) == ("00000060-run-2.json.gz", "00000060-run.json.gz")
    assert freezer.resolve("60", label="run-2") == r2
    assert freezer.resolve("60", label="run") == r
    x2 = c.freeze("x-2")
    assert x2.name == "00000060-x-2-2.json.gz", "the name 00000060-x-2 was taken by the second sample of x"
    assert freezer.resolve("60", label="x-2") == x2
    with pytest.raises(LookupError, match="say which: 00000060-x, 00000060-x-2$"):
        freezer.resolve("60", label="x")
    assert freezer.clean_label("Pre-Revive") == "pre-revive"
    with pytest.raises(ValueError, match="label"):
        freezer.clean_label("Bad Label!")
    with pytest.raises(ValueError, match="label"):
        c.freeze("no spaces")
    assert freezer.stems() == [
        "00000000-genesis",
        "00000060-run",
        "00000060-run-2",
        "00000060-x",
        "00000060-x-2",
        "00000060-x-2-2",
        "00000060-y",
    ]


def test_a_sample_that_is_not_a_sample_is_refused(culture, capsys):
    bad = config.FREEZER / "00000009-bad.json.gz"
    with gzip.open(bad, "wt") as f:
        f.write("{}")
    with pytest.raises(ValueError, match="not a sample"):
        freezer.read(bad)
    assert bad.name not in [e.stem for e in freezer.entries()]
    with pytest.raises(ValueError):
        culture.revive(bad)
    # a field of the wrong type is refused when the sample is read, so the listing skips the file
    # instead of tracing back on it, and a revive names the field
    dp = culture.freeze("typed")
    (fid,) = list(culture.registry.strains)
    sp = culture.freeze_strain(fid)
    for path, field, value, said in (
        (dp, "tick", "abc", "'tick' is not a tick"),
        (dp, "tick", 9.5, "'tick' is not a tick"),
        (dp, "seed", 7, "'seed' is not text"),
        (dp, "frozen_at", "yesterday", "'frozen_at' is not a time"),
        (dp, "label", ["typed"], "'label' is not text or null"),
        (sp, "w", "24", "'w' is not a size"),
        (sp, "h", 0, "'h' is not a size"),
        (sp, "memory", [1, 2], "'memory' is not a record"),
    ):
        keep = freezer.read(path)
        edit(path, lambda d: d.__setitem__(field, value))
        with pytest.raises(ValueError, match=f"{re.escape(path.name)}: {said}"):
            freezer.read(path)
        assert freezer.stem_of(path) not in [e.stem for e in freezer.entries()]
        main(["freezer"])
        main(["freezer", "--json"])
        assert freezer.stem_of(path) not in capsys.readouterr().out, f"{field}={value!r} broke the listing"
        argv = ["revive", str(path), "--yes"] if path is dp else ["revive", "--strain", str(path), "--yes"]
        with pytest.raises(SystemExit, match=said):
            main(argv)
        freezer.write(keep, path)
    assert {freezer.stem_of(dp), freezer.stem_of(sp)} <= {e.stem for e in freezer.entries()}


# --- a running incubator: the inbox and the lock --------------------------------------------------
def test_freezer_requests_arrive_through_the_inbox_while_the_incubator_runs(culture):
    c = culture
    (config.INBOX / "0001.json").write_text(json.dumps({"freeze": "q"}))
    step(c, 3)  # the inbox is read on ticks divisible by 3
    assert c.dish.tick == 3
    assert (config.FREEZER / "00000003-q.json.gz").exists()
    step(c, 9)
    (config.INBOX / "0002.json").write_text(json.dumps({"revive": "00000003-q"}))
    (config.INBOX / "0003.json").write_text(json.dumps({"revive": "00009999-nope"}))
    step(c, 3)
    assert c.dish.tick == 3, "the revive replaced the dish and the step returned without touching it"
    assert [e.tick for e in freezer.entries() if e.label == "pre-revive"] == [15]
    assert any("bad intervention" in e["msg"] and "00009999-nope" in e["msg"] for e in events("mind"))
    (fid,) = list(c.registry.strains)
    (config.INBOX / "0004.json").write_text(json.dumps({"freeze_strain": fid, "label": "inbox"}))
    step(c, 3)
    assert c.dish.tick == 6
    assert (config.FREEZER / f"strain-{fid}-inbox.json").exists()
    req = {"revive_strain": f"strain-{fid}-inbox", "n": 2, "at": [2, 6]}
    (config.INBOX / "0005.json").write_text(json.dumps(req))
    (config.INBOX / "0006.json").write_text(json.dumps({**req, "into": "fresh"}))
    step(c, 3)
    assert c.dish.tick == 9
    assert (2, 6) in c.dish.cells and (1, 6) in c.dish.cells
    assert any("bad intervention" in e["msg"] and "stopped incubator" in e["msg"] for e in events("mind"))
    n_frozen = len(events("frozen"))
    (config.INBOX / "0007.json").write_text(json.dumps({**req, "n": 0}))
    (config.INBOX / "0008.json").write_text(json.dumps({"freeze": "ghost", "pid": 999999}))
    (config.INBOX / "0009.json").write_text(json.dumps({"freeze": "mine", "pid": os.getpid()}))
    step(c, 3)
    assert c.dish.tick == 12
    assert any("bad intervention" in e["msg"] and "at least 1 cell, not 0" in e["msg"] for e in events("mind"))
    assert len(events("frozen")) == n_frozen + 1, "n=0 is refused before the pre-revive freeze"
    assert any(s.endswith("-mine") for s in freezer.stems()) and not any(s.endswith("-ghost") for s in freezer.stems())
    assert any(e["msg"] == "dropped a freeze request queued for another incubator (pid 999999)" for e in events("mind"))
    assert list(config.INBOX.glob("*.json")) == []


def test_incubator_lock_is_seen_by_the_cli_and_refuses_a_second_run(culture, capsys):
    c = culture
    (fid,) = list(c.registry.strains)
    assert incubating() is None
    f = open(config.LOCK_FILE, "a+")
    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    f.write("4242\n")
    f.flush()
    try:
        assert incubating() == 4242
        with pytest.raises(RuntimeError, match="already running \\(pid 4242\\)"):
            c.run(ticks=1)
        with pytest.raises(RuntimeError, match="stop it first"):
            sterilize()
        main(["freeze", "--label", "later"])
        out = capsys.readouterr().out
        assert "pid 4242" in out and "freeze queued" in out
        (req,) = list(config.INBOX.glob("*.json"))
        assert json.loads(req.read_text()) == {"freeze": "later", "pid": 4242}
        req.unlink()
        main(["revive", "0", "--yes"])
        assert "revive queued" in capsys.readouterr().out
        (req,) = list(config.INBOX.glob("*.json"))
        assert json.loads(req.read_text()) == {"revive": "00000000-genesis", "pid": 4242}
        req.unlink()
        c.freeze_strain(fid)
        main(["revive", "--strain", fid, "--into", "current", "--n", "2"])
        assert "revive queued" in capsys.readouterr().out
        (req,) = list(config.INBOX.glob("*.json"))
        assert json.loads(req.read_text()) == {"revive_strain": f"strain-{fid}", "n": 2, "at": None, "pid": 4242}
        req.unlink()
        with pytest.raises(SystemExit, match="pid 4242.*stop it .* before reviving into a fresh dish"):
            main(["revive", "--strain", fid, "--yes"])
        for argv in (["run", "--ticks", "1"], ["live"], ["sterilize", "--yes"], ["seed", "x", "--fresh"]):
            with pytest.raises(SystemExit, match="already running"):
                main(argv)
        assert c.dish.tick == 0 and config.DISH_FILE.exists()
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()
    assert incubating() is None
    c.run(ticks=2, tick_seconds=0)
    assert c.dish.tick == 2
    assert incubating() is None, "the lock is released when the run ends"


def test_a_probe_holding_the_lock_for_an_instant_does_not_refuse_the_incubator(culture):
    """`biotic status` probes the lock with a shared flock and lets go at once; an incubator that
    starts at that instant waits it out instead of reporting itself already running."""
    c = culture
    f = open(config.LOCK_FILE, "a+")
    fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
    assert incubating() is None, "a probe is not an incubator"

    def let_go():
        time.sleep(0.05)
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()

    t = threading.Thread(target=let_go)
    t.start()
    try:
        c.run(ticks=1, tick_seconds=0)
    finally:
        t.join()
    assert c.dish.tick == 1 and incubating() is None


def test_a_freezer_the_culture_cannot_write_does_not_stop_the_dish(culture, monkeypatch):
    """The cadence freeze is treated as curve.csv is: a freezer that cannot be written is said
    once as a `freezer` event, tried again at every cadence, and the log says when it works
    again. A freeze a person asks for raises, so the CLI and the inbox can tell them."""
    c = culture
    (fid,) = list(c.registry.strains)
    sp = c.freeze_strain(fid)
    good = config.FREEZER
    wall = config.VESSEL.parent / "wall"
    wall.write_text("a file where the directory should be\n")
    monkeypatch.setattr(config, "FREEZER", wall / "freezer")
    monkeypatch.setattr(config, "FREEZE_EVERY", 5)
    step(c, 12)
    assert c.dish.tick == 12
    (said,) = events("freezer")
    assert said["tick"] == 5 and said["msg"].startswith("sample not written at tick 5: ")
    with pytest.raises(OSError):
        c.freeze("manual")
    # from the CLI the same is a one-line refusal, and a revive refuses at its pre-revive freeze,
    # before anything changes (a sample named by its path is found without the freezer directory)
    for argv in (
        ["freeze"],
        ["freeze", "--strain", fid],
        ["revive", str(good / "00000000-genesis.json.gz"), "--yes"],
        ["revive", "--strain", str(sp), "--into", "current"],
        ["revive", "--strain", str(sp), "--yes"],
    ):
        with pytest.raises(SystemExit, match="^freezer not writable: "):
            main(argv)
    assert config.DISH_FILE.exists() and Culture.load(Mind()).dish.tick == 0
    monkeypatch.setattr(config, "FREEZER", good)
    step(c, 3)
    assert c.dish.tick == 15 and (good / "00000015-auto.json.gz").exists()
    assert [e["msg"] for e in events("freezer")][-1] == "freezer resumed at tick 15"
    assert [e["sample"] for e in events("frozen")] == ["00000000-genesis", f"strain-{fid}", "00000015-auto"]
    assert list(wall.parent.glob("*.tmp")) == []
    # the genesis freeze is the culture's own too: `biotic seed` founds the culture and says so
    monkeypatch.setattr(config, "FREEZER", wall / "freezer")
    c2 = Culture.germinate("test", Mind(), fresh=True)
    assert c2.dish.tick == 0 and config.DISH_FILE.exists()
    assert events("freezer")[-1]["msg"].startswith("sample not written at tick 0: ")


def test_a_failed_sample_write_leaves_nothing_behind(vessel):
    for name in ("00000099-x.json.gz", "strain-abcd.json"):
        with pytest.raises(TypeError):
            freezer.write({"format": 1, "odd": object()}, config.FREEZER / name)
    assert list(config.FREEZER.iterdir()) == [], "no half-written sample and no .tmp"


def test_a_strain_is_adopted_under_the_culture_lock(culture, monkeypatch):
    """The eyepiece iterates the registry under the lock; adopt() inserts into it, so it must
    hold the lock too, or a render mid-insert drops a frame."""
    c = culture
    held = []
    orig = Registry.adopt

    def spy(self, sd, tick):
        held.append(c.lock.locked())
        return orig(self, sd, tick)

    monkeypatch.setattr(Registry, "adopt", spy)
    c.revive_strain(strain_sample("abcd", VARIANT), n=2, at=(2, 6))
    assert held == [True]


def test_a_strain_whose_id_is_all_digits_is_revived_by_id(culture, capsys):
    """Ids are four hex characters, so about one in seven is all digits; `--strain 1234` is a
    strain, not tick 1234."""
    c = culture
    p = strain_sample("1234", VARIANT)
    assert freezer.resolve("1234", kind="strain") == p
    with pytest.raises(LookupError, match="nothing frozen at tick 1234"):
        freezer.resolve("1234", kind="dish")
    main(["revive", "--strain", "1234", "--into", "current", "--n", "2"])
    assert "revived guest (1234) into the dish" in capsys.readouterr().out
    assert Culture.load(Mind()).dish.census()["1234"] == 2
    (config.INBOX / "0001.json").write_text(json.dumps({"revive_strain": "1234", "n": 1, "at": [2, 6]}))
    step(c, 3)
    assert c.dish.cells[(2, 6)].strain == "1234"


def test_a_strain_record_with_a_malformed_field_is_refused_before_anything_changes(culture):
    """Samples are edited by hand. A field of the wrong shape is a refusal that names it, not a
    record the culture admits and trips over later: a generation that is text breaks the next
    curve row for good, and an id with path parts would put a fossil outside soma/."""
    c = culture
    tries = [
        ("generation", "2", "'generation' is not a generation"),
        ("born", "0", "'born' is not a tick"),
        ("hue", "0.3", "'hue' is not a hue"),
        ("hue", 1.0, "'hue' is not a hue"),
        ("id", "../..", "'id' is not a strain id"),
        ("id", "abcde", "'id' is not a strain id"),
        ("parent", "../x", "'parent' is not a strain id or null"),
        ("name", "Guest Two", "'name' is not a strain name"),
        ("name", "../guest", "'name' is not a strain name"),
        ("source", ["def live(me):"], "'source' is not a genome"),
        ("extinct_at", "never", "'extinct_at' is not a tick or null"),
        ("peak", -1, "'peak' is not a count"),
    ]
    files = sorted(config.SOMA.parent.rglob("*.py"))  # every .py under tmp_path: soma/ and everything above it
    for field, value, said in tries:
        p = strain_sample("abcd", VARIANT)
        edit(p, lambda d: d["strain"].__setitem__(field, value))
        before = freezer.stems()
        with pytest.raises(ValueError, match=f"strain record {said}"):
            c.revive_strain(p, n=2, at=(2, 6))
        with pytest.raises(SystemExit, match=f"strain record {said}"):
            main(["revive", "--strain", "abcd", "--into", "current"])
        with pytest.raises(SystemExit, match=f"strain record {said}"):
            main(["revive", "--strain", "abcd", "--yes"])
        assert freezer.stems() == before, f"{field}={value!r}: the refusal must come before the pre-revive freeze"
        assert "abcd" not in c.registry.strains and "abcd" not in c.mutagen.genomes
        p.unlink()
    assert sorted(config.SOMA.parent.rglob("*.py")) == files, "no fossil was written, in soma/ or anywhere above it"
    assert Culture.load(Mind()).dish.tick == 0 and [e["label"] for e in events("frozen")] == ["genesis"]
    # the same record inside a dish sample is refused when the registry is read, before the freeze
    dp = c.freeze("t")
    edit(dp, lambda d: d["strains"]["strains"][0].__setitem__("generation", "0"))
    n = len(freezer.files())
    with pytest.raises(ValueError, match="strain record 'generation' is not a generation"):
        c.revive(dp)
    assert len(freezer.files()) == n and c.dish.tick == 0
    # what is admitted is what the culture computes with: a revive, then a curve row
    c.revive_strain(strain_sample("abcd", VARIANT), n=2, at=(2, 6))
    step(c, 10)
    want = 2 * c.dish.census()["abcd"] / len(c.dish.cells)  # generation 2 admitted as an int, weighted by cell
    assert curve.read()[-1]["mean_gen"] == pytest.approx(want, abs=0.005), "mean_gen is written to two decimals"


def test_a_strain_sample_missing_a_field_is_refused_before_anything_changes(culture, capsys):
    """Samples are edited by hand. A record without a field a Strain needs is a refusal with the
    field's name, from the library and the CLI alike, and it comes before the pre-revive freeze."""
    c = culture
    p = strain_sample("abcd", VARIANT)
    edit(p, lambda d: d["strain"].pop("hue"))
    dp = c.freeze("t")
    edit(dp, lambda d: d["strains"]["strains"][0].pop("hue"))
    c.save()
    before = freezer.stems()
    with pytest.raises(ValueError, match="strain record is missing 'hue'"):
        c.revive_strain(p, n=2, at=(2, 6))
    with pytest.raises(ValueError, match="strain record is missing 'hue'"):
        c.revive(dp)
    with pytest.raises(SystemExit, match="strain record is missing 'hue'"):
        main(["revive", "--strain", "abcd", "--into", "current"])
    with pytest.raises(SystemExit, match="strain record is missing 'hue'"):
        main(["revive", "--strain", "abcd", "--yes"])
    with pytest.raises(SystemExit, match="strain record is missing 'hue'"):
        main(["revive", "0", "--label", "t", "--yes"])
    assert freezer.stems() == before and Culture.load(Mind()).dish.tick == 0
    assert [e["label"] for e in events("frozen")] == ["genesis", "t"]
    edit(p, lambda d: d.__setitem__("strain", "not a record"))
    with pytest.raises(ValueError, match="'strain' is not a record"):
        freezer.read(p)


def test_revive_strain_n_is_honoured_in_a_fresh_dish_and_at_is_for_the_current_one(culture, capsys):
    c = culture
    (fid,) = list(c.registry.strains)
    c.freeze_strain(fid)
    untouched = ["00000000-genesis", f"strain-{fid}"]
    with pytest.raises(SystemExit, match="--at goes with --into current"):
        main(["revive", "--strain", fid, "--at", "2,2", "--yes"])
    for argv in (
        ["revive", "--strain", fid, "--n", "0", "--yes"],
        ["revive", "--strain", fid, "--into", "current", "--n", "-1"],
    ):
        with pytest.raises(SystemExit):
            main(argv)
    assert "at least 1 cell" in capsys.readouterr().err
    assert Culture.load(Mind()).dish.tick == 0 and freezer.stems() == untouched, "a refused flag changes nothing"
    main(["revive", "--strain", fid, "--n", "9", "--yes"])
    assert f"revived founder ({fid}) into a fresh dish — 9 cells" in capsys.readouterr().out
    assert Culture.load(Mind()).dish.census() == {fid: 9}
    assert events("revived")[0]["n"] == 9
    main(["revive", "--strain", fid, "--into", "current", "--n", "3", "--at", "2,6"])
    assert "into the dish at (2,6) — 3 cells" in capsys.readouterr().out
    assert Culture.load(Mind()).dish.census() == {fid: 12}
    with pytest.raises(ValueError, match="at least 1 cell"):
        Culture.germinate("test", Mind(), fresh=True, n=0)


def test_cli_freeze_revive_and_freezer_in_process(culture, capsys, monkeypatch):
    c = culture
    (fid,) = list(c.registry.strains)
    step(c, 40)
    c.save()
    main(["freeze", "--label", "Bench"])
    assert "frozen as 00000040-bench" in capsys.readouterr().out
    main(["freeze", "--strain", fid])
    assert f"frozen as strain-{fid}" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="no strain zzzz"):
        main(["freeze", "--strain", "zzzz"])
    with pytest.raises(SystemExit, match="label"):
        main(["freeze", "--label", "not ok"])
    step(c, 20)
    c.save()
    main(["status"])
    assert re.search(r"^freezer\s+3 samples · last at tick 40$", capsys.readouterr().out, re.M)
    main(["freezer"])
    out = capsys.readouterr().out
    assert re.search(r"^\s+40\s+bench\s", out, re.M) and re.search(rf"^\s+{fid}\s+founder\s+gen 0", out, re.M)
    # a declined confirmation changes nothing
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    main(["revive", "40"])
    assert Culture.load(Mind()).dish.tick == 60
    main(["revive", "--strain", fid])
    assert Culture.load(Mind()).dish.tick == 60
    with pytest.raises(SystemExit, match="label"):
        main(["revive", "40", "--label", "not ok"])
    main(["revive", "40", "--label", "Bench", "--yes"])  # matched as `freeze --label Bench` stored it: bench
    assert capsys.readouterr().out.startswith("revived from tick 40 (the dish was at 60)")
    assert Culture.load(Mind()).dish.tick == 40
    main(["revive", "--strain", fid, "--into", "current", "--n", "2", "--at", "2,6"])
    assert "into the dish at (2,6) — 2 cells" in capsys.readouterr().out
    assert (2, 6) in Culture.load(Mind()).dish.cells
    main(["revive", "--strain", fid, "--yes"])
    out = capsys.readouterr().out
    assert out.startswith(f"revived founder ({fid}) into a fresh dish — 5 cells")
    assert "`biotic live`" in out
    assert Culture.load(Mind()).dish.tick == 0
    assert [e.tick for e in freezer.entries() if e.label == "pre-revive"] == [40, 40, 60]  # listed by tick
    assert not config.EVENTS.exists() or "into a fresh dish" in events("revived")[0]["msg"]
    for argv in (["revive"], ["revive", "40", "--strain", fid], ["revive", "40", "--n", "3"], ["revive", "7"]):
        with pytest.raises(SystemExit):
            main(argv)
    with pytest.raises(SystemExit, match="does not go with --strain"):
        main(["revive", "--strain", fid, "--label", "x"])
    with pytest.raises(SystemExit, match="is a strain sample"):
        main(["revive", f"strain-{fid}"])
    with pytest.raises(SystemExit, match="is a dish sample"):
        main(["revive", "--strain", "00000040-bench"])
    main(["sterilize", "--yes"])
    assert "the freezer is kept" in capsys.readouterr().out and freezer.stems()
    main(["freezer"])
    assert capsys.readouterr().out.startswith("freezer — 7 samples")  # no seed file; the samples are still listed
    main(["sterilize", "--yes", "--freezer"])
    capsys.readouterr()
    main(["freezer"])
    assert capsys.readouterr().out.strip() == "nothing in the freezer"


def test_revive_into_an_empty_vessel_from_the_cli(culture, capsys):
    c = culture
    step(c, 20)
    c.freeze("keep")
    (fid,) = list(c.registry.strains)
    c.freeze_strain(fid)
    sterilize()
    main(["revive", "20"])
    assert capsys.readouterr().out.startswith("revived from tick 20 (into an empty vessel)")
    assert Culture.load(Mind()).dish.tick == 20
    sterilize()
    main(["revive", "--strain", fid])
    assert "into a fresh dish — 5 cells" in capsys.readouterr().out
    assert Culture.load(Mind()).dish.census() == {fid: 5}
    sterilize()
    with pytest.raises(SystemExit, match="nothing in the dish to revive into"):
        main(["revive", "--strain", fid, "--into", "current"])
