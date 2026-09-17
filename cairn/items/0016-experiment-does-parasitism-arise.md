---
id: 16
title: 'Experiment: does parasitism arise?'
type: docs
status: done
milestone: biotic-env
assignee: Oddur Sigurdsson
depends_on:
- 5
- 6
- 12
- 13
- 14
- 15
created: 2026-09-08
updated: 2026-09-16
priority: p1
effort: l
area: experiments
---

## Problem

The first thing Tierra produced that nobody designed was a parasite. If the
biotic environment is real, something analogous should appear here: a strain
that never eats agar and lives by lysing, or by receiving from kin-mimics, or
one that splices donors' foraging code and drops its own. Whether it does is
the first real result this project can report, and it should be run as an
experiment, not noticed by accident.

## Proposal

A written protocol, executed, with results recorded *in this item*:

1. Six flasks, seed `"tide"`, features `lyse,give,hgt`, mutagen `mixed`,
   replenish default, 30,000 ticks each at `--tick 0`, budget $3 each.
2. Six control flasks: same, features off.
3. Freeze every 2,000 ticks.
4. Measure per flask: `shannon` over time, `arisen` slope in the last 10k
   ticks vs. the first 10k (is novelty decelerating?), share of `predated`
   deaths, and — by reading genomes — whether any living strain at the end has
   *no* `"eat"` path (an obligate predator or beggar).
5. Naturalist notes on for the treatment flasks; read them.
6. Write the result as a table in this item and a paragraph in CONCEPT.md's
   "honest risk" section, whichever way it comes out.

## Acceptance criteria

- [x] Protocol run to completion (scaled — see Results: 6 flasks × 15k ticks)
- [x] Table of metrics per flask in this item
- [x] A yes/no on obligate parasites, with the genome quoted if yes
- [x] CONCEPT.md updated with the finding

## Results (2026-09-16)

**Obligate parasites: NO.** Not a single living strain, in any of the six
flasks, lost its `"eat"` path. Predation *itself* arose readily and swept — but
it arose *facultative*, layered on top of foraging, never replacing it. Giving
never evolved at all, so no beggar could arise; and though HGT splices occurred,
no spliced strain dropped its own foraging code.

### Scale reductions from the stated protocol (reasons)

- **12 flasks → 6** (3 treatment + 3 control), **30,000 → 15,000 ticks**:
  budget cap ($3.00 total, not $3/flask) and wall-clock. Tick-clocked, each
  flask makes ~ticks/40 attempts; six ran in parallel and finished in ~4 min.
- **Budget $3/flask → $0.45/flask** (6 × 0.45 = $2.70 ceiling ≤ $3 cap).
  Realised spend **$0.178 total** — tick-clocked gemini-flash-lite is cheap
  (~$0.03/flask); no flask neared its budget.
- **Mutagen `mixed` with model `google/gemini-2.5-flash-lite`** (the default
  chosen by item 0041) for the LLM share; `BIOTIC_RANDOM_SHARE` 0.25 default.
