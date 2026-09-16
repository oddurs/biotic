# the budget

What a dish spends on the mind, how each call is priced, what happens when
the money runs out, and how a failing endpoint is retried. The point is that
a week-long run has a worst case, and the worst case is a number.

## what is counted

Every call the dish makes: the genesis calls that write the founding cell,
every mutagen call, and every field note the naturalist writes
(`docs/naturalist.md`; about a tenth of a cent a note, one every 600 ticks by
default, `BIOTIC_NOTES_EVERY=0` for none). All of them go through
`Mind.think`, and `Mind.think` is where the budget is enforced, so nothing the
dish does can spend past it. When the budget is spent the mutagen and the
naturalist both stop.

`biotic probe` is not a dish call. It is uncapped, prints what its one call
cost, and records nothing in any dish's ledger; it does fetch and cache the
price list in `vessel/prices.json` like any other call.

## how a call is priced

In order of preference:

1. **The endpoint's own figure.** If the reply carries `usage.cost`, that is
   the price. OpenRouter includes it in every reply; the figure is in credits,
   and a credit is a dollar. Nothing has to be asked for: the
   `usage: {include: true}` parameter older clients sent is documented as
   having no effect.
2. **The price table.** Otherwise `prompt_tokens × prompt + completion_tokens
   × completion + request`, with this model's rates from `vessel/prices.json`
   (below). The table knows nothing of cached-prompt discounts or reasoning
   surcharges, so a table-priced figure is an estimate.
3. **Nothing.** An endpoint that publishes no prices, such as Ollama, is free,
   and spend stays at `$0.000`.

Every call is a `call` event in `vessel/events.jsonl`, and `cost_source` on
the event says which of the three applied: `endpoint`, `table` or `none`.

## vessel/prices.json

    {"fetched_at": 1757300000.0,
     "base": "https://openrouter.ai/api/v1",
     "prices": {"qwen/qwen3-coder": {"prompt": 2.2e-07, "completion": 9.5e-07, "request": 0.0}, ...}}

Rates are dollars per token (`prompt`, `completion`) and dollars per call
(`request`). The file is written after the first *successful* call of a
process, from one `GET /models`; not before the first request, so a dead
endpoint is never asked for its price list and never doubles its error
events. Every later process reads it instead of asking again. It is fetched
again only when the model the dish is using is missing from it, once per
process. An empty table means the endpoint publishes no prices, and is not
refetched.

If `/models` fails and there is no cache, the question stays open: the calls
in between are priced from `usage.cost` or not at all, `cost_source` says
which, and the fetch is tried again after a later reply, but not more often
than every ten minutes. The failure is logged once per process.

The file belongs to the vessel: `biotic sterilize` wipes it with the rest.
Delete it to force a fresh fetch. The first call against a new endpoint is
worth checking by hand against this file: the format above is OpenRouter's,
and another endpoint's `pricing` block may hold something else.

## the budget

A dish has one budget, in dollars, and remembers it. Where it comes from, in
order of precedence:

1. `--budget` on `biotic seed`, `biotic live` or `biotic run`
2. what `vessel/dish.json` remembers from the last save
3. `BIOTIC_BUDGET_USD` in the environment or `.env`
4. `2.00`

The consequence of 2 over 3: once a dish has been saved, changing
`BIOTIC_BUDGET_USD` does nothing to it. `--budget` is the way to change a
dish's budget, and the new value is saved with the dish (every 150 ticks and
at exit), so it sticks.

`--budget inf` (or `BIOTIC_BUDGET_USD=inf`) is no cap; it is stored as
`null`. `0` means no calls at all: the dish grows from the built-in founder
and never varies. A negative value is treated as `0`.

**Exhaustion.** Before every request the mind compares what the dish has
spent with its budget; at or past it, no request is made. The mutagen then
enters the `exhausted` state, logs one event —

    mutagen exhausted at $2.003 / $2.00 — the culture grows on without variation

— and stops asking. The dish keeps ticking. Divisions that roll a mutation
take any daughter still waiting in the pool (a daughter produced by the call
that crossed the line was paid for and is not thrown away); after that they
divide faithfully. `biotic status` and the vitals panel both show the state.

The worst case is therefore the budget plus one call, because the check is
made before a request and the request that crosses the line completes. One
call is at most the prompt plus 1400 completion tokens; with a 2k-token
genome prompt at $1 per million tokens that is a third of a cent.

