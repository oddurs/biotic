# experiments

How to run flasks whose results can be compared. The one thing that decides it is
the mutagen's clock: what bounds the supply of variants, and whether that bound is
a property of the dish or of the machine it ran on.

    biotic run --ticks 5000 --tick 0             # headless; the mutagen on the tick clock
    biotic run --ticks 5000 --tick 0 --clock wall  # the old behaviour, if you want it
    biotic live --clock tick                     # watch a tick-clocked flask; the eyepiece pauses on each call

## why there are two clocks

The mutagen was built for `biotic live`. A thread calls the mind at most once every
`BIOTIC_MUTAGEN_INTERVAL` seconds (default 12); a division that rolls a mutation
takes a prepared daughter from the pool if one is ready and otherwise queues a
request and divides faithfully. The observer, watching at two ticks a second,
never waits on the network, and one call per twelve seconds is one call per 24
ticks, which is plenty.

That design is wrong for `biotic run --tick 0`, where the dish does hundreds of
ticks a second. One call per twelve seconds is then one call per several thousand
ticks, so almost every roll finds an empty pool. Worse, two runs are not
comparable: the effective mutation rate is `BIOTIC_MUTATION_RATE × P(a daughter is
ready)`, and that probability depends on CPU speed, the endpoint's latency and
`--tick`. A flask run on a laptop and a flask run on a server would have had
different mutation supplies before anything else about them differed.

So there are two clocks, and the command picks the one it is for.

## the wall clock

`biotic live`'s default. The thread, the pool, the queue, exactly as above. The
dish never waits; the rate of novelty is bounded by how fast the mind thinks; a
division's outcome depends on when the reply landed. Two `live` sittings from the
same seed diverge at the first variant taken, and that is fine: `live` is for
watching.

## the tick clock

`biotic run`'s default. There is no thread, no pool and no queue. When a division
rolls a mutation and at least `BIOTIC_MUTAGEN_EVERY_TICKS` ticks (default 40) have
passed since the last call, the dish calls the mind itself, from that division, and
waits for the reply. If the reply passes the membrane the daughter is born in that
division; if it does not, or the call fails, the division is faithful. Rolls inside
the interval divide faithfully. The interval is measured on `dish.tick`, never on
`time.time()`, so with a deterministic mind the attempt ticks, the birth ticks and
the counts are the same at `--tick 0` and at `--tick 0.05`, on any machine, and
across a stop and a resume.

What this costs: **`biotic run` waits on the mind.** Every attempt is a network call
of seconds, up to the mind's 120 s timeout plus the membrane's 20 s ceiling, made
while the dish stands still. At 5,000 ticks and `every_ticks` 40 that is up to 125
calls, and a headless run at `--tick 0` is now minutes to tens of minutes of wall
time, most of it the model's. That inverts what `--tick 0` used to mean, and it is
the point: the wall time went into the model instead of being spent by the dish
running past it. `biotic live --clock tick` pays the same way, and the eyepiece
freezes for the length of each call (the heartbeat pauses, the inbox is not read
until the tick ends). A `ctrl-c` that arrives during a call ends the run after the
tick it interrupted, so the dish saved on the way out is whole.

`biotic drop mutagen` divides the interval by six for its 300 ticks, as it divides
the wall interval, and the boost expires on both clocks.

## which clock, and how to set it

In order of precedence:

1. `--clock wall|tick` on `biotic live` or `biotic run`
2. `BIOTIC_MUTAGEN_CLOCK=wall|tick` in the environment or `.env`
3. the `--clock` the dish remembers from an earlier run
4. the command: `live` on the wall clock, `run` on the tick clock

Only the flag is remembered. `biotic run --clock wall` sticks to the dish like
`--budget`, so a resumed run keeps it; `biotic live` after a headless run is still
on the wall clock, because the dish remembers a flag, not a command. The
environment variable is per process, like `BIOTIC_MUTATION_RATE`: a `.env` set for a
protocol applies to every command in that checkout and leaves nothing in the flask.
A value that is not `wall` or `tick` stops `live` and `run` before the dish starts.

`biotic run` prints the clock on its second line, `mutagen clock: tick, every 40
ticks`, and logs the same words as a `mind` event at every run start. `biotic
status` shows what the last run ran under and whether a flag is remembered:

    mutagen     clock: tick, every 40 ticks  (last run)
    mutagen     clock: wall  (last run)  · --clock wall remembered
    mutagen     clock: not yet run (live: wall, run: tick)

