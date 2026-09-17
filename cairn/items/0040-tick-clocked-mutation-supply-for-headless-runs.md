---
id: 40
title: Tick-clocked mutation supply for headless runs
type: feature
status: done
milestone: dish
assignee: Oddur Sigurdsson
depends_on:
- 2
created: 2026-09-08
updated: 2026-09-16
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

- [x] Two 5,000-tick headless runs with the same seed and a fake deterministic `Mind` (monkeypatched `think`, no network), one at `--tick 0` and one at `--tick 0.05`, produce the same number of mutation attempts within ±5%
- [x] In `wall` mode a `Mind` whose `think` sleeps 2 s does not change tick duration: median tick time in a 200-tick `live`-mode run is within 10% of the same run with a dormant mind
- [x] In `tick` mode with `BIOTIC_MUTAGEN_EVERY_TICKS=40`, a 4,000-tick run makes at most 100 calls plus the spontaneous-mutation allowance, and never two calls fewer than 40 ticks apart
- [x] A `MindError` on every call in `tick` mode still lets the culture grow (population after 2,000 ticks matches a dormant-mind run within noise) and produces backoff in ticks, not seconds
- [x] `curve.csv` has `mutations_attempted`, `mutations_viable`, `mutations_taken`; `biotic curve` reads a file written before this change
- [x] `biotic run` prints the mode; `biotic status` shows it; `dish.json` carries it across a resume
- [x] `docs/experiments.md` exists and explains the two modes and when to use which; README points to it

## 2026-09-09

From 0003/0045: mutations_taken is derived from the registry (strains with a parent), not counted; keep deriving it or persist your counter so it stays monotone across resumes. Append mutations_attempted and mutations_viable after the existing eighteen columns; tests/test_metrics.py pins the full header as a literal (NEW_HEADER), so extend it there. Until this item lands the slope of arisen is wall-clock bound and not comparable across machines or --tick values.

## 2026-09-16

From 0005: curve.COLUMNS has nineteen columns now, the last being branch (a coordinate for revives). Append mutations_attempted and mutations_viable after branch and extend NEW_HEADER in tests/test_metrics.py accordingly.

## 2026-09-16

Tick mode is synchronous only: the thread exits at once on the tick clock; no pool, no queue, no spontaneous path. Every call is Mutagen.mutate_now(strain) from the dish thread at a division that rolled while the slot was open. A warm-pool thread under a shared tick interval would either make a second call per interval or race the dish, with a winner that depends on --tick and CPU speed, and an asynchronous reply lands latency-dependent ticks later — the machine-dependence the item exists to remove. With one caller, attempt ticks, birth ticks and counts are a function of (seed, replies, membrane verdicts). The item's 'spontaneous allowance' in criterion 3 is exactly zero.

## 2026-09-16

Clock precedence: --clock > BIOTIC_MUTAGEN_CLOCK > the --clock the dish remembers > by command (live: wall, anything else: tick). Only the flag is remembered (culture.clock in dish.json); the environment variable is per-process configuration like BIOTIC_MUTATION_RATE and is never written into the dish. So biotic live after a headless run stays on the wall clock, biotic run --clock wall survives a resume (the criterion), and a .env set for a protocol applies to every command in that checkout without leaving residue in the flask. The remembered flag and the last-run record (clock_used, every_ticks_used) belong to the vessel like branch: revive() carries them forward over the sample's.

## 2026-09-16

BIOTIC_MUTAGEN_EVERY_TICKS is per-process configuration, clamped to >= 1, never restored from dish.json. dish.json carries a record of the last run (clock_used, every_ticks_used) for biotic status, plus one visible mind event at every run start ('mutagen clock: tick, every 40 ticks', with clock and every_ticks in its data) as the durable record. The item's proposal both called it per-process and persisted it; that contradiction is resolved toward per-process.

## 2026-09-16

