---
id: 20
title: 'Seed → chemistry: the mind derives the substrate mix'
type: feature
status: planned
milestone: substrates
depends_on:
- 19
created: 2026-09-08
updated: 2026-09-08
priority: p1
effort: m
area: bio/prompts.py, bio/culture.py
---

## Problem

The seed inflects the founder's temperament and nothing else. With substrates
it can determine what the world is *made of*, which is the difference between
a mood and a world.

## Proposal

- At `biotic seed`, one call with `CHEMISTRY_SYSTEM`: given the seed and the
  catalogue of substrates (name, description, parameters), return a recipe:
  which substrates, their share of the agar, and parameters where a substrate
  takes them (sequence families, pattern rules, order length). Reply format is
  the same header/body form as genesis; parsed leniently; validated against the
  catalogue; anything unknown is dropped with a logged reason.
- A seed that is a *question* gets a recipe whose substrates are its
  sub-problems as far as the catalogue allows — and the recipe includes a
  one-paragraph `rationale` written to `vessel/chemistry.md`, so the
  experimenter can see the mind's reading of the seed.
- `biotic seed --chemistry glucose:0.6,sequence:0.4` overrides.
- The recipe is persisted in `dish.json`; the agar generator lays patches from it.

## Acceptance criteria

- [ ] `"tide"` yields a recipe dominated by `sequence` with periodic families; `chemistry.md` explains why
- [ ] An invalid recipe degrades to glucose-only with a logged reason, never a crash
- [ ] `--chemistry` override bypasses the call
