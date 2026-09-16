---
id: 43
title: Genome memory fidelity across a save
type: bug
status: done
milestone: dish
assignee: Oddur Sigurdsson
created: 2026-09-08
updated: 2026-09-16
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

- [x] A genome that stores a list in `me.memory` behaves identically before and after a save and load
- [x] The exact-twin test covers non-primitive memory
- [x] `CELL_API` states what `me.memory` may hold

## 2026-09-16

Design: option B from the item, bound me.memory at write time, applied in the dish after every live() (inside the cell's Budget, so the walk over what the cell built is charged to it) and in the smoke test after every round, with a faithful codec at the save. Option A (encode what can be encoded, drop the rest) can never give an exact twin: whatever the save drops, the running dish still has. The rule runs at the same point of every tick in both the running and the resumed dish, so at any save every memory is one the codec is the identity on.

## 2026-09-16

The check is a Python walk (membrane._walk), not json.dumps alone, and that is for correctness: dumps cannot see that one list sits in two places (a save separates it: twin broken), and on 3.12+ it recurses to ~5000 levels where copy.deepcopy in _inherit gives up at ~500 and falls back to sharing the structure between mother and daughter. The walk keeps a lower and an upper bound on the JSON length (per element 2; str len+2 / 12*len+2 since ensure_ascii writes an astral char as 12; key +4; int bits>>2 / bits//3+3; float 3/24; bool/None 4/5), stops as soon as the lower bound passes the cap (so work is O(cap), never O(memory): a 10**9-leaf DAG bomb is refused in ~7 us), and skips dumps when the upper bound is under the cap, which is most memories. tests/test_membrane.py::test_walk_size_is_a_lower_bound_on_the_json_length pins lo <= len(dumps) <= hi on 2000 seeded memories, so neither short cut can change a verdict. Do not loosen it: the reviewer's first prototype over-counted single-key dicts by one and that test is what catches it.

## 2026-09-16

Tagging instead of forbidding: JSON cannot tell a tuple from a list or an int key from a str key, so encode_memory writes a tuple as {"~t": [..]} and any dict whose keys are not all plain strings (or has a key beginning with ~) as {"~d": [[k, v], ..]}; decode_memory is total on any JSON and returns a dict at the top level. Forbidding tuples and numeric keys would push evolution toward a JSON dialect, the canalising kind of rule CONCEPT.md warns about, and the tag costs nothing per tick. freezer.FORMAT stays 1: the freezer is still under [Unreleased], tagged files are a superset of plain ones, and untagged files (older dish.json, hand-written samples) decode as plain JSON. Memory an older save had already flattened to a string stays flat; nothing can tell what it was.

## 2026-09-16

Over the bound is lysis, not trimming: trimming picks a key to drop, a silent semantic change; a burst shows in the death ledger and the smoke test tells the mutagen why. The five reasons are interface strings pinned by tests and docs/membrane.md. One deviation from the plan: the key reason reads 'memory has a tuple as a key; keys must be strings, numbers, bools or None' (one form for every refused key type, built from _name) rather than 'memory has a tuple key', because a Me or a Random as a key would otherwise read 'memory has me key'.

## 2026-09-16

Constants: MEMORY_MAX_CHARS = 2048 (holds ~100 floats or ~400 small ints, enough for a stage-2 substrate window; the per-tick cost is proportional to it; 0018 may revisit) and MEMORY_MAX_DEPTH = 16 (nothing a forager keeps nests past 4; it exists so deepcopy and the codec can never run out of stack on an admitted memory). Both are physics: a running culture with a strain whose memory already breaks the rule (aliased rows, nesting past 16, over 2 KB) sees those cells lyse on the first tick after upgrading. The owner's tide vessel is unaffected: no fossil in tests/fixtures/genomes uses memory. Said plainly in the changelog.

## 2026-09-16

Cost, measured on this machine, 72x34, stepped flat out, best of 3, origin/main vs this branch in the same session: founder (empty memory) 2.48 -> 2.50 ms/tick at 621 cells; WANDERER (a six-int trail) 2.91 -> 3.45 ms/tick at 588 cells (+19%, ~0.9 us per cell); TUPLE_GENOME (five keys, a tuple, an int-keyed dict of up to 8) 3.29 -> 4.56 ms/tick at 768 cells (+39%, ~1.6 us per cell; the walk alone, dumps is skipped by the upper bound). At TICK_SECONDS = 0.5 all of it is under 0.3% of a tick. Per memory: empty 0.04 us, WANDERER 0.93 us, tuple+counts 1.6 us, 100 floats 25 us, 400 ints 33 us (both near the cap, where dumps runs). Save/freeze gain a Python walk over every memory: WANDERER 0.15 ms per save, TUPLE 1.2 ms. If flat-out replays (0037) ever care, the next step is to move the leaf dispatch to a dict keyed by type; the upper bound already removed dumps from the common path.

## 2026-09-16

The codec is faithful, not a bound: anything memory_fault refuses is unreachable for a cell that has lived a tick, so encode_memory's fallback (str()[:80] via _text, and _text again for a value nested past the recursion limit) is only reachable from place()/inoculate() with hand-made memory or a hand-edited dish sample revived before its first tick, and exists so that a save never fails on it. Culture.save's except tuple is unchanged. A hand-edited dish.json with an over-cap memory loads (biotic status reads the same file) and that cell bursts on the first tick the culture runs; tests/test_culture.py shows it. A strain sample is different: both revives save right after placing the cells, before any tick runs the rule, so _strain_sample decodes the memory and refuses it by name before the pre-revive freeze.

## 2026-09-16

Watch: the cap-lysis test's admission margin is thin by construction (TOO_MUCH_GENOME reaches 2008 of 2048 chars after the smoke test's forty rounds); the first failing tick is computed from the constant, and the test asserts 30 < first <= 70 with a message saying to pick a new multiplier if the cap or the round count moves. nan/inf in memory are carried by json (allow_nan, as before) but nan != nan breaks dish_state equality and a nan dict key never matches on lookup even before a save; tests avoid them and the docs do not claim dish.json is strict JSON. The alias rule refuses m['a'] = m['b'] even when neither is mutated; the reason string says to copy, and the rejection feedback is what teaches the mutagen.

## 2026-09-16

Resumed an interrupted build. Reconciled the handed-in plan (which argued option 1, JSON-encode-at-save, had already shipped in d9f4a67 and to only finish CELL_API + one test) against the working tree, which had instead implemented option B (bound me.memory at write time). Kept option B: it is the design the item body itself records, it satisfies criterion 1 literally (Option A can never give an exact twin because whatever a save drops the running dish still has), and the whole suite was already green (379 tests, 12 s). Reverting working, tested, more-correct code for the smaller plan would have been the regression.

## 2026-09-16

Criteria proven: (1) list/tuple/dict identical across save -> test_persistence.test_resumed_dish_is_an_exact_twin_for_memory_plain_json_cannot_carry (fifty-tick twin) plus its control test_plain_json_memory_would_not_have_been_a_twin (the old plain-JSON save would have drifted); (2) exact-twin over non-primitive memory in test_persistence.py -> the parametrized cross-process twin [tuple_memory] and the in-process twin above; (3) CELL_API states the rule -> bio/prompts.py interpolates config.MEMORY_MAX_DEPTH/MEMORY_MAX_CHARS so prose cannot drift from the constants. Gate green bio-only; scripts/task check skips web (no web/ change) and 0048 tracks the site membrane page.

## 2026-09-16

Review pass: aligned the prose to the code rather than the code to the prose. The cap is len(json.dumps(memory)) on the plain form (tuple as list, numeric key as string); encode_memory's ~t/~d tags make the on-disk file a little larger, so a tuple-heavy memory admitted at the cap saves to over it. Kept the check on plain JSON (the _walk bounds and their O(cap) cost analysis are built for that form; re-basing them on the tagged form would be a real change for a doc-clarity gap) and reworded CELL_API, docs/membrane.md, the memory_fault docstring, config comment and the unreleased changelog to say plain JSON. New test_membrane.test_the_cap_is_measured_on_plain_json_not_the_tagged_file pins the decision.

## 2026-09-16

Review pass: CELL_API key clause said 'strings or numbers', narrower than the rule (_walk admits str/int/float/bool/None keys; _MEMORY_KEYS and docs say 'strings, numbers, bools or None'). Widened it to match, in CELL_API and the changelog. New tests/test_prompts.py pins CELL_API against _MEMORY_KEYS so the prompt cannot drift from the rule again.

## 2026-09-16

Review pass: moved MODULE_GENOME from test_persistence into tests/conftest.py so test_membrane no longer imports from a sibling test module; all shared genome constants now live in conftest. Both test modules import it from there.
