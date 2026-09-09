---
id: 41
title: 'Experiment: the mutagen''s identity — a model comparison'
type: docs
status: planned
milestone: biotic-env
depends_on:
- 2
- 6
- 15
- 40
created: 2026-09-08
updated: 2026-09-08
priority: p1
effort: l
area: experiments
---

## Problem

Every claim in this project about a "semantic mutagen" is, so far, a claim
about one model: `qwen/qwen3-coder`, chosen by habit and set in
`.env.example`. Models differ in how often they return something the membrane
admits, in how large a change they make when asked for one small one, in what
a viable variant costs, and in how much diversity they leave behind after a
few thousand ticks. CONCEPT.md already names "different models as different
mutagens — UV versus chemical" as a countermeasure to canalisation, but
nobody has measured whether the models differ in the direction that matters.

The default model for every later experiment (0016, 0021, 0028, 0038) should
be chosen from data. The constraint is money: the OpenRouter balance is about
$40 for the whole project, so the comparison itself has to be cheap, bounded,
and stop by itself.

## Proposal

A written protocol, executed, with results recorded in this item and in
`docs/experiments.md`.

Apparatus (all prerequisites, none of them optional):

- tick-clocked mutation supply (0040), so every flask gets the same number of
  attempts regardless of latency: `BIOTIC_MUTAGEN_CLOCK=tick`,
  `BIOTIC_MUTAGEN_EVERY_TICKS=40`
- the budget and price cache (0002), for `spent_usd` per flask and the hard cap
- replicate flasks (0006), for three flasks per condition from one install
- the random mutagen (0015), as the no-model control

Design:

- Seed `"tide"`, replenish default, physics untouched, `--tick 0`,
  8,000 ticks per flask, so each flask makes about 200 attempts
  (`8000 / 40`, fewer under backoff). Three flasks per condition.
- Conditions:
  1. `qwen/qwen3-coder-30b-a3b-instruct` ($0.07 / $0.28 per M tokens)
  2. `qwen/qwen3-coder` ($0.30 / $1.00 per M) — the current default
  3. one cheap non-Qwen model, chosen with `biotic minds` on the day: the
     cheapest listed model with a coder reputation (a small Gemini Flash-Lite,
     a DeepSeek chat model, or a GPT mini). Record which and its price here
     before the run.
  4. `--mutagen random` — the control, zero calls
- Hard cap: $6.00 total across all conditions, enforced as
  `BIOTIC_BUDGET_USD=0.65` per LLM flask (9 flasks × $0.65 = $5.85). If a
  flask exhausts its budget, it runs on without variation to 8,000 ticks
  and the exhaustion tick is recorded; if the project balance reports $6
  spent before all flasks finish, stop, and report the partial table. Do
  not start the run without checking the balance first.

Measured per flask, from `curve.csv`, `events.jsonl`, `strains.json` and
`dish.json`; then mean ± range over the three flasks per condition:

| column | what | source |
| --- | --- | --- |
| `attempted` | mutagen calls made | `mutations_attempted` at the last row |
| `pass_rate` | `mutations_viable / mutations_attempted` (membrane pass rate) | curve |
| `latency_mean`, `latency_p95` | seconds per call | per-call latency logged to `events.jsonl` by 0002 |
| `usd_per_viable` | `spent_usd / mutations_viable` | `dish.json` |
| `arisen` | strains ever created | curve, last row |
| `arisen_slope` | new strains per 1k ticks over ticks 4,000–8,000 | linear fit on curve |
| `shannon_end`, `dominance_end` | diversity and dominance at tick 8,000 | curve |
| `len_drift` | mean genome length of living strains at 8,000 minus the founder's, in characters | `strains.json` |
| `size_small / medium / rewrite` | reader's rating of 5 mutations sampled at random with a fixed seed from the `arose` events, parent and child diffed | rubric below |

Rubric for the qualitative read, written before sampling: *small* — one
constant, comparison, or branch changed, diff under 4 lines; *medium* — one
rule added or removed, diff 4–12 lines, the founder's structure still
recognisable; *rewrite* — the structure is gone or the diff exceeds 12
lines. Read all 20 samples (5 per LLM condition, plus 5 from the random arm
as a calibration) without knowing which model produced them.

Decision rule, fixed here before the data exist: the default experimental
model is the cheapest condition (by `usd_per_viable`) with `pass_rate ≥ 0.7`
and `shannon_end` no more than 20% below the best LLM condition's. If no
condition meets both thresholds, keep the current default and say so.

Then:

- record the full table, the spend, and the decision with the rule that
  produced it, in a note on this item and in `docs/experiments.md`
- set the chosen model as `BIOTIC_MODEL` in `.env.example`
- add a paragraph to CONCEPT.md's "The honest risk" section describing what
  the models actually did with "make one small change": the size
  distribution, the length drift, and whether any model rewrote rather than
  varied

## Acceptance criteria

- [ ] Protocol run to completion (12 flasks × 8,000 ticks) or stopped at the cap, with total spend recorded and under $6.00
- [ ] Table of all metrics per condition (mean ± range over 3 flasks) in this item, including the third model's name and price
- [ ] 20 sampled mutations rated by the rubric, ratings recorded
- [ ] The default model decision recorded with the rule that produced it, and `.env.example` updated to match
- [ ] `docs/experiments.md` carries the protocol and the table; CONCEPT.md's "The honest risk" carries the paragraph
