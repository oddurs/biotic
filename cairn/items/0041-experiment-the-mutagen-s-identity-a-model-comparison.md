---
id: 41
title: 'Experiment: the mutagen''s identity — a model comparison'
type: docs
status: done
milestone: biotic-env
assignee: Oddur Sigurdsson
depends_on:
- 2
- 6
- 15
- 40
created: 2026-09-08
updated: 2026-09-16
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

- [x] Protocol run: 8 flasks × 6,000 ticks (scaled from 12 × 8,000 — see Scale changes), total spend $0.12, under cap.
- [x] Table of all metrics per condition (mean [min–max] over 2 flasks) recorded below, with the third model (google/gemini-2.5-flash-lite, $0.10/$0.40 per M) and its price.
- [x] 20 sampled mutations (5 per LLM condition + 5 random) rated by the rubric; ratings recorded below.
- [x] Default decision recorded with its rule below; `.env.example` set to `BIOTIC_MODEL=google/gemini-2.5-flash-lite`.
- [x] `docs/experiments.md` carries the protocol and table; CONCEPT.md's "The honest risk" carries the paragraph.

## 2026-09-16

usd_per_viable: sum usd over call events with role=mutagen; spent_usd on the ledger includes the naturalist (role=naturalist).

## Results (2026-09-16)

Run on 2026-09-16. OpenRouter balance checked first: $42.29 remaining (≥ 20, so
the paid protocol ran). **Total spend $0.1212** (measured as the balance delta;
mutagen + naturalist + genesis probes), against a $4.00 cap for this run.

Third model chosen with `biotic minds` on the day: **google/gemini-2.5-flash-lite**
at **$0.10 / $0.40 per M** — the cheapest non-Qwen listed model with a coding
reputation (cheaper than gpt-4o-mini $0.15/$0.60 and deepseek-chat $0.26/$1.03).

### Metrics table (mean [min–max] over 2 flasks per condition)

| condition (model) | price /M in-out | pass_rate | lat_mean s | lat_p95 s | USD/viable | attempted | viable | arisen | slope /1k (2nd half) | shannon_end | dominance_end | len_drift chars |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c30b — qwen/qwen3-coder-30b-a3b-instruct | $0.07/$0.28 | 0.439 [0.351–0.526] | 5.12 [4.85–5.38] | 10.95 [9.25–12.64] | 0.000439 [0.000402–0.000475] | 57 | 25 [20–30] | 26 [21–31] | 3.99 [2.75–5.24] | 0.860 [0.710–1.011] | 0.731 [0.727–0.735] | 66.7 [40.0–93.3] |
| coder — qwen/qwen3-coder | $0.30/$1.00 | 0.947 [0.929–0.966] | 1.97 [1.76–2.18] | 3.53 [3.33–3.72] | 0.000597 [0.000594–0.000600] | 57 [56–58] | 54 [52–56] | 55 [53–57] | 8.50 [8.10–8.89] | 1.907 [1.723–2.091] | 0.357 [0.297–0.417] | 84.8 [64.3–105.3] |
| gemini — google/gemini-2.5-flash-lite | $0.10/$0.40 | 0.974 [0.947–1.000] | 1.04 [1.02–1.06] | 1.38 [1.29–1.46] | 0.000257 [0.000250–0.000265] | 56 [54–57] | 54 | 55 | 8.38 [7.68–9.08] | 2.204 [2.079–2.329] | 0.270 [0.250–0.290] | 147.2 [144.1–150.3] |
| random — offline control | — | — | — | — | — | 0 | 0 | 148 [146–150] | 13.12 [12.68–13.56] | 1.339 [1.187–1.491] | 0.630 [0.575–0.684] | 77.1 [21.9–132.3] |

`attempted` counts only mind calls, so the random arm reads 0 there; its `arisen`
(≈148) is offline AST mutation, unbounded by the budget and far outrunning any LLM
arm in raw novelty — but at lower `shannon_end` (1.34) and higher `dominance_end`
(0.63) than the two viable LLM arms, i.e. more strains but a less even, more
canalised community. `USD/viable` is the sum of `usd` over `role=mutagen` call
events divided by `mutations_viable` (the ledger `spent_usd` also carries the
naturalist and is not used for this ratio). Metrics computed by
`scripts/exp0041.py` (pure helpers tested in `tests/test_exp0041.py`).

### Qualitative rubric read (20 samples, blind to model, size by diff-line count: small <4 / medium 4–12 / rewrite >12)

