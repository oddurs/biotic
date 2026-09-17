---
id: 49
title: Let replicate flasks opt into spending on the mind
type: feature
status: planned
milestone: substrates
created: 2026-09-17
updated: 2026-09-17
priority: p1
effort: s
area: bio/culture.py, bio/__main__.py
---

## Problem

`biotic flasks run` blanks the OpenRouter key in every child process. `flasks._child_env`
sets `OPENROUTER_API_KEY`, `BIOTIC_API_KEY` and `BIOTIC_BASE_URL` to empty strings before
spawning each `biotic run --vessel <dir>` subprocess, so `Mind.awake` is false in every
replicate and the mind never runs. That was the right default for the flasks item (0006,
which authorized no spend), but it means a replicate can never spend on the mind or vary
through the LLM mutagen — a flask set can only ever run the offline `random` arm or the
built-in fallback founder.

Both biotic-env experiments paid for this. The model comparison (0041) and the tierra
plateau write-up could not use `flasks run` at all: to get real mutation they founded the
set with `biotic flasks new` and then launched one `biotic run --vessel <dir> --clock tick
--mutagen llm --budget 0.60` process per flask by hand, orchestrated outside the tool.
docs/experiments.md says so in as many words ("`biotic flasks run` is *not* usable here
because it blanks the API key in every child"), and its `flasks run comp-llm` example a few
sections earlier is aspirational — it founds an `llm` set but the run that follows spends
nothing. The instrument write-up (0038) will need many flasks with a live mind and hits the
same wall.

## Proposal

Add an opt-in `--spend` flag to `biotic flasks run` (and `BIOTIC_FLASKS_SPEND=1` for the
per-process form) that carries the real key into the child processes instead of blanking it,
guarded by a per-flask budget so a stray `flasks run` can never drain the balance.

- `flasks.run(...)` gains a `spend: bool = False` parameter. When false (the default),
  `_child_env` behaves exactly as today — the three key/URL vars are emptied and no child
  spends. When true, `_child_env` leaves the inherited `OPENROUTER_API_KEY` /
  `BIOTIC_API_KEY` / `BIOTIC_BASE_URL` untouched so the child's `Mind` wakes.
- The guard: spending requires a per-flask budget. A budget is present when either `--budget
  X` is passed to `flasks run`, or every flask's dish already remembers a budget (the value
  `biotic run` persists to `dish.json`, the same one `--budget` sets). `flasks run --spend`
  with no `--budget` and at least one flask that remembers no budget is refused, exits
  non-zero, and names the flasks that are missing one. `--budget X` is threaded into each
  child's argv as `biotic run ... --budget X`, so the existing per-dish cap enforced by the
  budget/price cache (0002) applies unchanged — `--spend` never widens a cap, it only
  unblocks the key.
- `--spend` without `--budget` is the only refusal; `--spend --budget X` and plain `flasks
  run` (no spend, no key) both proceed. `BIOTIC_FLASKS_SPEND=1` is equivalent to `--spend`;
  the flag wins when both are set.
- The default is unchanged in every respect: `flasks run` and `flasks run --budget X`
  without `--spend` still blank the key and spend nothing, so no existing invocation starts
  spending. The child argv already carries `--clock`/`--mutagen` from the dish's remembered
  settings, so a set founded with `flasks new --mutagen llm` varies through the mind once the
  key is present.

Wiring:

- `bio/flasks.py`: `_child_env(spend: bool)`, `run(..., spend=False, budget=None)`, the
  per-flask budget check reading each `dish.json`, and `--budget` threaded into `_argv`.
- `bio/__main__.py`: `--spend` (`store_true`) and `--budget` (`type=float`) on the `flasks
  run` parser, `BIOTIC_FLASKS_SPEND` read as the default for `--spend`, and the refusal
  message in `cmd_flasks_run`.
- docs/flasks.md and the `flasks run` command help gain the `--spend`/`--budget` contract and
  the "default spends nothing" guarantee.
- docs/experiments.md: correct the aspirational `flasks run comp-llm` example to
  `flasks run comp-llm --spend --budget 0.60`, and update the model-comparison paragraph that
  says `flasks run` "is *not* usable here" to note that `--spend` now makes it usable.
- CHANGELOG.md: an `### Added` entry under `## [Unreleased]`.

## Acceptance criteria

- [ ] `flasks run --spend --budget X` carries the key into the children: a test with a
      fake/dormant Mind and an injected runner asserts the child env has a non-empty
      `OPENROUTER_API_KEY` only under `--spend`, and an empty one without it.
- [ ] `flasks run --spend` with no `--budget` and no remembered per-flask budget exits
      non-zero with a message naming the flasks that lack a budget; `--spend --budget X`
      proceeds.
- [ ] Plain `flasks run` (and `flasks run --budget X` without `--spend`) still blanks the key
      and spends nothing — asserted by the same env test.
- [ ] `--budget X` under `--spend` reaches each child as `biotic run ... --budget X`, so the
      per-dish cap is enforced (asserted on the built argv).
- [ ] `BIOTIC_FLASKS_SPEND=1` is equivalent to `--spend`.
- [ ] docs/flasks.md, docs/experiments.md and the `flasks run` help are updated; the
      aspirational example is corrected.
- [ ] CHANGELOG entry under `## [Unreleased] / ### Added`.
