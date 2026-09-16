---
id: 4
title: '`biotic curve` — plot a run'
type: feature
status: done
milestone: dish
assignee: Oddur Sigurdsson
depends_on:
- 3
created: 2026-09-08
updated: 2026-09-16
priority: p1
effort: m
area: bio/__main__.py
---

## Problem

The growth curve is the primary output of an experiment and there is no way to
look at it except opening a CSV. A microbiologist reads the plate *and* the
curve.

## Proposal

`biotic curve [--png out.png] [--cols population,shannon,nutrient] [--since TICK]`

- Default: an ASCII plot in the terminal using `rich` — population as the main
  trace, strain count as a second axis, phase transitions marked as vertical
  ticks with labels (lag / log / stationary / death), interventions marked with
  the drop glyph.
- `--png` renders the same with matplotlib *if installed* (optional dependency
  group `[plot]` in pyproject; do not make it a hard requirement — the organism
  stays a one-dependency thing).
- Reads `vessel/curve.csv` and `vessel/events.jsonl` (for phase and drop markers).

## Acceptance criteria

- [x] `biotic curve` on the current dish prints a plot with phase markers
- [x] `biotic curve --png` produces a file when matplotlib is present and says how to install it when not
- [x] Works on a curve with 50 rows and with 50,000 rows (downsamples)

## 2026-09-09

From 0003/0045: read the curve through bio.curve.read(path); rows from a nine-column file carry None in the new columns. Markers (drops, phase changes, extinctions, incubation gaps) come from events.jsonl joined on tick, not from curve columns. docs/curve.md names dominance as the Berger-Parker index and defines mean_gen as lineage depth; use those words in axis labels.

## 2026-09-16

From 0005: after a dish revive, join events on (branch, tick), not on tick; the curve's branch column is 0 until the first revive and one more after each, and an event's branch is the number of revived dish events (the ones with from and was) before it in events.jsonl. The earlier advice to split the file where tick decreases is withdrawn: a forward revive leaves tick monotone. A plot is per branch, or of the last branch by default; rows from a file older than the column read None there and are branch 0.

## 2026-09-16

Small multiples, no dual axis: the first --cols column is the tall panel, each further column a half-height panel under it, all on one tick axis. population (0-2000), shannon (0-3) and nutrient (0-1) cannot share a right-hand axis honestly. Default --cols population,strains is the proposal's picture.

## 2026-09-16

The terminal plot is a braille canvas in bio/plot.py emitted as rich.text.Text: rich 15.0.0 has no plot primitive, braille needs no dependency, it strips to plain text when piped, and every glyph used (braille, the marker glyphs, the rule and axis) is one cell wide by rich.cells.cell_len; a test pins that. Consecutive points are joined by Bresenham on the dot grid, so a stretch with no rows is bridged by a straight line; docs say so.

## 2026-09-16

Markers come from events.jsonl through curve.events(), which stamps every event with its branch, and are joined on (branch, tick); the last branch by default, --branch N for another. The revived event that opens a branch is logged at the sample's tick, before the branch's first row, so it is drawn at the left edge unless --since is past its tick (pinned by a test). Markers are positioned by tick on the axis, not joined to a row: events fall between rows.

## 2026-09-16

Deviation from the plan: curve.events() follows the branch an opener carries (the culture stamps it after the swap) rather than counting openers, and only counts when an opener has none; on every log the culture writes the two agree, and when they would not, following the opener is what matches the rows. An event whose branch is null is stamped like one with no branch key.

## 2026-09-16

Phase events now carry phase=raw beside the message (one keyword on a rare log call, no tick-path cost). Older logs fall back to parsing 'entered (\w+) phase' from msg. The first believed phase is never logged (if self.last_phase is not None), so the segment before the first rule has no name; docs/curve.md says so.

## 2026-09-16

