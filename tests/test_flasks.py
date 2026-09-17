"""Replicate flasks: one install, many dishes. Every test here is offline (a dormant mind, the
conftest network trap armed), deterministic (a fixed seed, a fixed dish size) and on the main
thread. Most use the injectable in-process runner; the one exception,
`test_default_runner_spawns_real_isolated_subprocesses`, drives the default `subprocess.Popen`
runner with real child processes to guard the concurrent and entrypoint paths (the children stay
dormant, so it is still offline). It covers the four acceptance criteria of item 0006 one by one,
plus the founder-identity and determinism invariants the divergence rests on."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from bio import config, curve, flasks, plot
from bio.__main__ import main
from bio.culture import FALLBACK_GENESIS, Culture
from bio.dish import Dish
from bio.mind import Mind
from bio.strains import Registry

SEED = "tide"
SIZE = (24, 12)  # the small dish the suite uses; big enough that the flasks diverge within ~60 ticks


def _root(tmp_path: Path) -> Path:
    return tmp_path / "flasks"


def _dishes(name: str, root: Path) -> list[Dish]:
    """Each flask's saved dish, freshly loaded, in flask order."""
    base = flasks.flask_root(root) / name
    man = flasks.load_manifest(name, root)
    return [Dish.from_dict(json.loads((base / fid / "dish.json").read_text())) for fid in man["flasks"]]


def _series(dish: Dish, ticks: int) -> tuple[int, ...]:
    """The population, tick by tick, as the dish grows. A bare dish stepped with no on_divide hook
    reproduces exactly what a dormant-mind culture's dish does (the hook only rolls the culture
    RNG, never the dish RNG), so this is a faithful, deterministic trajectory."""
    out = []
    for _ in range(ticks):
        dish.step()
        out.append(len(dish.cells))
    return tuple(out)


def _in_process_runner(ticks: int = 30):
    """A runner for flasks.run that runs each flask in this process, on the main thread, so the
    cell budget's SIGALRM works. Loads and runs the culture inside each flask's vessel scope."""

    def run(jobs: list[tuple[str, Path]]) -> list[tuple[str, int]]:
        out = []
        for fid, d in jobs:
            with config.vessel_scope(d):
                c = Culture.load()
                assert not c.mind.awake, "a flask run must be dormant — item 0006 authorizes no spend"
                c.run(ticks=ticks, tick_seconds=0)
                c.mutagen.join(timeout=5)
            out.append((fid, 0))
        return out

    return run


# --- AC#2: identical agar, divergent trajectories ------------------------------


def test_flasks_share_their_agar_but_diverge(tmp_path):
    root = _root(tmp_path)
    flasks.new("tide", SEED, n=3, root=root, size=SIZE)
    dishes = _dishes("tide", root)
    assert [d.flask for d in dishes] == ["01", "02", "03"]

    # same seed -> the same agar, tile for tile, in every flask
    assert all(d.nutrient == dishes[0].nutrient for d in dishes), "replicates of one seed must share their agar"
    assert all(d.w == SIZE[0] and d.h == SIZE[1] for d in dishes), "every flask shares the dish geometry"

    # the per-flask RNG salt diverges the dynamics from the very inoculation: the founding cells
    # land on different tiles in each flask, though the count is the same
    inocula = {tuple(sorted((c.x, c.y) for c in d.cells.values())) for d in dishes}
    assert len(inocula) == 3, "the founding cells scatter to different tiles in each flask"
    # and it compounds: over a full horizon (a series, not one coarse final count) all three differ
    trajectories = {_series(d, 70) for d in dishes}
    assert len(trajectories) >= 2, "flasks with the same agar must still diverge as they grow"


# --- AC#1: two vessels in one checkout, isolated -------------------------------


def test_new_restores_the_config_globals_it_scoped(tmp_path):
    before = {k: getattr(config, k) for k in config._paths(config.VESSEL)}
    flasks.new("tide", SEED, n=2, root=_root(tmp_path), size=SIZE)
    after = {k: getattr(config, k) for k in config._paths(config.VESSEL)}
    assert after == before, "flasks.new must leave the process-global config exactly as it found it"