The vitals panel names the clock in the label of the mutagen's second row (`wall
12 viable · 3 nonviable`), and on the tick clock the state row reads `every 40
ticks` where the pool figures would be, since there is no pool.

## BIOTIC_MUTAGEN_EVERY_TICKS

The least number of ticks between calls on the tick clock; default 40; clamped to
at least 1; read per process, never from the dish. What a value means:

- **At most** `ticks / every_ticks` attempts per flask: 125 for 5,000 ticks at 40.
- Fewer under backoff (below), and fewer when divisions are rare. An attempt needs
  a division that rolls a mutation, so a dish in lag or death phase makes fewer
  than the ceiling, and a small dish in stationary phase, where births are
  occasional, may make far fewer. On a 72×34 dish under the built-in founder the
  bloom has hundreds of births per 200 ticks and the stationary phase between 40
  and 170; at the default 6 % roll that is an attempt every 45 to 70 ticks.
  **Report `mutations_attempted`; do not assume the ceiling.**
- The budget bounds it too. A call is a third of a cent or so at a dollar per
  million tokens; 125 calls is under half a dollar; an exhausted budget means no
  call and a faithful division, on either clock. `docs/budget.md`.

Two flasks being compared must share the clock, `every_ticks`,
`BIOTIC_MUTATION_RATE`, the dish size and the founder. A flask on the wall clock and
a flask on the tick clock differ in one more way than their supply: the wall clock
serves the oldest queued request, one per strain, so a rare strain is served as
often as the dominant one; the tick clock serves whichever strain's division rolled
first after the slot opened, so the dominant strain is mutated in proportion to its
share of divisions. A `live` flask and a `run` flask are not the same experiment.

## failure on the tick clock

A failed call (an HTTP error, a timeout, a reply that cannot be read) closes the
slot for 2 intervals, then 4, 8, … up to 50 intervals (2,000 ticks at the default),
reset by the next success. The wait is in ticks so that a dead endpoint does not
stall a fast run: the culture grows on and the log fills at the dish's pace, not the
wall's. Each failure is one `mind` event, `mutagen call failed: HTTP 503 … — next
attempt in 80 ticks`, with `retry_in` in ticks and `unit: "ticks"` in its data.

The one wall-clock input on the tick path: a `Retry-After` from the endpoint (HTTP
429 does; 503 may) is honoured as a floor on the wall clock, up to an hour, during
which no attempt is made and none is counted. The event says so: `next attempt in
80 ticks (Retry-After 1m30s)`. An endpoint that names a wait is stating its own
constraint; the tick schedule is ours. This costs nothing in reproducibility, since
a failing run is not reproducing anyway — its replies differ.

A dead endpoint at `--tick 0` is retried every 2,000 ticks once the schedule is
capped, which is every few seconds: hundreds of error events an hour where the wall
schedule made eleven in the first hour. If that proves too much in practice a
wall-clock floor on the tick backoff is a one-line change; it is not there yet.

## the counters

- `mutations_attempted`, cumulative: calls that got an answer or an error. Calls
  the mind refused before any request (dormant, budget spent) do not count. On
  either clock.
- `mutations_viable`, cumulative: daughters that passed the membrane; into the pool
  on the wall clock, born at once on the tick clock. `viable ≤ attempted`.
- `mutations_taken`, cumulative, derived from the registry: strains with a parent.
  On the tick clock it equals `viable`; on the wall clock it is at most `viable`,
  since a pooled daughter can expire with its strain. `mutations_ready` is 0 on the
  tick clock.
- `mind.calls` in `dish.json` and `biotic status` is the money ledger: every
  answered call including genesis, caught up from the log after a hard kill. It is
  not `attempted`.

The three counters live in `dish.json` with the culture's state, so they are
monotone across a stop and a resume and go back with a `biotic revive`, like
`arisen`. A hard kill loses up to 150 ticks of them, as it does of the dish. The
attempt schedule — the tick of the last call and any backoff — is saved with them,
so a resumed run opens the slot when the unbroken run would have. `docs/curve.md`
has the columns.

## reading two flasks

Join `curve.csv` on `tick` (within a branch; `docs/curve.md`). With the tick clock,
the same seed and a mind that replays its replies, every column reproduces; with a
live model, the supply schedule reproduces and the replies do not, which is the
experiment. What differs between two conditions is then the model's answers and
what the dish did with them, not how many chances the model got.

## the control arm

The tick clock makes the *supply* of variants a property of the run. The mutagen's
*arm* decides where those variants come from: the semantic mind, the offline random
mutagen, or a mix (`docs/mutagen.md`). The comparison the project is built to make —
does the semantic mutagen escape the plateau random mutation reached? — needs both
arms run under the same conditions.

Found one set per arm from one seed, run both, and overlay them:

    biotic flasks new comp-llm    --seed "tide" --mutagen llm
    biotic flasks new comp-random --seed "tide" --mutagen random
    biotic flasks run comp-llm    --ticks 5000
    biotic flasks run comp-random --ticks 5000
    biotic flasks curve comp-random --cols arisen,shannon,dominance

Same seed means the same agar, so the only difference between the sets is the mutagen.
The random set is fully offline — the flasks are dormant, and the random arm needs no
mind — so it costs nothing and runs at whatever speed the box allows; the `llm` set
spends from the budget and is bounded by the tick clock. Compare the shape of `arisen`,
the ceiling of `shannon`, and how long `dominance` sits near 1: that is the plateau
question, asked directly. The write-up of the comparison is items 0038 and 0041.
