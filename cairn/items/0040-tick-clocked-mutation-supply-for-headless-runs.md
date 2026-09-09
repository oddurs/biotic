---
id: 40
title: Tick-clocked mutation supply for headless runs
type: feature
status: planned
milestone: dish
depends_on:
- 2
created: 2026-09-08
updated: 2026-09-08
priority: p0
effort: m
area: bio/mutagen.py, bio/culture.py
---

## Problem

The mutagen is bound to the wall clock. `Mutagen.run` waits
`config.MUTAGEN_INTERVAL` seconds (default 12) between calls, on a daemon
thread the dish never waits on; a division that rolls a mutation takes from
the pool if a daughter is ready and otherwise queues a request and divides
faithfully. That is the right design for `biotic live`, where the observer is
watching at two ticks a second. It is the wrong design for `biotic run`.

At `biotic run --tick 0` the dish does roughly 500 ticks/s. One mutagen call
per 12 s is one call per ~6,000 ticks, so mutation supply per tick collapses
to near zero and almost every roll that succeeds finds an empty pool. Worse,
two runs at different tick speeds are not comparable at all: the effective
mutation rate is `MUTATION_RATE × P(pool non-empty)`, and that probability is
a function of CPU speed, endpoint latency and `--tick`. Every experiment item
in the roadmap — the parasitism protocol (0016), the citrate experiment
(0021), public goods and cheaters (0028), the model comparison, the write-up
(0038) — compares flasks, and a comparison whose mutation supply depends on
the machine it ran on is invalid before it starts.

## Proposal

A mutagen clock mode, so that in a headless run the supply of variants is a
function of ticks and budget and nothing else.

- `BIOTIC_MUTAGEN_CLOCK=wall|tick`, read in `bio/config.py` as
  `MUTAGEN_CLOCK`. The default depends on the command: `biotic live` uses
  `wall` (the observer's experience must never block on the network),
  `biotic run` and anything else headless (`flasks run`, trials) use `tick`.
  `biotic run --clock wall` and `biotic live --clock tick` override; the
  choice is persisted into `dish.json` so a resumed run keeps it.
- `wall` mode is exactly today's behaviour: `MUTAGEN_INTERVAL` seconds between
  calls, a background thread, the dish never waits.
- `tick` mode:
  - The minimum interval between mutagen calls is
    `BIOTIC_MUTAGEN_EVERY_TICKS` ticks (`MUTAGEN_EVERY_TICKS`, default 40),
    measured on `dish.tick`, not `time.time()`. The `boost` from
    `biotic drop mutagen` divides the interval as it divides the wall
    interval today.
  - When `Culture._on_divide` rolls a mutation and `Mutagen.take` returns
    nothing, and at least `MUTAGEN_EVERY_TICKS` ticks have passed since the
    last call, the dish makes a synchronous call to the mutagen for that
    strain (`Mutagen.mutate_now(strain)`) and, if the result passes the
    membrane, the daughter is born from it in the same division. At most one
    blocking call per interval; further rolls inside the interval divide
    faithfully as they do now, and queue a request so the background thread
    can keep the pool warm between blocking calls.
  - The blocking call is bounded by the budget item (0002): an exhausted
    budget means no call and a faithful division. On `MindError` the cell
    divides faithfully and the backoff from 0002 applies, expressed in ticks
    (`MUTAGEN_EVERY_TICKS × 2, ×4, …`, capped at 50 intervals) so a dead
    endpoint does not stall a fast run.
  - The `_pick` spontaneous-mutation path (keep the pool warm for the
    dominant strain after `5 × MUTAGEN_INTERVAL` idle) is also measured in
    ticks in this mode: `5 × MUTAGEN_EVERY_TICKS` since the last call.
  - Horizontal gene transfer (0014) requests daughters through the same
    path, so its supply is tick-clocked too; this item only has to leave the
    seam (`mutate_now` takes an optional donor source) rather than implement it.
- Counters. `Mutagen` gains `attempted` (calls made, whatever the outcome),
  `viable` (passed the membrane and entered the pool, or were taken directly
  by a blocking call) alongside the existing `produced` and `nonviable`;
  `Culture` counts `taken` (divisions that actually produced a new strain).
  `curve.csv` gains three cumulative columns, `mutations_attempted`,
  `mutations_viable`, `mutations_taken`, appended after the columns from
  0003 (`mutations_ready`, `mutations_taken` there become `mutations_ready`
  and this item's `mutations_taken`; coordinate so the header is written
  once, in one order, and old files stay readable by `biotic curve`).
- `biotic run` prints the mode and interval on start
  (`mutagen clock: tick, every 40 ticks`), `biotic status` shows it under
  the mutagen line, and the vitals panel shows `tick` or `wall` next to the
  mutagen state.
- `docs/experiments.md` (new) explains why the two modes exist, that `live`
  and `run` default differently, when to set `BIOTIC_MUTAGEN_EVERY_TICKS`
  and what a given value means in attempts per flask
  (`ticks / every_ticks`, minus backoff), and that any two flasks being
  compared must share the mode and the interval. README gains one sentence
  pointing there from the `biotic run` description.

## Acceptance criteria

- [ ] Two 5,000-tick headless runs with the same seed and a fake deterministic `Mind` (monkeypatched `think`, no network), one at `--tick 0` and one at `--tick 0.05`, produce the same number of mutation attempts within ±5%
- [ ] In `wall` mode a `Mind` whose `think` sleeps 2 s does not change tick duration: median tick time in a 200-tick `live`-mode run is within 10% of the same run with a dormant mind
- [ ] In `tick` mode with `BIOTIC_MUTAGEN_EVERY_TICKS=40`, a 4,000-tick run makes at most 100 calls plus the spontaneous-mutation allowance, and never two calls fewer than 40 ticks apart
- [ ] A `MindError` on every call in `tick` mode still lets the culture grow (population after 2,000 ticks matches a dormant-mind run within noise) and produces backoff in ticks, not seconds
- [ ] `curve.csv` has `mutations_attempted`, `mutations_viable`, `mutations_taken`; `biotic curve` reads a file written before this change
- [ ] `biotic run` prints the mode; `biotic status` shows it; `dish.json` carries it across a resume
- [ ] `docs/experiments.md` exists and explains the two modes and when to use which; README points to it
