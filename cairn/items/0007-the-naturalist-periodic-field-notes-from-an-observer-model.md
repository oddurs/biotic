---
id: 7
title: 'The naturalist: periodic field notes from an observer model'
type: feature
status: planned
milestone: dish
depends_on:
- 3
created: 2026-09-08
updated: 2026-09-08
priority: p1
effort: m
area: bio/prompts.py, bio/culture.py, bio/tui.py
---

## Problem

The incubator log is a list of events; nobody reads 4,000 lines of "arose" and
"extinct". What a human wants is what a microbiologist writes in the lab book:
what changed since the last look, what it might mean, hedged. This is the one
output of a long run a person will actually read, and it is what makes the
dish feel observed rather than logged. (Sakana's ASAL is the precedent for a
foundation model as the observer of an artificial-life system.)

## Proposal

- Every `BIOTIC_NOTES_EVERY` ticks (default 600, ≈ 5 min at 0.5s) the culture
  builds an *observation packet*: tick, phase, population and diversity deltas
  since the last note, census with names and one-line notes, births/deaths by
  cause, the last 20 events, a low-resolution text rendering of the dish, and
  the previous field note (so notes read as a continuing record).
- One call to the mind with a `NATURALIST_SYSTEM` prompt: write 3–8 sentences
  in the voice of a lab notebook. Report what is observable; when interpreting,
  say so ("this resembles…"). Never invent mechanisms. Never give advice.
- Appended to `vessel/fieldnotes.md` under a `## tick N · HH:MM` heading, and
  logged as a `note` event. `biotic notes [-n]` prints them. The TUI shows the
  latest note's first line in the footer area instead of the static help text
  when a note exists.
- Counts against the budget like any call. Off when `BIOTIC_NOTES_EVERY=0`.

## Acceptance criteria

- [ ] Notes appear at the cadence; each references the previous by content
- [ ] A sweep (one strain going from <10% to >70%) is remarked on in the next note
- [ ] `biotic notes` prints the notebook; the TUI shows the latest line
- [ ] Prompt text in `bio/prompts.py`; no instructions to the culture leak into it
