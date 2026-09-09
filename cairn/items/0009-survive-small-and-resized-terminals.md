---
id: 9
title: Survive small and resized terminals
type: feature
status: planned
milestone: dish
created: 2026-09-08
updated: 2026-09-09
priority: p2
effort: s
area: bio/tui.py
---

## Problem

The dish is sized to the terminal at seed time. Watch it later from a smaller
window and the layout clips silently; resize mid-run and the frame tears.

## Proposal

- On each frame, compare `console.size` to what the layout needs. If the dish
  does not fit, render it at half resolution: 2×2 tiles → one glyph, coloured by
  the dominant strain in the block, `▪` when only one cell, `●` when ≥2. Show a
  `½` badge in the agar panel title.
- Below ~80 columns, drop the side panel and put a one-line vitals strip above
  the log instead.
- Handle `SIGWINCH` by letting `rich.Live` re-measure (it does) and by
  recomputing the layout in `build()` every frame — already the case; verify.

## Acceptance criteria

- [ ] A dish seeded at 150×50 is watchable at 100×30 with the ½ badge
- [ ] Resizing during `biotic live` never raises and settles within one frame

## 2026-09-09

From the 0003 review: the events deque is appended by the main and mutagen threads and iterated by the renderer with no lock; the renderer swallows the RuntimeError, so a frame is dropped now and then. Pre-existing; the eyepiece work here is the place to own it.
