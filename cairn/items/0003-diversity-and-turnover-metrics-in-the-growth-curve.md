---
id: 3
title: Diversity and turnover metrics in the growth curve
type: feature
status: done
milestone: dish
assignee: Oddur Sigurdsson
created: 2026-09-08
updated: 2026-09-08
priority: p0
effort: s
area: bio/dish.py, bio/culture.py
---

## Problem

`curve.csv` records population and strain count. Neither can answer the
project's central question — is novelty ongoing or does the dish converge? —
because ten strains at 1 cell each and one strain at 90% look identical in
`strains`. The research claim in CONCEPT.md needs diversity, dominance and
turnover, sampled at the same cadence as everything else.

## Proposal

Add columns to `vessel/curve.csv` every 10 ticks:

- `shannon` — Shannon diversity over the strain census, in nats
- `dominance` — share of the most common strain
- `mean_gen` — mean generation of living cells (how deep the lineage runs)
- `arisen` — cumulative strains ever created (novelty rate = its slope)
- `extinct` — cumulative extinctions
- `pheromone` — mean pheromone over the agar (are they signalling at all)
- `mutations_ready`, `mutations_taken` — supply vs. uptake of variants

Keep the header backward compatible: new columns appended, existing order kept.
`Dish` gets a `metrics()` method that returns the dict; `Culture._curve` writes it.
Show `shannon` and `dominance` in the vitals panel.

## Acceptance criteria

- [x] `curve.csv` has the new columns and an old file is still readable by `biotic curve`
- [x] A monoculture reports `shannon=0.0, dominance=1.0`
- [x] Vitals panel shows diversity next to the strain count

## 2026-09-08

Two layers: Dish.metrics() returns only what the dish knows (tick, population, strains, nutrient, pheromone, shannon, dominance, births, deaths incl. killed) so dish.py stays ignorant of the registry and the mind; Culture.metrics() merges phase, mean_gen, arisen, extinct, mutations_ready, mutations_taken from the registry and mutagen. snapshot()['metrics'] carries it to the eyepiece and status.

## 2026-09-08

mutations_taken is derived, not counted: strains with a parent. No new persisted state, monotone across resumes, equals the number of arose events. Until strains can arrive without a mutated division it equals arisen - 1 in every row; documented rather than dropped because 0040 already names it. 0040 must keep deriving it or persist its counter; 0015 can split it by origin.

## 2026-09-08

Old curve.csv is widened in place by one rule: target header = existing header + the COLUMNS it lacks, in COLUMNS order; rows padded with empty cells; rewritten via curve.csv.tmp then replace(), so a crash leaves the original. Unknown columns from a newer apparatus keep their place and are written empty. Reconciled once per process (fieldnames cached on the culture) and logged once as a curve event. Two processes appending to one vessel is unsupported and could interleave.

## 2026-09-08

killed added as a column (it was already counted in Dish.deaths, never written) so the ledger births - (starved + lysed + senescent + killed) = population - inoculum closes after an antibiotic disc; tested.

## 2026-09-08

No prompt change. The mutagen is still told strains=len(census) and not H or dominance: the observer does not grade (CONCEPT.md). config.py, membrane.py, mutagen.py, mind.py, prompts.py, strains.py, soma/ untouched.

## 2026-09-08

mutations_ready is the one wall-clock column: a 10-tick sample of the mutagen pool, filled by a background thread. 0037's 'identical curve.csv' criterion must exclude it until 0040's tick clock exists. docs/curve.md says to leave it out when comparing curves.

## 2026-09-08

Markers (drops, phase changes, extinctions, incubation gaps) stay in events.jsonl and are joined on tick; 0004, 0005, 0010, 0012 should not add marker columns. bio.curve.read(path) takes a path so 0006's flasks can read several curves; the default is config.CURVE resolved at call time, never bound at import.

## 2026-09-08

Acceptance criterion 1 says 'readable by biotic curve'; biotic curve is 0004. Met here by shipping the reader it will use, bio.curve.read(), tested against a verbatim nine-column file, plus the in-place widening tested end to end.

## 2026-09-08

Vitals: the value column is 33 cells at the default 120-column bench (side panel 48, chrome 4, label 10, gap 1). strains and diversity rows are 28 and 32 cells at worst (three-digit counts, dominance 100%, mean gen >= 10) and a test renders the panel at width 48 to prove they do not wrap. 0009 owns narrower benches. The maximum generation left the strains row; snapshot()['generation'] is kept for anything else that reads it.

## 2026-09-08

cmd_run's progress() now takes c.lock around snapshot(): metrics() iterates registry.strains, which _on_divide mutates inside d.step() under the lock, and the reporter thread read it unlocked before (latent 'dictionary changed size during iteration'). The final progress() after run() returns is outside any locked section, so the non-reentrant lock is safe. The lock is not fair: at --tick 0 a progress line may arrive late.

## 2026-09-08

Tests: an autouse conftest fixture redirects every config path to tmp_path, makes the Mind dormant (no key, invalid base URL), monkeypatches urllib.request.urlopen to fail, and asserts at teardown that the repository's vessel/curve.csv mtime did not change. Trajectory tests prove metrics() and snapshot() are inert: a watched dish and a bare dish share census, nutrient and RNG state after 100 ticks.
