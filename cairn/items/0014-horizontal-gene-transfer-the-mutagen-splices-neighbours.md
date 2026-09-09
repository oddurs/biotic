---
id: 14
title: 'Horizontal gene transfer: the mutagen splices neighbours'
type: feature
status: planned
milestone: biotic-env
depends_on:
- 12
created: 2026-09-08
updated: 2026-09-08
priority: p0
effort: l
area: bio/mutagen.py, bio/strains.py, bio/prompts.py
---

## Problem

Mutation is the only source of variation, and it acts on one lineage at a
time. Real bacteria trade genes across lineages — plasmids, transformation,
phage — and that is how antibiotic resistance crosses species in a season. With
a semantic mutagen, recombination is not bit-level crossover but *splicing by
meaning*: "take the scent-following from that strain and the division rule from
this one." This is the single largest lever on novelty rate the project has,
and it is the fast lane for coevolution.

## Proposal

- On a division that rolls a mutation, with probability `HGT_RATE` (0.3 of
  mutations), the request is an HGT request: it carries the parent genome *and*
  the genome of one random adjacent non-kin cell (the donor). If no non-kin
  neighbour exists, it is an ordinary mutation.
- `Mutagen` gets a second prompt, `HGT_SYSTEM`: you are handed a recipient and
  a donor; return the recipient with one behaviour borrowed from the donor.
  Keep the recipient's temperament. Name the strain after both.
- The new strain records `parent` *and* `donor`; `Strain.donor: str | None`.
  The fossil header says "from X, with a gene from Y". Lineage becomes a DAG;
  `lineage_of` follows `parent` only, `biotic genome` prints donors inline.
- The pool is keyed by `(recipient, donor)` so a prepared splice is taken only
  when that pair divides again next to each other — if it never does, the
  variant expires after 500 ticks (real conjugation needs contact).
- Feature flag as in lyse. Event kind `spliced` with its own glyph (`⇄`).

## Acceptance criteria

- [ ] Splices arise in a two-strain dish and the fossil header names both parents
- [ ] Strains that never touch never splice
- [ ] `biotic strains` shows donor lineage; census colour of a splice is between the parents' hues
- [ ] Curve gets a `spliced` cumulative column