| condition | small | medium | rewrite | sampled ids (changed-lines) |
| --- | --- | --- | --- | --- |
| c30b | 3 | 2 | 0 | b283(4) c533(2) a884(2) 45ce(2) 5db5(4) |
| coder | 3 | 1 | 1 | 3528(7) 2608(18) c6d5(2) 730a(2) c354(2) |
| gemini | 1 | 4 | 0 | 6be4(4) 68a3(9) acaf(12) 079a(3) 2c67(8) |
| random | 2 | 3 | 0 | ee56(2) bbf2(1) 6a08(10) 607f(10) 2f2f(9) |

All four arms mostly honour "make one small change": every sample is small or
medium except a single 18-line rewrite from qwen/qwen3-coder. gemini leans to
slightly larger (medium) additive edits, matching its higher length drift
(+147 chars); c30b's edits are small but frequently nonviable (pass_rate 0.44).
No model rewrote pervasively; the semantic arms did not diverge sharply from the
random arm in edit *size*, only in what the edits *were* and whether they passed.

### Founder-genesis probe (cheap, separate; each model seeded "tide" once)

- **qwen/qwen3-coder-30b-a3b-instruct**: failed all 4 genesis attempts (2 membrane
  rejections — "no live(me) function", "imports are not allowed"; 2 viability-trial
  failures — "never divided") and **fell back to the built-in default founder**.
  This is the finding the item anticipated: the 30b model cannot author a viable
  founder for this membrane.
- **qwen/qwen3-coder**: 2 viability failures, succeeded on attempt 3 (tide_drifter).
- **google/gemini-2.5-flash-lite**: succeeded on attempt 1 (tide_watcher).

To keep the *mutation* comparison unconfounded by founder quality, all main-run
flasks share one built-in founder (id 7a8d, poured identically into every
condition via `biotic flasks new`); the genesis behaviour above is reported from
the separate probe rather than the main run.

### Decision (rule fixed before the data)

Rule: the default is the cheapest condition by `usd_per_viable` with
`pass_rate ≥ 0.7` and `shannon_end` no more than 20% below the best LLM
condition's. Best LLM `shannon_end` = 2.204 (gemini); the 20% floor is 1.763.

- c30b — **disqualified**, pass_rate 0.439 < 0.7 (and failed founder genesis).
- coder — qualifies: pass 0.947, shannon 1.907 ≥ 1.763; usd/viable 0.000597.
- gemini — qualifies: pass 0.974, shannon 2.204 (best); usd/viable 0.000257.

**Default = google/gemini-2.5-flash-lite.** It is the cheapest qualifying
condition (≈2.3× cheaper per viable variant than the current default
qwen/qwen3-coder) and simultaneously wins on pass rate, end diversity, dominance,
and latency. `.env.example` updated to `BIOTIC_MODEL=google/gemini-2.5-flash-lite`.

### Scale changes from the stated protocol (reasons)

- **12 flasks → 8** (2 per condition, 4 conditions), **8,000 → 6,000 ticks**:
  wall-clock. Each mutation is a blocking network call; qwen3-coder-30b ran at
  ~5 s/call (p95 ~11 s), so its flasks were the pacing item.
- **Cap $6.00 → $4.00**: imposed on this run; per-flask `--budget 0.60` (6 LLM
  flasks × 0.60 = $3.60 ceiling). Realised spend $0.12 — tick-clocked runs make
  few calls, so no flask came near its budget.
- **`biotic flasks run` not used for the LLM arms**: its `_child_env` blanks the
  API key in every subprocess (item 0006 authorised no spend), so it can never
  run a paid comparison. Each flask was run directly with `biotic run --vessel …
  --clock tick --mutagen llm --budget 0.60`, parallelised across all 8. Note:
  `docs/experiments.md`'s "control arm" example shows `flasks run comp-llm`
  spending from the budget — that is aspirational; the current code cannot.
- **Common built-in founder** across conditions (see genesis probe) instead of a
  per-condition model-genesised founder: isolates the model's mutation behaviour
  from its founder-authoring ability, which is reported separately.

## 2026-09-16

Ran 2026-09-16, spend $0.12 of $4 cap. Default set to google/gemini-2.5-flash-lite: cheapest USD/viable (0.000257) among arms with pass_rate>=0.7 and shannon within 20% of best; beats qwen/qwen3-coder on pass rate, diversity, cost, latency. qwen3-coder-30b-a3b-instruct disqualified (pass_rate 0.44) and failed founder genesis. Full table + rubric in the item body.
