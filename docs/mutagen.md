# the mutagen

On a fraction of divisions a cell does not copy its genome faithfully; a mutagen
writes the daughter's instead. biotic has two, and a dish runs on one arm or a mix
of both.

## two mutagens

**The semantic mutagen** is the mind. It is handed the parent's genome and what the
dish looks like, and it writes a daughter — a variation that means something, because
the model has a prior over all of human programming. This is the project's claim:
that a mutagen which understands what code *means* reaches neighbours a bit-flip never
would ("follow the scent" becomes "follow the scent, but only your kin's"). It needs a
mind, a network and a budget, and it is clocked (`docs/experiments.md`).

**The random mutagen** is the control arm. It rewrites the genome at the level of the
syntax tree — no model, no network, no spend — and the change is structural, not
semantic. It exists for two reasons, both in `CONCEPT.md`:

- The claim is untestable without the thing it is compared to. Tierra and Avida
  evolved under random mutation and then plateaued; the question is whether the
  semantic mutagen pushes past that plateau. You cannot answer it with the semantic
  arm alone.
- The honest risk is the opposite one — that the LLM prior *canalises*, so every
  mutant is a sensible variation on sensible foraging and the weird things never
  appear. A fraction of random mutations is a countermeasure: it keeps a source of
  novelty the prior cannot flatten.

## the seven transforms

Each random mutation is one change at one randomly chosen site, drawn uniformly from
the transforms that have a site to act on:

1. **perturb a constant** — one numeric constant shifted by ±10–50% (an integer stays
   an integer, magnitude at least 1). Exponents, subscript indices, `range()` bounds
   and the counts that multiply a list literal are left alone: perturbing those makes a
   genome the membrane rejects rather than a living variant.
2. **flip a comparison** — one `<`↔`>` or `<=`↔`>=`.
3. **flip a boolean operator** — one `and`↔`or`.
4. **swap a subscript index** — a constant index in `0..7` changed to another, or two
   such indices swapped (this is `me.around[3]` becoming `me.around[5]`).
5. **drop an `if` branch** — either the `else` is removed, or the condition is removed
   and the body always runs.
6. **duplicate a statement** — one statement copied in place, just after itself.
7. **swap two return actions** — the values of two `return`s exchanged.

The result passes the membrane like any other genome. A daughter that does not — a
resource bomb, one that throws on the stand-in cell, or one identical to its parent —
is refused, and the division is faithful; nothing crashes the dish. Because the
change is made through the syntax tree and written back with `ast.unparse`, the fossil
in `soma/` is reindented and its comments are gone: a reader diffing it against the
parent sees the reflow, not the single token. The change is the same one; the membrane
admits it.

## the three arms

Set the arm with `BIOTIC_MUTAGEN`, or `--mutagen` on `biotic live`, `biotic run` and
`biotic flasks new`. Like `--clock` and `--budget`, a `--mutagen` flag is remembered in
`dish.json` and sticks; the environment variable is per process.

| arm | what a mutation roll does |
| --- | --- |
| `llm` | always the semantic mutagen |
| `random` | always the random mutagen — offline, no spend |
| `mixed` | `BIOTIC_RANDOM_SHARE` of rolls go to random, the rest to the LLM |

`mixed` is the default, and `BIOTIC_RANDOM_SHARE` is `0.25`. A roll is decided first
(`BIOTIC_MUTATION_RATE`, unchanged), then the arm; there is no fallback — a random roll
that finds no change to make leaves the division faithful rather than asking the mind.
The two arms draw from different random generators, so a pure `--mutagen llm` dish is
byte-for-byte what it was before this arm existed.

**The default changed the physics.** Before this, every dish mutated only through the
mind, so a dish with no key — and every replicate flask, which runs dormant — never
varied. Now, unless you set `--mutagen llm` (or `BIOTIC_MUTAGEN=llm`), a quarter of a
dish's rolls go to the offline arm: an existing dish changes trajectory on its next
run, and dormant flasks vary where they could not. Set `--mutagen llm` to keep the old
behaviour exactly.

## offline and deterministic

The random arm draws from its own seeded generator (`rng_mut`), salted by the flask id
and saved with the dish, so a random or mixed run reproduces on any machine, and a save
and reload lands on the same trajectory. A run that touches the network *not at all*
also needs the naturalist off — it calls the mind on its own cadence — so a truly
zero-call control is `BIOTIC_MUTAGEN=random BIOTIC_NOTES_EVERY=0 biotic run`. (A sample
frozen before this feature carries no `rng_mut`; a run revived from such an old sample
keeps the reviving process's generator rather than resetting it, so only samples this
apparatus wrote reproduce the random stream cross-machine.)

## which mutagen made what

Every strain records its origin — `llm`, `random`, or null for the founder — in
`strains.json` and in its fossil header (`arose … by the random mutagen`). The census
counts it, and the growth curve splits `arisen` into `arisen_llm` and `arisen_random`
(`docs/curve.md`). `biotic status` shows the arm the last run used and any `--mutagen`
the dish remembers.

## the control experiment

Found two flask sets from one seed, one on each arm, and compare them:

    biotic flasks new comp-llm    --seed "tide" --mutagen llm
    biotic flasks new comp-random --seed "tide" --mutagen random
    biotic flasks run comp-llm    --ticks 5000
    biotic flasks run comp-random --ticks 5000
    biotic flasks curve comp-random --cols arisen,shannon

The random set is a complete offline control — the flasks are dormant, and the random
arm needs no mind — so it costs nothing to run. `docs/experiments.md` has the rest of
the flask methodology.
