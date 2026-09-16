---
id: 2
title: Mutagen budget, cost tracking and backoff
type: feature
status: done
milestone: dish
assignee: Oddur Sigurdsson
created: 2026-09-08
updated: 2026-09-16
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

## 2026-09-09

Revised on review (2026-09-09). The loop no longer picks a strain while backing off: _cycle returns before _pick until clock() >= retry_at, so requests stay queued and the oldest live one is taken when the schedule allows, instead of a strain being picked and held through a wait of up to ten minutes. run()'s two-second wake timeout bounds the poll; stop.wait is used only for the interval gap, so close() still interrupts it.

## 2026-09-09

Mutagen.clock is an attribute (default time.time) and every wall-clock read in the class goes through it; Culture.snapshot()['mutagen']['retry_in'] uses it too. Tests turn it by hand instead of patching the module, and 0040 can install a tick clock the same way.

## 2026-09-09

The price fetch is serialised by its own lock (_price_lock), never the counter lock, so a think() on another thread is not held up for the 15 s a /models request may take. A failed fetch with no cache is not asked again for MUTAGEN_BACKOFF_MAX (600 s): a /models that is down or unimplemented costs at most one attempt per ten minutes, warned once per process; the calls in between are priced from usage.cost or not at all, and cost_source says which.

## 2026-09-09

Checked against OpenRouter's usage-accounting documentation on 2026-09-09: usage: {include: true} is listed under deprecated parameters as having no effect, and usage with cost (in credits) is included in every response. Nothing extra is sent. An endpoint that omits cost falls back to the table and the call event says so in cost_source.

## 2026-09-09

After a hard kill the ledger catches up from the log: Culture.load reads the last call event in events.jsonl (each carries the running spent_usd and calls) and takes it when it is ahead of dish.json, logging one mind event ('ledger caught up from the log'). It happens before the mutagen is built, so a dish that crossed its budget between saves resumes exhausted without a second exhaustion event. It never lowers the ledger, so an old event cannot reset spend. Tokens are not reconciled; the events carry them per call.

## 2026-09-09

Dropped from the earlier draft: a non-JSON 200 reply (Unreadable) was going to be counted as a call with no usage. It is a MindError like any other failure: there is no usage to count and the table would price it at zero anyway. The vitals show spent / budget on their own 'spent' row beneath 'mind' instead of appended to the mind line, which already fills the 48-cell side panel.

## 2026-09-09

Test layout: tests/test_mind.py (the client and the ledger) and tests/test_budget.py (mutagen, culture, status, eyepiece), on a FakeMind that overrides only _request and repeats its last scripted reply. The membrane runs in-process only for tests that opt in with the no_subprocess fixture; the one threaded test (the real run() loop on a real clock) stubs admission instead, because Budget's alarm is main-thread only.

## 2026-09-16

Bookkeeping kinds (call, prepared; HIDDEN in bio/culture.py) are written to events.jsonl but never appended to Culture.events, and _load_recent_events skips them, so one call event every twelve seconds leaves the incubator log's density as it was. Resolves the deque concern from the plan review; the eyepiece filter stays as a second guard.

## 2026-09-16

Culture.load writes nothing: biotic status runs beside a live dish. What load finds out (the ledger caught up from the log, a budget lowered below the spend) waits in Culture._unsaid and is logged by run(), the process that will save the dish.

## 2026-09-16

events.jsonl is read from its last 64 KiB on load (_tail); the whole file only when that holds no call event. A partial read drops its first, probably cut, line. A week's log is tens of megabytes and status should not have to read it.

## 2026-09-16

Lowering the budget below the spend (--budget on a dish that has spent more, or seed --budget 0 on an awake mind) logs one exhaustion event with the reason, through exhausted_msg(); a dish resumed already exhausted logs nothing. A keyless mind with a zero budget is dormant, not exhausted, in status and in the mutagen.

## 2026-09-16

The loop body is Mutagen._turn: _cycle under a last-resort handler for a fault in _fail or _exhaust themselves (a broken log, say). It backs off by the cap and suppresses its own log call, since the log may be what is broken; tested on the main thread by calling _turn.

## 2026-09-16

backoff() clamps its exponent at 60: a week of a dead endpoint is past the thousandth consecutive failure, and 2**failures must not overflow a float.

## 2026-09-16

Rebased onto main after the cairn format 3 migration. The CLI reference (web/apps/site/src/content/docs/reference/cli.mdx) is generated from argparse and checked by scripts/task lint; regenerated for --budget on seed, live and run.

## 2026-09-16

For 0040 (synchronous mutate_now on the main thread): Mind.think may run on the main thread while the mutagen thread is also in think; Mind._lock covers the counters only, and the call must stay outside Dish._apply's SIGALRM Budget block, which is main-thread only and would interrupt the request.

## 2026-09-16

Review fix: the genesis exhaustion event is decided after _genesis(), not before it, so a budget the founding calls spend (one founder call that costs it all, or attempts that did not take until nothing was left) is said at seed time. The reason is 'nothing to spend' when mind.calls == 0, else 'spent by the founding calls'. germinate also sets the mutagen's state to exhausted so a run on the same Culture object says nothing more; load() already rebuilt it exhausted from the saved ledger. Exhausted during genesis returns the default with one 'genesis stopped' event instead of breaking out to 'could not write a founder that grows'.

## 2026-09-16

Review fix: http.client.HTTPException (IncompleteRead, BadStatusLine) joined Mind.think's except tuple. It is not an OSError, so a reply cut short escaped think as itself: caught as a 'mutagen fault' with no status or latency on the mutagen thread, and uncaught in genesis, where it would have ended biotic seed with a traceback. Pre-existing on main; fixed here because docs/budget.md defines a reply that cannot be read as a failed call.

## 2026-09-16

Review fix: biotic run --quiet prints no budget line. --quiet keeps the meaning it had on main: no reporter while it runs; the summary line and 'done in' at the end still print (tests/test_metrics.py pins the summary under --quiet, so stderr is not made empty). The flag has a help string now and the CLI reference was regenerated.

## 2026-09-16

Review fixes to docs: the site's configuration table had BIOTIC_TICK 0.35 and BIOTIC_REPLENISH 0.0004 where bio/config.py reads 0.5 and 0.0025, corrected in place since this branch reflowed the table; docs/budget.md says probe writes vessel/prices.json (the price cache) though it records nothing in a dish's ledger, and that the 64 KiB tail is tens of minutes of a busy dish (a call event is about 300 bytes, so about 220 calls), not hours.

## 2026-09-16

Review fix to tests: test_exhausted_dish_keeps_growing queues a request and turns _cycle by hand after its 150 ticks, so 'no call after the budget was spent' is shown on a path that could have called, not asserted on one that could not; test_a_budget_spent_by_the_founding_calls_is_said_once covers both founding-call cases through germinate, load and one tick of run.

## 2026-09-16

Rebased onto main after #26 (membrane suite). Conflicts in bio/culture.py: load() now both restores the culture RNG (main) and the mind ledger with the log catch-up (this branch); save() writes culture, mind and dish in one blob; run() logs what load found before _screen(). tests/__init__.py from this branch made main's 'from conftest import' fail to collect, so the four suites from #26 import '.conftest' like the rest. The site-e2e bug filed here collided with main's 0046 (site membrane page) and is 0047 now. The gate's web half was run against a throwaway Playwright config on port 6970 because an astro dev from the primary checkout holds 6969 (14 passed); that is exactly 0047.
