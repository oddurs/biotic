---
id: 18
title: Substrate abstraction and the `digest` action
type: feature
status: planned
milestone: substrates
created: 2026-09-08
updated: 2026-09-08
priority: p0
effort: l
area: bio/substrates.py, bio/dish.py, bio/prompts.py
---

## Problem

There is one kind of food and eating it requires no computation. For the output
of a run to be software, eating has to require computing something.

## Proposal

`bio/substrates.py`:

```python
class Substrate:
    name: str            # "glucose" is the plain nutrient; others are tasks
    glyph: str; hue: float
    def sample(self, rng) -> Any        # what a tile offers this tick (small: ints, short lists, short strings)
    def score(self, sample, answer) -> float   # 0..1; must be total (never raise), fast
    yield_: float        # energy at score 1.0; richer than glucose (0.15 vs 0.06)
    cost: float          # energy to attempt (0.02) — wrong answers are not free
```

- The dish gains `substrate: list[list[str | None]]` — a substrate name per tile,
  laid down in patches by the same blob generator as agar (so a seed gives the
  same geography every time). `nutrient` stays as glucose everywhere.
- `me.substrate` → `(name, sample)` or `None`; `me.around_substrate` → 8 names.
  Samples are regenerated each tick from `rng` seeded by `(tick, x, y)` so two
  cells on one tile see the same sample and a cell cannot farm a lucky one.
- Action `("digest", answer)`: pay `cost`; gain `yield_ × score`. A score below
  0.2 also depletes nothing; a score ≥ 0.8 depletes the tile's *substrate
  richness* (a second float grid, replenishing slowly like nutrient) so a
  solved patch is a contested one.
- Membrane: `answer` must be JSON-serialisable and ≤ 256 bytes, else lysis.
- `CELL_API` in the prompt documents digest and shows each substrate's
  *sample shape* and *what a correct answer is*, in one line each — the mutagen
  must know the task to write a pathway for it. The mutagen also gets the
  recipient strain's current per-substrate accuracy in its context.
- Per-strain digestion stats accumulate in the registry: attempts, mean score
  per substrate. That is the "diet".

## Acceptance criteria

- [ ] `Substrate` protocol with three built-ins (see the next item) and a registry by name
- [ ] Dish lays patches, renders them (distinct glyph/hue per substrate), and `me.substrate` is populated
- [ ] A hand-written genome that digests one substrate correctly outcompetes the fallback founder on that patch
- [ ] Wrong answers cost energy; a genome that answers randomly starves on substrate and survives on glucose
- [ ] Fossil headers include the diet: `digests: sequence 0.91, sort 0.12`
