---
id: 26
title: '`biotic web` — who eats whose secretions'
type: feature
status: planned
milestone: secretions
depends_on:
- 25
created: 2026-09-08
updated: 2026-09-08
priority: p1
effort: m
area: bio/__main__.py, bio/tui.py
---

## Problem

Once intermediates flow between strains there is a food web, and it is the
architecture. It must be observable.

## Proposal

- The dish records edges `(secretor_strain, consumer_strain, substrate, stage)`
  with counts per curve interval.
- `biotic web [--substrate X] [--since TICK] [--dot out.dot]`: a text tree per
  substrate showing stage → secreting strains → consuming strains with counts;
  `--dot` emits Graphviz.
- The TUI census marks strains that live mostly on intermediates (`⇢`) or
  mostly by secreting (`⇠`).
- Curve columns: `intermediates_alive`, `web_edges`.

## Acceptance criteria

- [ ] `biotic web` on the fixture pair shows one edge with a growing count
- [ ] `--dot` renders in Graphviz
- [ ] Census marks producers and consumers