An exhausted dish resumes exhausted: the state is rebuilt from the ledger and
nothing new is logged. `biotic live --budget 5` raises the cap and the mutagen
picks up where it stopped. Lowering the cap below what is already spent
exhausts the dish at once, and the run says why:

    mutagen exhausted at $0.500 / $0.25 — the budget was lowered below the spend; the culture grows on without variation

A budget that is gone at inoculation is said by `biotic seed`, once, after
the `genesis` event. With `--budget 0` and a key the founder is the built-in
one, a `genesis stopped` event says why, and the exhaustion event reads
`nothing to spend`. When the founding calls themselves spend it — one founder
call that costs the whole budget, or attempts that did not take until nothing
was left — it reads `spent by the founding calls`. `biotic live` and `biotic
run` then take the dish up exhausted and say nothing more.

## backoff

A failed call — an HTTP error, a timeout, an unreachable host, a reply that
cannot be read — puts the mutagen in the `error` state and schedules the next
attempt: 15 s after the first failure, doubling with each consecutive one,
capped at 10 minutes. A success resets the schedule. If the endpoint sends a
`Retry-After` header (HTTP 429 does; so may 503) and it asks for longer than
the schedule would wait, it is honoured, up to an hour.

While the schedule says wait, the mutagen picks nothing: requests from the
dish stay queued, and when the time comes the oldest one whose strain is
still alive is taken. Nothing sleeps inside the failed call, so `ctrl-c` is
never held up by it.

Each failure is one event:

    mutagen call failed: HTTP 503: upstream unavailable — next attempt in 2m00s

with `status`, `retry_in`, `failures` and `latency` on the event. A dead
endpoint produces eleven such events in its first hour, then one every ten
minutes. HTTP 402 — out of credits at the provider — is backed off like any
other error; the retries cost nothing.

## what is logged, and where

- `events.jsonl`, kind `call`: `model`, `prompt_tokens`, `completion_tokens`,
  `usd`, `spent_usd` and `calls` (the running totals after this call),
  `latency`, `cost_source`, and `role` — `genesis`, `mutagen`, `naturalist` or
  `probe` — so the observer's spend can be summed apart from the mutagen's
  (`spent_usd` counts both). Every caller names its role; a call that names
  none is logged as `unknown`, unattributed rather than counted as any one
  role's. `biotic log` prints them. They are bookkeeping:
  in the file, but not among the recent events the eyepiece shows, so one
  call every twelve seconds cannot crowd the dish's own events out of the
  incubator log. `prepared` events are kept the same way.
- `events.jsonl`, kind `mind`: the price-table message once per process, each
  failed call with its `retry_in`, the one `mutagen exhausted` event (with
  its reason when the budget did not run out in the ordinary way: `nothing
  to spend`, `spent by the founding calls`, `the budget was lowered below the
  spend`), and `ledger caught up from the log` when a run found calls the
  last save had missed (below).
- `dish.json`, key `mind`: `model`, `budget_usd` (`null` for no cap),
  `spent_usd`, `calls`, `prompt_tokens`, `completion_tokens`. Written with the
  dish, every 150 ticks and at exit.
- `biotic status`: `spent  $0.043 / $2.00  (12 calls)`, with `— exhausted`
  when it is. `biotic run` ends its progress line with the spend.
- The vitals panel: a `spent` row beneath `mind` reads `$0.043 / $2.00`; the
  mutagen row shows `· exhausted`, or `! error  retry in 45s`.

A process killed between saves — a power cut, a `kill -9` — leaves its last
calls in `events.jsonl` but not in `dish.json`. The next load takes the
running totals from the last `call` event when they are ahead of what the
dish saved: `biotic status` shows the true figure at once, and the next
`biotic live` or `biotic run` logs one `mind` event saying so and saves it.
Loading writes nothing, since `status` may run beside a live dish. If the
true figure is past the budget the dish resumes exhausted, quietly: the
process that spent the money said so. The `call` events are the complete
record either way. A call in flight at the moment of the kill is the one
thing neither holds; the endpoint's own dashboard is the final word.

The log is read from its end: the last 64 KiB — tens of minutes of a busy
dish, and always its most recent calls — and the whole file only when that
holds no `call` at all. A week's log is tens of megabytes, and a load should
not have to read it.
