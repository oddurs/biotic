---
id: 15
title: A random mutagen as the control arm
type: feature
status: planned
milestone: biotic-env
created: 2026-09-08
updated: 2026-09-08
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

- [ ] A `--mutagen random` dish evolves (strain count > 1 after 5,000 ticks) with zero API calls
- [ ] Every strain carries its origin; curve splits arisen by origin
- [ ] Random mutations respect the membrane (fuzz 1,000 mutations of the fallback founder; all admitted or rejected, none crash)
