---
id: 6
title: 'Replicate flasks: many dishes from one install'
type: feature
status: done
milestone: dish
assignee: Oddur Sigurdsson
depends_on:
- 4
created: 2026-09-08
updated: 2026-09-16
priority: p1
effort: m
area: bio/config.py, bio/culture.py
---

## Problem

Every path is hardcoded to `vessel/` and `soma/`. One experiment per checkout.
The whole methodology of the field is replication — Lenski has twelve flasks,
and the citrate result means something *because* eleven flasks did not do it.

## Proposal

- `BIOTIC_VESSEL=<dir>` and `--vessel <dir>` on every command. `soma/` moves
  inside the vessel (`<vessel>/soma/`) so a flask is one directory. The root
  `soma/` becomes a symlink to the default vessel's, or is dropped from the
  README in favour of `<vessel>/soma`. Decide and record here.
- `biotic flasks new <name> --seed "…" [--n 12]` creates `flasks/<name>/{01..12}/`,
  each seeded identically (same seed → same agar; different `flask_id` mixed into
  the culture RNG so they diverge — like real replicates).
- `biotic flasks run <name> --ticks N [--tick 0] [--parallel 4]` runs them
  headless as subprocesses; `biotic flasks curve <name>` overlays their curves.
- `biotic live --vessel flasks/x/03` watches one.

## Acceptance criteria

- [x] Two vessels run simultaneously in one checkout without touching each other's files
- [x] `flasks new tide --n 3` produces three dishes with identical agar and different trajectories
- [x] `flasks curve` overlays population for all replicates on one plot
- [x] README updated for the vessel layout

## 2026-09-16

soma moved inside the vessel (config.SOMA = vessel/soma) so a flask is one self-contained dir; root soma/ and its git-tracked __init__.py removed (nothing imports the soma package). sterilize's old root-soma glob blocks deleted — the vessel iterdir loop now wipes vessel/soma too.

## 2026-09-16

Divergence source is the per-flask salt on the dish RNG (f'{seed}::{flask}::dish') and culture RNG; agar RNG (_make_agar, f'{seed}::agar') is left unsalted so replicates share agar exactly. flask='' keeps the exact legacy keys byte-for-byte (determinism pin in test_flasks). Registry RNG intentionally NOT salted: strain ids are sha1(n:source), not RNG-derived, and keeping the ancestral lineage identical is the faithful Lenski analogue.

## 2026-09-16

flasks default dormant, no spend (item authorizes none). flasks.new founds with a forced-dormant mind; flasks run's child env BLANKS OPENROUTER_API_KEY/BIOTIC_API_KEY/BIOTIC_BASE_URL rather than deleting them, because the child's own _load_dotenv would setdefault a deleted key back from .env. Awake replicate runs are a later item.

## 2026-09-16

Vessel is a runtime choice: config._paths(vessel) is the single source of truth; use_vessel() reassigns the module globals, vessel_scope() does it for a with-block. Sound because every module reads config.<NAME> at call time (no by-value imports). Single-process only — replicates run as separate PROCESSES (SIGALRM cell budget is main-thread-only; config.* is process-global). conftest repointed to config._paths(v), which adds FLASK_FILE and moves SOMA to v/soma.

## 2026-09-16

AC#1 'simultaneously' can't be proven deterministically without flakiness; the test proves the property that matters — running one vessel writes only its own dir and leaves every sibling at tick 0 with no curve, plus config globals restored around the scoped run. AC#2 divergence tested over a 70-tick population SERIES plus distinct inoculation coords (not one coarse final count), which diverge from tick 0.

## 2026-09-16

cli_reference.py was NOT changed; it renders only top-level subcommands, so the flasks new/run/curve flags do not appear in the generated CLI reference (the 'flasks' entry shows the fcmd choices). docs/flasks.md is the authoritative reference for them. The default subprocess runner is smoke-tested by hand (biotic flasks new/run/curve with real processes) and its argv + mind-off child env are pinned in test_flasks; it is not run as real processes in the suite.

## 2026-09-16

Env quirk (pre-existing, not introduced): the worktree lives under .worktrees/, a hidden dir ruff skips during traversal, so 'scripts/task check' ruff format/lint print 'No Python files found' and pass trivially in the worktree. Verified format+lint clean by running ruff on copies outside the dot-path (34 files). CI runs in a normal path and will lint for real.