Backoff in ticks; Retry-After is a wall-clock floor. On the tick clock a failed call closes the slot for 2·every, 4·every, … <= 50·every ticks (backoff(failures, base=2e, cap=50e)); a Retry-After additionally sets retry_wall_at = time.time() + min(ra, RETRY_AFTER_MAX), during which no attempt is made and none is counted. A dead endpoint must not stall a fast run (the item's words), but an endpoint that names a wait is stating its own constraint, and at --tick 0 a tick-only cap of 2000 ticks is a retry every ~4 s. This is the only wall-clock input on the tick path and it exists only under failure, where reproducibility is already gone because the replies differ. Not persisted: a resumed process asks again. failures is not persisted either (as on the wall clock), but retry_at_tick is, so a resumed dish waits out the schedule it was in and a later failure starts at 2 intervals again.

## 2026-09-16

produced is renamed viable. On the wall path produced counted daughters admitted into the pool, which is exactly the item's viable ('passed the membrane and entered the pool, or were taken directly by a blocking call'). Two counters equal on one path and one always zero on the other is a trap. attempted counts calls that got an answer or an error (MindError); Dormant and Exhausted are raised before any request and do not count. attempted, viable and nonviable are persisted in the culture blob so the cumulative curve columns stay monotone across resumes; a revive restores the sample's counters (coordinates of the timeline, like arisen); mind.calls stays the money ledger and includes genesis.

## 2026-09-16

The tick schedule is persisted (last_call_tick, retry_at_tick in the culture blob; last_call_tick is null for -inf, the open-at-once state of a dish that never called). Without it every resume opens the slot at once, the first roll after a load calls early, and every later attempt tick shifts: a resumed run would not be the twin README promises, and 0037's replay needs the schedule to be state. tests/test_clock.py::test_the_tick_schedule_and_counters_survive_a_resume shows a 600+600 run has the attempt ticks and the dish of one unbroken 1200. On the wall clock state_dict carries the loaded values forward unchanged so a live peek does not erase a headless run's schedule.

## 2026-09-16

run() primes mutagen.context before the first tick on the tick clock only, so a blocking call in the first ticks after a resume is prompted with the real census and phase (step() refreshes it only every third tick, after the step). Priming on the wall clock too, as first planned, changed wall behaviour: _pick's spontaneous path only needs a census and last_call = 0.0, so the thread called the mind at its first turn — on close(), in a one-tick run — and tests/test_budget.py::test_ledger_catches_up_from_the_log_after_a_hard_kill caught it (a third call after the save). The wall path is left exactly as it was: same calls, same order.

## 2026-09-16

Ctrl-c inside a blocking call ends the run at a tick boundary: _on_divide catches KeyboardInterrupt from mutate_now, the division is faithful, Culture._interrupted is set and run() raises KeyboardInterrupt after step() returns, inside its try/finally, so the dish saved on the way out is whole and its resumed twin equals a dormant dish stepped to the same tick. The interrupted attempt is not counted (attempted increments after think returns); last_call was already set, so the slot stays closed for one interval after a resume, which errs on the side of the interval. A second interrupt mid-tick behaves as before.

## 2026-09-16

Boost expiry fixed in Culture.step(): boost returns to 1.0 once dish.tick >= boost_until, on both clocks and in dish.json. Before, drop mutagen set boost = 6.0 forever: _on_divide used boost_until for the rate but _cycle divided the wall interval by boost for the rest of the run (2 s instead of 12 s) and state_dict persisted 6.0. This item makes boost divide the tick interval too, so the expiry had to be real. Changelog under Fixed; tests/test_freezer.py's boost round trip compares twins before boost_until and stays green.

## 2026-09-16

The vitals show the clock as the label of the mutagen's second row (the dim label column: 'wall 12 viable · 3 nonviable'), not inside the value. The plan put 'wall · ' in the value; at the narrowest side panel (80x24, 36 columns, value column 23 cells) that row is the one mutagen row that does not wrap today (22 cells with zero counts), and one more wrapped row folds the side panel into the strip — docs/eyepiece.md promises the side panel at 80x24 and tests/test_tui.py pins Fit(1, True, 0, 1, 40, 18) with zero slack. The label costs no width. On the tick clock the state row shows 'every 40 ticks' where 'N ready · M queued' would be: there is no pool there and the figures are structurally zero; the strip shows 'tick' in place of '0 ready' for the same reason. The retry countdown reads 'retry in 80 ticks'.

## 2026-09-16

Which strain gets mutated shifts on the tick clock: the wall path served the oldest queued request (one per strain, so a rare strain was served as often as the dominant one); the tick path serves whichever strain's division rolled first after the slot opened, i.e. in proportion to division share. Stated in docs/experiments.md. Not a defect, but a live flask and a run flask are not the same experiment in that respect; a rare-strain-favouring pick would be a different design.

## 2026-09-16

Test lever: on the 24x12 test dish under the built-in founder there are ~230 births in the first 200 ticks and then ~10 per 200 ticks (measured), so at the default 6 % a roll is rarer than a 40-tick interval and the interval is not what bounds attempts. The tests about the interval set culture.mutation_rate = 1.0 (every division rolls) so the interval is the binding constraint; the roll RNG is drawn once per division whatever the rate, so the dormant twins in those tests still walk the same path. At 72x34 births run 40-170 per 200 ticks after the bloom, so at 6 % an attempt every ~45-70 ticks is what a real run sees; docs/experiments.md says attempts depend on the division rate and to report mutations_attempted rather than assume ticks / every_ticks.

## 2026-09-16

Finished the interrupted build. Reconciled with main (already at origin/main tip; #27 budget, #28 freezer, #31 curve-widening all in the base). Full scripts/task check green: 363 pytest, 15 web unit, 14 e2e, uv build + astro build. Two formatting reconciliations were needed from the interrupted state: a stray blank line splitting the CHANGELOG ### Changed list, and configuration.mdx's env table was not re-aligned after two rows were added (prettier --check flagged it; scripts/task fmt fixed it). cli.mdx is generator-current (scripts/cli_reference.py --check passes).

## 2026-09-16

Watch items for later experiment items (0015/0016/0021/0028/0038/0041): (1) criterion 3's '>=40 ticks apart' invariant holds only with no active boost. drop mutagen divides interval() by 6 on the tick clock too, so spacing drops toward every/6 for the boost's 300 ticks; test_boost_divides_the_tick_interval_and_expires demonstrates gaps of 7..<40 while boosted and >=40 after expiry. A protocol that assumes strict 40-tick spacing must not drop the mutagen. (2) attempted/viable/nonviable are timeline coordinates: revive() restores them from the sample blob (like arisen/branch), and Mutagen.reset() on a dish swap does NOT zero them, so a revive --into current carries the previous dish's cumulative counts forward by design; a fresh biotic seed starts a new Mutagen at 0. (3) On a hard kill up to ~150 ticks of counters and schedule are lost with the dish, same as arisen.

## 2026-09-16

Correction to the earlier 'already at origin/main tip' note: the branch was three commits behind (#32 curve plot, #33 naturalist+role, #34 me.memory at write time). Rebased onto them. Conflicts resolved by union in culture.py (naturalist baseline + clock/counter/schedule state coexist in state_dict/restore_state/revive/run) and __main__.py (naturalist import + CLOCKS/clock_words). Re-added role='mutagen' to _ask and kept #33's role param on Mind.think; test_budget asserts both role and the produced->viable rename. CHANGELOG: removed a stray second '### Fixed' that split '### Changed'; the drop-mutagen boost bullet now sits in the one real Fixed section. #34's dish.step calls _apply (hence on_divide/mutate_now) outside the CELL_TIME_BUDGET block, so the synchronous tick call is unaffected. Integration fix: the two new curve columns needed plot.LABELS entries (test_plot pins column/label parity). Full scripts/task check green: 440 pytest, 15 web unit, 14 e2e, uv+astro build.
