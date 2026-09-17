---
id: 10
title: 'Incubation gaps: record wall-clock absence, do not fake ticks'
type: feature
status: done
milestone: dish
assignee: Oddur Sigurdsson
depends_on:
- 7
created: 2026-09-08
updated: 2026-09-16
priority: p2
effort: s
area: bio/culture.py
---

## Problem

`biotic live` after 12 hours away resumes at the tick it left. That is correct —
a dish in the freezer does not grow — but the curve and notes should say so,
and the naturalist should not describe a 12-hour gap as "since the last note".

## Proposal

- `Culture.load` compares `state.saved_at` to now; if the gap exceeds 10 minutes
  it logs `incubation resumed after 12h 04m` and writes a marker row to the curve.
- The observation packet for the naturalist includes the gap.
- `biotic status` shows `last active`.

## Acceptance criteria

- [x] A resumed dish logs the gap once
- [x] `biotic curve` shows the gap marker

## 2026-09-16

The composed packet carries since.seconds, since.ticks and since.pace (ticks at the incubator's pace) and the prompt says wall time beyond the ticks is time the incubator was off; add the measured gap to compose() when saved_at exists.

## 2026-09-16

saved_at lives at the dish.json blob top level, never in state_dict(): state_dict rides verbatim into every freezer sample and into the Dish/culture round-trip the twin tests pin, so a non-deterministic save clock there would pollute samples and break determinism. Top-level keeps it as pure persistence metadata; Dish.to_dict/from_dict untouched. Freezer samples never carry saved_at and revive() never measures a gap.

## 2026-09-16

The gap is measured in load() (time.time() - saved_at) but NOT written there: load() must stay write-free because biotic status loads too, possibly while another process holds the dish. It is queued in _unsaid and emitted by run() via the existing drain, at the resume tick, on the main thread, before the mutagen/naturalist threads start.

## 2026-09-16

_swap() clears self._resume: a resume measured on the old branch must not leak into the first post-seam non-seam note on the new branch. The compose window (previous.tick <= resume.tick <= packet.tick) has no branch guard, so without the clear a revive could spuriously report the pre-revive gap.

## 2026-09-16

compose() surfaces the gap once and only once: the window previous.tick <= resume.tick <= packet.tick holds for exactly the first note written after the resume; once written the baseline advances past resume.tick and the window closes. No clear-after-use flag. It survives a dropped/failed mind call because self.last only advances when a note lands.

## 2026-09-16

dish.tick > 0 guard: germinate() saves at tick 0, so a freshly seeded but never-run dish must not claim a phantom resume. gap >= INCUBATION_GAP also excludes negative gaps from clock skew.

## 2026-09-16

BIOTIC_INCUBATION_GAP default 600s (10 min), bookkeeping not physics — sits with FREEZE_EVERY/NOTES_EVERY under that heading in config.py, env-overridable, user-visible so it is in the changelog; no membrane/physics caveat.

## 2026-09-16

Accepted limitation: a resume on a dish with no prior naturalist baseline (never wrote a note) surfaces no measured-gap line to the naturalist — compose's first-entry path (previous falsy) skips the non-seam block. The gap event and the curve marker still record the absence, so both acceptance criteria hold; documented, not fixed.

## 2026-09-16

The display half (⋯ glyph, plot.MARKERS/markers/figure/render, curve.events branch join, the naturalist off-time principle in NATURALIST_SYSTEM) already shipped with #32/#33. This item added: emit the gap event on resume (both criteria), the measured gap in the naturalist packet/prompt per the 2026-09-16 note, biotic status last-active, and tui.ICONS[gap] so the resume banner shows a real glyph in the incubator log. No new curve.csv column: the marker is drawn from the event via curve.events()+plot.markers(), per bio/curve.py's rule.

## 2026-09-16

Gap dedup on reload: a process hard-killed between the resume drain and its first periodic save leaves dish.json's saved_at unchanged, so the next load re-satisfies the threshold. load() now reads _last_gap and skips queuing when the last gap event's saved_at equals the current one, mirroring the note/ledger reconcile pattern. Curve glyph was already deduped by (branch, resume_tick); this stops a second incubator-log line. A save that advances saved_at still makes a genuinely new absence a fresh gap.
