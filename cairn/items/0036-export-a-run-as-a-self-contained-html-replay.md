---
id: 36
title: Export a run as a self-contained HTML replay
type: feature
status: planned
milestone: instrument
depends_on:
- 5
- 7
created: 2026-09-08
updated: 2026-09-08
priority: p1
effort: l
area: bio/export.py
---

## Problem

A run lives in a terminal on one machine. There is no way to show someone a
dish without them installing it.

## Proposal

- `biotic export <out.html>`: one file, no network. Contains the curve, the
  field notes, the fossil record (collapsible genomes with lineage), the
  trophic web, and a *replay* of the dish from the freezer snapshots with
  in-between frames interpolated from the events log (cells fade in/out;
  exact positions only at snapshot ticks — say so in the UI). Scrubber over
  ticks; phase bands on the timeline; drops marked.
- Under 5 MB for a 50k-tick run with 2k-tick freezes.

## Acceptance criteria

- [ ] Opens offline in a browser; scrubber works; notes and fossils readable
- [ ] Size bound met on a real run
