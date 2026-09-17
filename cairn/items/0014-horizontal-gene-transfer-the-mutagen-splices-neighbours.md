---
id: 14
title: 'Horizontal gene transfer: the mutagen splices neighbours'
type: feature
status: done
milestone: biotic-env
assignee: Oddur Sigurdsson
depends_on:
- 12
created: 2026-09-08
updated: 2026-09-16
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

- [x] Splices arise in a two-strain dish and the fossil header names both parents
- [x] Strains that never touch never splice
- [x] `biotic strains` shows donor lineage; census colour of a splice is between the parents' hues
- [x] Curve gets a `spliced` cumulative column

## 2026-09-16

Hue: a splice's base hue is _mix_hue(parent, donor) (shortest-arc midpoint, wrap-safe), an ordinary mutation stays on the parent's hue; either way exactly one gauss(0,0.07) jitter is drawn in the known-parent branch, so the hue RNG advances identically and no seeded trajectory shifts. Pinned exactly in test_hgt (parallel Random primed with reg._rng state).

## 2026-09-16

Draw order in Culture._on_divide is fixed: mutation roll, then (only if dish.features['hgt']) the HGT roll, then _pick_donor. Both extra draws sit behind the feature gate, so an hgt-off dish's culture-RNG stream is byte-identical to before. Pinned by test_the_divide_hook_draws...; resume determinism covered by test_an_hgt_on_dish_resumes... (matters for biotic reproduce, 0037).

## 2026-09-16

Wall-clock pool: requests/pool keyed by str (mutation) or (recipient,donor) tuple (splice), via _split(). splice_at{key->tick} drives _expire(): a prepared/pending splice lapses after HGT_EXPIRY_TICKS (500) if the pair never re-touches. Expiry is approximate (+/-~3 ticks) because context['tick'] refreshes every 3 ticks on the wall clock; _expire runs only under self.lock (called from take/_pick). Tested on the hand clock, thread never started.

## 2026-09-16

conftest fake_mutagen signature had to become take(self, strain, donor=None) because _on_divide now calls take(cell.strain, donor=donor); without it the freezer tests TypeError. A splice increments BOTH mutations_taken and spliced (a splice is a kind of mutation) so the two curve columns are not disjoint; documented in docs/hgt.md and CHANGELOG. _ask's donor-missing fallback: if the donor left genomes between request and prep, the splice falls through to an ordinary mutation prompt (wall-clock edge only; tick clock guarantees the donor is present).

## 2026-09-16

Review fix: docs/predation.md misstated CONCEPT.md §1 order (had hgt second, give third). CONCEPT.md §1 is predation, sharing, hgt; docs/hgt.md agrees. Reworded predation.md to 'sharing is second, hgt third'. Docs-only, no behaviour change (CHANGELOG/README 'second rule' means second-implemented, left as-is).