def _dish_tick(d: Path) -> int:
    return Dish.from_dict(json.loads((d / "dish.json").read_text())).tick


def test_running_one_vessel_leaves_the_others_files_untouched(tmp_path):
    """The acceptance criterion is that two vessels run in one checkout without touching each
    other's files. Rather than a flaky true-concurrency test we prove the property that matters and
    is deterministic: running one vessel writes only into its own directory and leaves every other
    flask exactly as it was, and the process-global config is restored around the scoped run.
    (Real simultaneity is safe because replicates run as separate processes, each with its own
    process-global config and its own incubator.lock — docs/flasks.md.)"""
    root = _root(tmp_path)
    flasks.new("tide", SEED, n=3, root=root, size=SIZE)
    d01, d02, d03 = flasks.flask_dirs("tide", root)
    # a second, independent set of the same seed in a different directory
    flasks.new("other", SEED, n=1, root=root, size=SIZE)
    (other,) = flasks.flask_dirs("other", root)

    before = config.CURVE
    with config.vessel_scope(d01):
        c = Culture.load()
        c.run(ticks=30, tick_seconds=0)
        c.mutagen.join(timeout=5)
    assert config.CURVE == before, "the scoped run must restore the process globals it changed"

    # flask 01 advanced and wrote its own curve and lock
    assert (d01 / "curve.csv").exists() and (d01 / "incubator.lock").exists()
    assert _dish_tick(d01) >= 30
    # every other vessel — its siblings and the unrelated set — is untouched: still tick 0, no curve
    for d in (d02, d03, other):
        assert not (d / "curve.csv").exists(), f"running flask 01 wrote into {d}"
        assert _dish_tick(d) == 0, f"running flask 01 advanced {d}"
    assert other.is_relative_to(root / "other") and not other.is_relative_to(root / "tide")


# --- AC#3: one overlay for all replicates --------------------------------------


def test_curve_figure_overlays_one_trace_per_flask(tmp_path):
    root = _root(tmp_path)
    flasks.new("tide", SEED, n=3, root=root, size=SIZE)
    flasks.run("tide", 30, root=root, runner=_in_process_runner())

    fig = flasks.curve_figure("tide", root=root)
    assert len(fig.panels) == 1  # the default column, population
    (panel,) = fig.panels
    assert len(panel.traces) == 3, "one trace per flask"
    assert [t.label for t in panel.traces] == ["01", "02", "03"]
    assert len({t.style for t in panel.traces}) == 3, "each flask gets a distinct style"
    assert all(t.xs and t.ys for t in panel.traces), "every trace has points"
    assert "3 flasks" in fig.title and f"seed “{SEED}”" in fig.title
    assert fig.markers == [], "an overlay carries no per-flask event markers"


def test_curve_figure_can_overlay_several_columns(tmp_path):
    root = _root(tmp_path)
    flasks.new("tide", SEED, n=2, root=root, size=SIZE)
    flasks.run("tide", 30, root=root, runner=_in_process_runner())
    fig = flasks.curve_figure("tide", cols=("population", "nutrient"), root=root)
    assert [p.label for p in fig.panels] == [plot.LABELS["population"], plot.LABELS["nutrient"]]
    assert all(len(p.traces) == 2 for p in fig.panels)


# --- one ancestor, no network --------------------------------------------------


def test_every_flask_is_founded_from_one_ancestor_offline(tmp_path):
    root = _root(tmp_path)
    man = flasks.new("tide", SEED, n=4, root=root, size=SIZE)
    base = flasks.flask_root(root) / "tide"

    genesis = {(base / fid / "genesis.py").read_text() for fid in man["flasks"]}
    assert len(genesis) == 1, "every flask must carry the byte-identical ancestor genome"
    # the dormant mind founds the built-in fallback, and reaching the network would have tripped
    # the conftest urlopen trap during new()
    assert next(iter(genesis)) == FALLBACK_GENESIS
    assert man["model"] is None, "a dormant founding records no model"
    ids = {json.loads((base / fid / "strains.json").read_text())["strains"][0]["id"] for fid in man["flasks"]}
    assert ids == {man["founder"]["id"]}, "the same ancestor strain id in every flask"


