---
id: 2
title: Mutagen budget, cost tracking and backoff
type: feature
status: done
milestone: dish
assignee: Oddur Sigurdsson
created: 2026-09-08
updated: 2026-09-08
priority: p0
effort: m
area: bio/mind.py, bio/mutagen.py
---

## Problem

A week-long run is the point of the project, and today nothing bounds what it
costs. `Mind` counts tokens but not money, a failing endpoint is retried every
15 seconds forever, and a rate-limit (HTTP 429) is treated like any other error.
Nobody will leave this running overnight until the worst case is a number.

## Proposal

- `Mind` learns prices. On first use, fetch `/models` once and cache
  `{model: (prompt_usd_per_tok, completion_usd_per_tok)}` in `vessel/prices.json`.
  Expose `mind.spent_usd`. If the endpoint has no pricing (local), spent is 0.
- `BIOTIC_BUDGET_USD` (default 2.00 per dish, persisted into `dish.json` so a
  resumed run remembers). When exceeded the mutagen goes `state = "exhausted"`,
  logs one event, and the dish keeps running without variation. `biotic status`
  and the vitals panel show `$0.43 / $2.00`.
- Exponential backoff on `MindError`: 15s, 30s, 60s … capped at 10 minutes, reset
  on success. On 429 specifically, honour `Retry-After` if present.
- `biotic run --budget 0.50` and `biotic seed --budget` override per dish.

## Acceptance criteria

- [x] `vessel/prices.json` written after the first call; `spent_usd` grows with each call
- [x] A dish with `BIOTIC_BUDGET_USD=0.01` stops mutating after the first call, logs `mutagen exhausted`, and the culture keeps growing
- [x] A dead endpoint produces at most ~10 error events in the first hour, not 240
- [x] `biotic status` prints spent / budget

## 2026-09-08

Budget enforced in Mind.think: Exhausted(MindError) is raised before any request once spent_usd >= budget_usd. One gate bounds genesis, the mutagen, and later callers (0007 naturalist, 0040 mutate_now); the mutagen only adds the exhausted state, one log event, and stops picking work.

## 2026-09-08

Spend persists as dish.json['mind'] (model, budget_usd, spent_usd, calls, tokens), written by Culture.save and read by Culture.load before the mutagen is built, so a resumed dish starts in state exhausted without logging again. Dish.to_dict/from_dict untouched: from_dict reads named keys, so the extra key is ignored by old code and old files load with spent 0.

## 2026-09-08

Cost per call: usage.cost from the reply when present (OpenRouter sends it on every reply; treated as 1 credit = 1 USD), else price table x tokens + per-request fee, else 0. No 'usage: {include: true}' is sent: OpenRouter documents it as deprecated and a no-op. Each call event records cost_source = endpoint|table|none.

## 2026-09-08

Prices are fetched from /models after the first successful reply, not before the first request. A dead endpoint therefore never hits /models, never doubles its error events (AC 3 counts eleven in the first hour), and no lock is held across a request until the endpoint has answered once. A fetch failure with no cache leaves the question open for the next success; with a cache lacking the model, the cache stands.

## 2026-09-08

Backoff is a schedule, not a sleep: Mutagen.failures (consecutive) and Mutagen.retry_at (wall clock); the loop waits for max(interval gap, retry_at) via stop.wait, so close() interrupts it and nothing sleeps inside _mutate. Retry-After stretches the wait upward only, capped at RETRY_AFTER_MAX (3600 s). 0040 can re-express failures in ticks.

## 2026-09-08

Budget precedence: --budget flag > dish.json > BIOTIC_BUDGET_USD > 2.00. The flag is persisted by the save at exit. Consequence, documented: once a dish is saved, editing .env does nothing to it; --budget is the escape hatch. inf = no cap (JSON null); 0 = no calls; negatives clamp to 0.

## 2026-09-08

No special case for HTTP 402 (out of credits): a MindError with status=402, backed off like any error; the retries cost nothing. biotic probe is exempt from the budget (Mind(budget_usd=inf)): it is not a dish call and a probe that fails because of the dish budget would contradict its purpose; it prints what its call cost.

## 2026-09-08

Tick path untouched by construction: no new RNG draws anywhere, bio/dish.py has no diff, Culture.step/_on_divide unchanged; test_growth_is_the_same_with_and_without_a_ledger shows an exhausted dish and a dormant one grow identically for 120 ticks. No timing benchmark: a single run cannot resolve anything below run-to-run noise and the primary checkout's dish must not be used.

## 2026-09-08

Two robustness fixes in scope: _mutate returns quietly when the strain was forgotten during the wait (previously self.genomes[strain] raised KeyError out of run() and ended the daemon thread silently), and _cycle wraps _mutate so an unexpected exception is logged as 'mutagen fault' and backed off.

## 2026-09-08

Watch: the /models pricing format (USD per token as strings, request per call) is assumed from OpenRouter's current responses; parse failures skip the row and negatives clamp to 0, but the first real call against OpenRouter should be checked by hand against vessel/prices.json. fmt_usd prints three decimals, so a call under a tenth of a cent shows as $0.000 while the total in dish.json stays exact. call events share the 200-entry Culture.events deque with visible events; if they crowd the eyepiece on a busy dish, skip them in _load_recent_events and the deque, not in the file.
