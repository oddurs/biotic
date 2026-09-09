---
id: 45
title: 'Growth curve: pin the header and sharpen docs/curve.md'
type: chore
status: done
milestone: dish
assignee: Oddur Sigurdsson
depends_on:
- 3
created: 2026-09-09
updated: 2026-09-09
priority: p3
effort: s
area: docs/curve.md, tests/test_metrics.py, bio/culture.py
---

## Problem

Item 0003 shipped the diversity and turnover columns. A review of what shipped
found nothing that breaks a measurement, but four small things worth a pass:
the test that pins the curve header pins only the first nine names to a
literal, so the order of the new nine, which docs/curve.md promises is stable,
is unguarded; `mean_gen` reads as cell doublings to a microbiologist when it is
lineage depth; the note on `mutations_ready` says two replays "differ in it and
nowhere else", which is only true under 0037's exact replay; and the
`make_culture` fixture's docstring says the mutagen thread never starts, which
`test_run_reports_diversity_in_its_progress_line` contradicts.

## Proposal

- Pin all eighteen column names as a literal in `tests/test_metrics.py`.
- docs/curve.md: define `mean_gen` as lineage depth; name `dominance` as the
  Berger–Parker index; say what four decimals resolve in `pheromone`; reword
  the replay caveat.
- Fix the fixture docstring, and have the `biotic run` test show that the
  dormant mutagen thread does not outlive the run.
- `Culture.snapshot()` takes `nutrient` from the metrics row instead of
  reading the agar twice per frame.

No physics, membrane, prompt or schema change; no changelog entry.

## Acceptance criteria

- [x] The suite fails if any of the eighteen curve columns is renamed or reordered
- [x] docs/curve.md defines `mean_gen`, names the Berger–Parker index, states the `pheromone` resolution, and the replay caveat no longer says "nowhere else"
- [x] `tests/conftest.py` says when the mutagen thread starts, and a test proves it exits under a dormant mind

## 2026-09-09

Minted as 0042 by cairn new and renumbered to 0045 by hand (front-matter id and filename) because 0042, 0043 and 0044 already exist on the unmerged test/membrane-physics-suite branch; a duplicate id at merge time would need cairn renumber, a gap costs nothing.

## 2026-09-09

mean_gen: Strain.generation is parent.generation + 1 at Registry.new(), so it counts mutated divisions between a strain and the founder, not cell doublings. A microbiologist reads 'generation' as doublings, so docs/curve.md now defines it. The vitals label 'gen' stays.

## 2026-09-09

Replay caveat: 'two replays can differ in mutations_ready and nowhere else' was true only under 0037's exact replay of admitted genomes at their original ticks. Without one, the wall-clock pool decides when the first variant is taken and every column diverges from there; and phase depends on where a run is resumed because the debounce is not persisted. docs/curve.md now says both.

## 2026-09-09

pheromone resolution, measured: injecting 0.2 at one tile every tick on a 72x34 dish (1928 tiles, decay 0.06, diffusion 0.10) settles the mean at 0.00112 by tick 100; 0.05 every tick at 0.00041; a genome that eats and emits 0.2 holds 0.0011 for 400 ticks. A single emission of 0.2 reads 0.0001, of 0.05 reads 0.0000; the threshold is 0.0964 (0.00005 x 1928). A genome that only emits starves before tick 50, which is why a first attempt at the measurement showed decay, not signalling.

## 2026-09-09

snapshot() now takes nutrient from the metrics row it already computes; it read the agar twice per frame. Same value, one pass; test_snapshot_reads_the_agar_once pins that the two agree.

## 2026-09-09

The in-place widening was trialled on a copy of the owner's real 0.1.0 curve (123 lines, 122 rows) in a scratch directory: 9 columns added, 122 rows of 18 cells, typed rows identical before and after, a second reconcile a no-op, an append reads back. The original was copied to vessel/curve.csv.0.1.0 beside it before the first live run from main; vessel/ is ignored by git.

## 2026-09-09

Watch, not fixed here: Culture.step() runs registry.update() (peak, extinct_at) outside c.lock while the renderer reads those fields under it; attribute writes cannot raise, so at worst extinct is one frame stale. And a process killed between open and close in curve.append() can leave a partial last line that the next append glues a row onto; one buffered write per ten ticks, the same exposure the 0.1.0 writer had. Both are behaviour, not docs.