def test_new_records_the_flask_id_in_each_vessel(tmp_path):
    root = _root(tmp_path)
    man = flasks.new("tide", SEED, n=3, root=root, size=SIZE)
    base = flasks.flask_root(root) / "tide"
    for fid in man["flasks"]:
        assert (base / fid / "flask.txt").read_text().strip() == fid


def test_new_records_the_resolved_arm_not_a_bad_env(tmp_path, monkeypatch):
    """A malformed BIOTIC_MUTAGEN with no --mutagen flag: the flasks fall back to `mixed` at
    construction (as Culture.__init__ does, mirroring the clock), so the manifest must record the
    arm they actually run — the resolved `mixed`, not the raw invalid string. flasks new does not
    go through use_mutagen, so without this the bad env would be written verbatim into the
    manifest while the flasks ran `mixed`."""
    monkeypatch.setattr(config, "MUTAGEN_KIND", "cosmic")  # a typo'd BIOTIC_MUTAGEN
    root = _root(tmp_path)
    man = flasks.new("tide", SEED, n=2, root=root, size=SIZE)
    assert man["mutagen"] == "mixed", "the manifest kept the raw invalid env, not the resolved arm"
    on_disk = json.loads((flasks.flask_root(root) / "tide" / "flasks.json").read_text())
    assert on_disk["mutagen"] == "mixed"


def test_new_records_an_explicit_mutagen_arm(tmp_path):
    """A --mutagen arm passed to flasks new is remembered in the manifest as the arm every flask of
    the set runs under."""
    root = _root(tmp_path)
    man = flasks.new("tide", SEED, n=2, root=root, size=SIZE, mutagen="random")
    assert man["mutagen"] == "random"


def test_new_refuses_an_existing_populated_set(tmp_path):
    root = _root(tmp_path)
    flasks.new("tide", SEED, n=2, root=root, size=SIZE)
    with pytest.raises(FileExistsError, match="already holds a set of flasks"):
        flasks.new("tide", SEED, n=2, root=root, size=SIZE)


@pytest.mark.parametrize("n", [0, -3])
def test_new_refuses_a_nonpositive_flask_count(tmp_path, n):
    """A set has at least one flask. The count is validated before any directory is made, so a bad
    --n is a clean ValueError (surfaced by cmd_flasks_new), not an IndexError traceback, and it
    leaves no empty flasks/<name>/ behind."""
    root = _root(tmp_path)
    with pytest.raises(ValueError, match="at least 1 flask"):
        flasks.new("zero", SEED, n=n, root=root, size=SIZE)
    assert not (flasks.flask_root(root) / "zero").exists(), "a refused set must leave no directory behind"


# --- determinism pins ----------------------------------------------------------


def test_empty_flask_reproduces_the_lone_dish_and_culture_rng():
    """The salt is conditional: an empty flask must key the RNGs byte-for-byte the way a lone dish
    always has, so committed samples, physics pins and the resume round-trip are untouched."""
    lone = random.Random(f"{SEED}::dish").getstate()
    assert Dish(SEED).rng.getstate() == lone
    assert Dish(SEED, flask="").rng.getstate() == lone
    # a salted flask keys a different stream
    assert Dish(SEED, flask="01").rng.getstate() != lone

    # the culture RNG carries the same conditional salt
    c_lone = Culture(SEED, Dish(SEED), Registry(SEED), Mind())
    assert c_lone.rng.getstate() == random.Random(f"{SEED}::culture").getstate()
    c_flask = Culture(SEED, Dish(SEED, flask="01"), Registry(SEED), Mind())
    assert c_flask.rng.getstate() == random.Random(f"{SEED}::01::culture").getstate()


def test_flask_rides_through_dish_json_round_trip():
    d = Dish(SEED, *SIZE, flask="07")
    clone = Dish.from_dict(json.loads(json.dumps(d.to_dict())))
    assert clone.flask == "07"


# --- flasks run ----------------------------------------------------------------