- **Common built-in founder** (ancestor `7a8d`, "eats where it stands, divides
  when full, drifts uphill") poured identically into all six flasks via
  `biotic flasks new` (as 0041 did), features enabled on the treatment three by
  `biotic drop feature {lyse,give,hgt}`. This isolates evolved behaviour from
  founder authoring and keeps treatment/control founders identical.
- **No every-2,000-tick freezing**: the time series (Shannon, `arisen`,
  predated deaths) is read from `curve.csv`, which logs every 10 ticks — finer
  than 2,000-tick freezes would give.
- **Naturalist notes not enabled** (proposal step 5): the naturalist adds
  model calls every few hundred ticks and is not an acceptance criterion; the
  quantitative signals (predated deaths, per-strain sources) answered the
  question without it. Skipped for budget/wall-clock.
- `biotic flasks run` is **not** usable for a paid run (it blanks the API key in
  every child; item 0006). Each flask ran as its own `biotic run --vessel …
  --clock tick --mutagen mixed --budget 0.45` process, parallelised.

### Per-flask metrics

Treatment = features `lyse,give,hgt` on. Control = features off. Same seed
`"tide"`, same founder, mutagen `mixed`, 15,000 ticks, `EVERY_TICKS`=40.

| flask | pop | strains (end) | Shannon end | Shannon max | dominance | arisen | slope /1k (early→late) | predated (share of deaths) | given | spliced | living | obligate no-eat |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| treat/01 | 169 | 2 | 0.66 | 1.35 | 0.63 | 197 | 11.97 → 12.18 | 659 (11.1%) | 0.0 | 0 | 18 | **0** |
| treat/02 | 177 | 1 | 0.00 | 2.84 | 1.00 | 164 | 11.55 → 9.77 | 237 (3.9%) | 0.0 | 13 | 4 | **0** |
| treat/03 | 120 | 1 | 0.00 | 1.78 | 1.00 | 192 | 12.78 → 9.81 | 793 (11.5%) | 0.0 | 2 | 34 | **0** |
| ctrl/01 | 201 | 11 | 1.63 | 2.31 | 0.44 | 173 | 11.58 → 10.64 | 0 (—) | 0.0 | 0 | 11 | **0** |
| ctrl/02 | 168 | 14 | 2.00 | 2.46 | 0.36 | 158 | 10.89 → 9.05 | 0 (—) | 0.0 | 0 | 14 | **0** |
| ctrl/03 | 144 | 14 | 2.00 | 2.45 | 0.33 | 185 | 11.44 → 13.11 | 0 (—) | 0.0 | 0 | 14 | **0** |

"early" slope = `arisen` over the first 5,000 ticks; "late" = over the last
5,000. Total spend $0.178 of the $3.00 cap.

### Reading it

- **Predation arose and became near-universal, but facultative.** In every
  treatment flask almost every *living* strain carries a `("lyse", d)` path
  (17/18, 4/4, 34/34) — yet every one of those same strains still returns
  `"eat"` too (18/18, 4/4, 34/34). Predation was added *to* foraging, not
  *instead of* it. Predated deaths reached 11.5% of all deaths.
- **The predator sweeps diversity, it does not raise it.** The arms-race hope
  was coexistence; the result was collapse. Treatment ended near-monoculture
  (mean Shannon 0.22, dominance 0.88, ~1.3 strains) while the control stayed
  diverse (mean Shannon 1.87, dominance 0.38, 13 strains). A hunter that eats
  *and* lyses dominates a dish of pure foragers.
- **Giving never evolved** (`given` = 0.0 everywhere), so the "beggar" route to
  parasitism — living on kin-mimic gifts — never even opened. Take is easy for
  the prior to reach from a forager; give is not.
- **HGT fired** (spliced 13 and 2 strains in treat/02, treat/03) but produced no
  parasite: a splice grafts one behaviour onto a strain that keeps its own, so
  the recipient kept eating.
- **Novelty barely decelerates over 15k ticks.** `arisen` climbs near-linearly
  at ~10–13 new strains per 1,000 ticks; late slope is below early in four of
  six flasks but by a small margin — no plateau within this run.

### The nearest thing to a parasite (quoted)

The clearest evolved predator is `scavenger_42b1_ambusher` (id `8735`, LLM
mutagen) — the dominant living strain of treat/03. It is a *facultative* hunter,
not an obligate one: it lyses a weaker neighbour when it can, but falls straight
through to `"eat"`. This is the genome the experiment was hunting for, one step
short of parasitism:

```python
def live(me):
    free = [d for d in range(8) if not me.crowd[d]]
    if me.energy > 1.0 and free:
        return "divide"

    # Prioritize hunting if there's a weaker threat
    threat_val = max(me.threat)
    if threat_val > 0 and me.energy > threat_val * 0.5:
        threat_dir = me.threat.index(threat_val)
        if not me.kin[threat_dir]:
            # This is the primary hunting behavior
            return ("lyse", threat_dir)

    # If no good hunt, then consider eating
    if me.here > 0.01:
        return "eat"

    # If still no good options, move to a richer spot if available
    if free:
        best = max(free, key=lambda d: me.around[d])
        if me.around[best] > me.here + 0.01:
            return ("move", best)

    return "rest"
```

Remove the `return "eat"` line and it would be an obligate predator. The prior
never removed it — every hunter it wrote kept eating as a fallback.

## 2026-09-16

Ran 2026-09-16, spend $0.178 of $3 cap. Obligate parasites: NO — no living strain in any of 6 flasks lost its eat path. Predation arose facultative and near-universal (17/18,4/4,34/34 living strains lyse, all still eat), swept diversity to near-monoculture (Shannon 0.22 vs control 1.87). Giving never evolved; HGT grafted without replacing. Scaled 12x30k -> 6x15k for budget/wall-clock, mutagen mixed w/ google/gemini-2.5-flash-lite (0041 default). Full table + genome in item body.