Marker kinds: phase -> a rule through the main panel with the name beside it; drop -> the alembic glyph in a marker row under the tick labels; revived -> the revive glyph (dish revive at the branch's left edge, a strain revive at its tick; took / did not take verdicts are not markers); gap -> an ellipsis, registered now so 0010 only has to log an event of kind gap. Extinctions and arose are not drawn: a long run has thousands and they are the extinct/arisen columns (--cols extinct,arisen). Glyphs for phase, drop and revived equal tui.ICONS; a test pins it without plot importing tui.

## 2026-09-16

Phase names are drawn to the right of the rule, or to the left when the right has no room; a name that would touch another name, cross another rule or leave the canvas is dropped and only the rule drawn. On a 50k-tick run with hundreds of transitions the main panel shows many unnamed rules; a --no-phases flag or a phase-band panel may be wanted later.

## 2026-09-16

Deviation from the plan: each panel's label is a line of its own above the canvas, not written over the top canvas row, so no trace cell is covered by it (the top row carries the phase names). A middle y label that repeats an end label is left out; a flat series gets a unit of headroom so it sits on the floor under a top label of 1.

## 2026-09-16

Downsampling is min and max per dot column (2*cw buckets), bucketed by tick over [x0, x1], not by row index; the first and last raw points are always kept; a series that already fits is returned unchanged. A one-row crash or spike therefore survives at full height. The PNG plots every row. Pure and O(n): 50,000 points into 200 buckets return at most 402.

## 2026-09-16

The real-matplotlib test was run locally after uv sync --extra plot in the worktree: it passes and the PNG was looked at (two axes, phase rules with rotated names, suptitle). uv run --locked syncs inexactly by default, so the extra survives scripts/task check.

## 2026-09-16

biotic curve reads only curve.csv, events.jsonl and seed.txt, never constructs a Culture, never touches dish.json, the inbox or incubator.lock (a test holds the flock and records every mtime in the vessel). A trailing curve row whose tick does not climb past the previous row's is a torn line and is left out; a torn line of events.jsonl is skipped. A torn numeric cell that still parses ('12' of '123') cannot be told from a whole one and shows a smaller value for that instant: documented, not fixed; the write is one small append.

## 2026-09-16

Known limit, documented in docs/curve.md: a vessel whose events.jsonl holds dish revives from before the branch column existed would have rows reading branch 0 while events count 1. No such vessel exists that we know of.

## 2026-09-16

Measurements: the 500-tick test culture (seed test, 24x12, dormant mind) steps in 0.21 s with phase events at 60 log, 189 death, 419 stationary and writes 50 rows; the 50,000-row test (write with csv.writer, read, render at 100 columns) takes about 0.6 s wall; the whole suite is 14.6 s with matplotlib installed. curve.read of 50k rows is 0.16 s.

## 2026-09-16

scripts/task docs regenerated web/apps/site/src/content/docs/reference/cli.mdx (it is prettier-ignored), so scripts/task check runs the web half for this branch; expect the slower gate.

## 2026-09-16

Neighbours: 0006 - Panel.traces is a list; a flasks overlay is one Trace per flask through plot.render/plot.png, and curve.read(path)/curve.events(path) take paths. 0007 - curve.events() is the branch-aware log reader; phase events carry phase. 0010 - log an event of kind gap (with msg), not a curve row; it is a marker kind already; add an icon to tui.ICONS. 0036 - reuse plot.figure() for the HTML timeline. 0040 - a renamed column must update plot.LABELS; test_plottable_columns_and_labels_use_the_docs_words fails otherwise.

## 2026-09-16

The --png flag writes the file and prints 'wrote <path>', nothing else. matplotlib is the optional extra plot = [matplotlib>=3.8] (height_ratios in subplots needs >= 3.6); uv lock pulled numpy (pinned per Python version, so 3.11 through 3.13 resolve), pillow, fonttools, kiwisolver, contourpy, cycler, pyparsing, python-dateutil, packaging, six into uv.lock; inert for CI, which runs uv run --locked with no extras, so the real-matplotlib test skips there. Every string handed to matplotlib has $ escaped: the seed is free text and mathtext would parse it.
