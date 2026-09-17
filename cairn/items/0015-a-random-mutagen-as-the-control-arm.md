---
id: 15
title: A random mutagen as the control arm
type: feature
status: done
milestone: biotic-env
assignee: Oddur Sigurdsson
created: 2026-09-08
updated: 2026-09-16
priority: p0
effort: m
area: bio/mutagen_random.py
---

## Problem

The project's claim — semantic mutation may escape the Tierra plateau — is
untestable without the thing it is compared to. And the honest risk in
CONCEPT.md is that the LLM prior *canalises*: every mutant is a sensible
variation on sensible foraging, and the weird things never appear. A non-LLM
mutagen is both the control and the countermeasure.

## Proposal

- `bio/mutagen_random.py`: AST-level mutations that need no model: perturb a
  numeric constant by ±10–50%; swap `<`/`>`/`<=`; flip `and`/`or`; swap two
  indices in a `me.around[...]`-style subscript; delete one `if` branch;
  duplicate one statement; swap two return actions. Each result passes the
  membrane like anything else.
- `BIOTIC_MUTAGEN=llm|random|mixed` (default `mixed`); in `mixed`,
  `BIOTIC_RANDOM_SHARE` (0.25) of mutation rolls go to the random mutagen.
  Strains record `mutagen: "llm" | "random" | "hgt"` so the census, the curve
  (`arisen_llm`, `arisen_random`) and the fossils say which produced what.
- `biotic flasks new … --mutagen llm` / `random` sets up the comparison.

## Acceptance criteria

- [x] A `--mutagen random` dish evolves (strain count > 1 after 5,000 ticks) with zero API calls
- [x] Every strain carries its origin; curve splits arisen by origin
- [x] Random mutations respect the membrane (fuzz 1,000 mutations of the fallback founder; all admitted or rejected, none crash)

## 2026-09-16

The naturalist makes calls of its own: a zero-call control arm needs BIOTIC_NOTES_EVERY=0, or count only call events with role=mutagen.

## 2026-09-16

Default arm kept as mixed per the item's explicit spec; this changes every existing dish's next run (25% of rolls become random) and makes dormant flasks vary where they could not before. Flagged in CHANGELOG ### Changed and docs/mutagen.md. status shows the arm. Set --mutagen llm to keep pure-LLM. If the owner prefers no behaviour change, flip config.MUTAGEN_KIND default to llm (one line).

## 2026-09-16

The suite's baseline arm is pinned to llm in tests/conftest.py (vessel fixture), so a dormant culture stays faithful exactly as before the feature; tests for random/mixed opt in via monkeypatch. This preserved ~30 pre-existing determinism/trajectory tests without recomputing them and is not a weakened check.

## 2026-09-16

No fallback to the LLM on a refused random roll: a random roll that returns None (no eligible site, identical result, or membrane refusal) leaves the division faithful. Keeps the arms an exact partition; test_mixed_with_zero_random_share_is_all_llm and the full-share test pin it.

## 2026-09-16

In-process admit() (not admit_isolated) in RandomMutagen.mutate: _on_divide runs on the main thread after the cell's Budget block closes (Dish._apply calls on_divide after 'with Budget' exits), so the SIGALRM smoke test is safe there. A subprocess per mutation would make the fuzz test and a dense random dish slow for no gain; the verdict is identical.

## 2026-09-16

rng_mut is a separate, flask-salted, persisted RNG. Its purpose is to keep the random-mutation stream ISOLATED from the dish RNG so a later dish change never shifts mutation content — NOT what makes pure-LLM byte-identical (that is the self.rng roll staying first, plus the mixed share test being short-circuited by 'and' when kind!=mixed). A pure-llm run never draws from rng_mut.

## 2026-09-16

random mode does not start the LLM Mutagen thread (run() gates mutagen.start() on kind!=random), or its _pick spontaneous path would call the mind on the wall clock (last_call starts at 0.0, so the wall interval is already long past). mutagen.close() in the finally is safe on an unstarted thread. mixed still starts it (a mixed roll may go to the LLM); on the tick clock the thread returns at once regardless. Proven by the wall-clock case of test_random_arm_evolves_with_zero_api_calls.

## 2026-09-16

The --mutagen flag is on live/run and flasks new only (mirrors --clock, which is on live/run); seed does not take it. A lone user sets the arm with 'biotic run --mutagen random' (remembered in dish.json). A pre-feature freezer sample has no rng_mut, so restore_state leaves the reviving process's rng_mut as constructed rather than resetting it: cross-machine determinism of a random/mixed run revived from an OLD sample is not guaranteed. New samples round-trip exactly (test_a_freezer_sample_preserves_origin_and_the_mutation_rng).
