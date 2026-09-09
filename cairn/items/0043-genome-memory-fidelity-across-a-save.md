---
id: 43
title: Genome memory fidelity across a save
type: bug
status: backlog
milestone: dish
created: 2026-09-08
updated: 2026-09-08
priority: p2
area: bio/dish.py
---

## Problem

`Dish.to_dict` runs each cell's `me.memory` through `_jsonable`, which keeps
ints, floats, strings, bools and None and turns anything else — a list of
directions, a nested dict — into `str(v)[:80]`. A genome that keeps a list in
memory gets a string back after a resume, and its next `me.memory["path"][0]`
throws: the cell lyses on the first tick after `biotic live` restarts. The exact
twin the persistence tests prove holds for primitive memory only, and keys
beyond the first 64 are dropped silently.

## Proposal

Either serialise JSON-compatible containers (lists, and dicts with string keys)
recursively under a total size cap and drop only what cannot be represented, or
bound `me.memory` at write time to a small dict of primitives so what a genome
sees is exactly what survives a save. Whichever: `CELL_API` in `bio/prompts.py`
must say what memory may hold, and `tests/test_persistence.py` must exercise it.

## Acceptance criteria

- [ ] A genome that stores a list in `me.memory` behaves identically before and after a save and load
- [ ] The exact-twin test covers non-primitive memory
- [ ] `CELL_API` states what `me.memory` may hold