def test_run_advances_every_flasks_curve(tmp_path):
    root = _root(tmp_path)
    flasks.new("tide", SEED, n=3, root=root, size=SIZE)
    results = flasks.run("tide", 30, root=root, runner=_in_process_runner(ticks=30))
    assert results == [("01", 0), ("02", 0), ("03", 0)]
    for d in flasks.flask_dirs("tide", root):
        rows = curve.read(d / "curve.csv")
        assert rows and max(r["tick"] for r in rows) >= 30, "each flask ran forward and wrote its curve"


def test_run_without_ticks_is_refused(tmp_path):
    root = _root(tmp_path)
    flasks.new("tide", SEED, n=2, root=root, size=SIZE)
    with pytest.raises(ValueError, match="bounded run"):
        flasks.run("tide", None, root=root, runner=_in_process_runner())
    with pytest.raises(SystemExit):  # argparse makes --ticks required on the CLI
        main(["flasks", "run", "tide", "--dir", str(root)])


def test_a_missing_set_is_named_not_an_errno_path(tmp_path):
    """load_manifest names the missing set and points at `flasks new`, rather than leaking the
    internal flasks.json path with a raw errno. Both `flasks run` and `flasks curve` inherit it,
    and the CLI surfaces that message on exit (not `[Errno 2] .../flasks.json`)."""
    root = _root(tmp_path)
    for call in (lambda: flasks.run("nope", 5, root=root), lambda: flasks.curve_figure("nope", root=root)):
        with pytest.raises(FileNotFoundError, match="no flask set named “nope”"):
            call()

    for argv in (["flasks", "run", "nope", "--ticks", "5"], ["flasks", "curve", "nope"]):
        with pytest.raises(SystemExit) as e:
            main([*argv, "--dir", str(root)])
        msg = str(e.value.code)
        assert "no flask set named “nope”" in msg
        assert "Errno" not in msg and "flasks.json" not in msg, "the CLI must not leak the errno or the json path"


def test_subprocess_runner_targets_the_flask_with_the_mind_off():
    """The default runner spawns `biotic run --vessel <dir>` with the mind's keys emptied. This pins
    the argv and the child environment cheaply, where a packaging or budget regression would
    otherwise ship; the real processes themselves run in
    `test_default_runner_spawns_real_isolated_subprocesses` below."""
    argv = flasks._argv(Path("/flasks/x/03"), ticks=100, tick=0.0)
    assert argv[1:] == ["-m", "bio", "run", "--vessel", "/flasks/x/03", "--tick", "0.0", "--ticks", "100", "--quiet"]
    env = flasks._child_env()
    assert env["OPENROUTER_API_KEY"] == "" and env["BIOTIC_API_KEY"] == "" and env["BIOTIC_BASE_URL"] == ""


def test_default_runner_spawns_real_isolated_subprocesses(tmp_path):
    """AC#1, exercised end to end: the default runner (no injected runner) launches one real
    `biotic run --vessel <dir>` process per flask, `--parallel 2` at once, and both advance their
    own curve without touching each other's directory. This is the one test that spawns real
    children, so it guards the Popen pool and the `-m bio` entrypoint that the in-process runner
    never reaches. The children run dormant (keys blanked in `_child_env`), so it is still offline;
    it is bounded (30 ticks on a small dish) so it stays fast."""
    root = _root(tmp_path)
    flasks.new("tide", SEED, n=2, root=root, size=SIZE)

    results = flasks.run("tide", 30, parallel=2, root=root)  # default runner: real subprocesses
    assert results == [("01", 0), ("02", 0)], "both real subprocesses must exit cleanly"

    d01, d02 = flasks.flask_dirs("tide", root)
    for d in (d01, d02):
        rows = curve.read(d / "curve.csv")
        assert rows and max(r["tick"] for r in rows) >= 30, f"{d.name} did not run its own curve forward"
        assert (d / "incubator.lock").exists(), f"{d.name} did not hold its own lock"
    # each child wrote its own distinct dish: a shared-file race would have left them identical
    assert (d01 / "dish.json").read_text() != (d02 / "dish.json").read_text(), "the flasks must stay isolated"
