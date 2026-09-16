# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). `scripts/release`
turns the `Unreleased` section into a dated release.

## [Unreleased]

### Added

- The project site at https://oddurs.github.io/biotic/: a StyleX design system, docs with search and a generated CLI reference, the specimen library, field notes with RSS, and Open Graph images. Lives in `web/` and is checked by the same `scripts/task check`.

### Added

- Diversity and turnover in the growth curve: `vessel/curve.csv` gains `killed`, `shannon`, `dominance`,
  `mean_gen`, `arisen`, `extinct`, `pheromone`, `mutations_ready` and `mutations_taken`, sampled every
  10 ticks like the rest. `Dish.metrics()`, `Culture.metrics()` and `bio.curve.read()` expose them; the
  vitals panel and `biotic status` show diversity next to the strain count, and `biotic run` prints H in
  its progress line. See `docs/curve.md`.
- A test suite for the membrane, `parse_action`, the physics and persistence (`scripts/task test`): one genome
  per escape class, ten fossils from a real run as the positive control, growth phases and carrying capacity
  under the built-in founder, determinism under a seed, and an exact resume from `dish.json`. Tests never touch
  the network or the real `vessel/`.
- `docs/membrane.md`: every rule with its reason string, what a burst is and why a genome cannot catch it, and
  the membrane's known limits.
- The ledger: every call the dish makes is priced (the endpoint's own `usage.cost` when it reports one, else
  its price list, fetched once from `/models` and cached in `vessel/prices.json`), logged as a `call` event
  with the running total, and saved with the dish in `dish.json`. A dish killed between saves catches its
  ledger up from the log on the next run; `biotic status` shows the caught-up figure without writing anything.
- A per-dish budget: `BIOTIC_BUDGET_USD` (default 2.00), `--budget` on `seed`, `live` and `run`, `inf` for
  no cap, remembered in `dish.json`. When it is spent — by the mutagen, or already by the founding calls at
  `biotic seed` — the mutagen goes `exhausted`, logs one event saying so, and the culture grows on without
  variation. See `docs/budget.md`.
- `biotic status` prints `spent  $0.043 / $2.00  (12 calls)`, the vitals panel has a `spent` row,
  `biotic run` opens with the budget (not under `--quiet`) and ends its progress line with the spend, and
  `biotic probe` prints what its call cost.
- The freezer: `biotic freeze [--label L] [--strain ID]`, `biotic revive TICK | --strain ID [--into fresh|current]
  [--n N] [--at x,y]` and `biotic freezer [--json]`. The dish is frozen at genesis and every `BIOTIC_FREEZE_EVERY`
  ticks (default 2000) as `vessel/freezer/<tick>-<label>.json.gz`; samples are never overwritten. A revive freezes
  the current dish first as `pre-revive`, passes every genome through the membrane again and logs a `revived`
  event; a revived strain is watched for 300 ticks and the log says whether it took. Samples are checked field
  by field when read, so a hand edit that breaks one is refused by name before anything changes. See
  `docs/freezer.md`.
- `vessel/curve.csv` gains a `branch` column after the columns above: 0 until the first dish revive and one
  more after each, so `(branch, tick)` names a row uniquely once a revive has sent `tick` back through values
  already in the file. An older file is widened with the rest; its rows read as empty, which means branch 0.
- `vessel/incubator.lock` is held while a culture runs: freezer commands go through the inbox when the incubator
  is running, and a second `biotic live` or `biotic run` on the same vessel refuses to start, as do `biotic seed`
  and `biotic sterilize`.
- `biotic status` shows the freezer's size and the latest frozen tick, and the incubator's pid when one is running.
- A `freezer` event when an automatic sample cannot be written: said once, tried again at the next cadence, and
  the log says when the freezer is writable again. The dish does not stop for it.
- The eyepiece fits the terminal it is watched from: a dish larger than the window renders at half (or
  third, or quarter) resolution with a `½` badge on the agar panel, the side panel folds into a one-line
  vitals strip when there is no room for it, the incubator log yields rows before the agar does, the
  census lists the strains that fit beside the agar and ends with `… n more`, the header and the footer
  stay on one row with the heartbeat and the `ctrl-c` hint, and resizing mid-run re-fits on the next
  frame. See `docs/eyepiece.md`.
- A frame the eyepiece cannot draw is written once to the incubator log as an `eyepiece` event (`!`),
  with the exception and where it was raised; the dish runs on and `biotic log` says why the eyepiece froze.

### Changed

- A `curve.csv` written before this release is widened in place the first time the culture appends to
  it: older rows keep their values and have empty cells in the new columns. Logged once as a `curve` event
  (`≡` in the incubator log). A file re-saved by a spreadsheet, with a byte-order mark, is recognised.
- A `curve.csv` the culture cannot read or write no longer stops the dish: the failure is logged once as a
  `curve` event, every later row is tried again, and a `resumed` event says when writing works.
- The vitals `strains` row reads `living  arisen  extinct`; the maximum generation it used to show is
  replaced by the cell-weighted mean generation on the new `diversity` row.
- The membrane rejects attributes beginning with `_` (`random._os`), `.format`, `.format_map` and `.mro`,
  `finally`, `with`, `except*`, bare `except:`, `except` clauses that name anything but the six built-in
  exceptions a genome can see, and any binding of those six names (`ValueError = 5`, `def helper(me, KeyError)`,
  `except KeyError as ValueError`). Attributes are read-only: `math.pi = 0` used to change `math.pi` for every
  genome in the process. Module level may hold only `def`s without decorators and constants — numbers, strings,
  tuples, names and arithmetic on them, in assignments, default arguments and annotations alike; no calls, lists,
  dicts or lambdas there. Inside a genome, `random` is the dish's own seeded generator rather than the module, so
  a culture is deterministic under its seed and `random.Random`/`random.SystemRandom` no longer exist there.
- A genome can no longer catch or outlive its time budget: `Lysis` is a `BaseException`, and with no `finally`,
  no `with`, no bare `except`, no `except` outside that list and no way to rebind a name on it, nothing in a
  genome runs after it is raised. The smoke test also budgets module-level code.
- A dish loaded from `dish.json` compiles its genomes again, so module-level code runs a second time. With module
  level held to constants and attributes read-only, everything a genome can change between ticks is in `me.memory`
  or the dish's generator, both of which the save carries, so a resumed dish is an exact twin of the running one
  for any genome the membrane admits (memory JSON can carry; `docs/membrane.md` has the limit).
- The membrane refuses sets: `set()`, `frozenset`, set displays and set comprehensions, and `set` is no longer in a
  genome's namespace. A set of strings iterates in an order the interpreter's hash seed picks, which differs from
  process to process, so a genome that walked one was the one admitted thing that could diverge from its twin
  across a resume. Dicts are unaffected.
- A thawed dish is held against the static gate again when the culture starts to run: a strain the current rules
  refuse (a bare `except`, a `finally`, a set, a module-level draw, from a vessel saved under 0.1.0) is lysed
  before it can run, its genome leaves the dish, and one `nonviable` event names the strain and the reason.
  `biotic status` and the other readers do not screen, so they show the dish as it is on disk.
- `dish.json` carries the culture's own generator, which rolls the mutations, so a resumed culture rolls them
  at the divisions the running one would have. Of `me.memory` it keeps ints in `[-2**63, 2**63)` exactly and
  stringifies wider ones like any other value JSON cannot carry.
- A genome longer than `GENOME_MAX_CHARS` is rejected before it is parsed.
- The mutagen's prompt states the rules the membrane enforces.
- A failing mind is retried with exponential backoff, 15 s doubling to 10 min and reset on success, instead
  of every 15 s; a `Retry-After` header is honoured, up to an hour. While it waits the mutagen picks no
  strain, so requests stay queued and the oldest living one goes first when the schedule allows.
- `MindError` carries the HTTP status and any `Retry-After`; `Exhausted` is the `MindError` raised, before
  any request, once the budget is spent.
- `call` and `prepared` events are kept in `events.jsonl` only, not among the recent events the eyepiece
  shows, so bookkeeping cannot crowd the incubator log. Lowering a dish's budget below what it has spent
  exhausts it at once, with one event saying why.
- `dish.json` stores cell energy at full precision and carries the culture's own state (the mutation-roll RNG,
  the phase detector, a running mutagen boost) under a `culture` key, so a resumed or revived dish continues on
  exactly the trajectory it left. A dish saved before this change resumes, but not bit-for-bit.
- A daughter's memory is a deep copy of its mother's: nested lists and dicts are no longer shared between kin.
  Memory values JSON can carry, lists and dicts included, survive a save unchanged up to 200 characters each
  instead of becoming strings; sets, longer containers and ints outside `[-2**63, 2**63)` still become strings.
- `biotic sterilize` keeps `vessel/freezer/`; `biotic sterilize --freezer` empties it too.

### Fixed

- An empty `curve.csv`, or one holding only blank lines, is given its header with the next row instead
  of being appended to without one.
- `dish.json` no longer rounds cell energy, so a resumed dish follows exactly the trajectory the running one
  would have.
- `parse_action` returns `None` instead of raising on `nan`, `inf` and other values it cannot coerce, and no
  longer turns `("emit", nan)` into a full emission or a bool into a direction or an amount (`("move", True)`,
  `("divide", False)`, `("emit", True)`).
- A `dish.json` that cannot be written no longer stops the culture: the failure is logged once as a `freezer`
  event (`≣` in the incubator log), every later save is tried again, and an event says when writing works.
  Before, a memory int past 4300 digits, which an admitted genome can grow in an afternoon, made the save raise
  at tick 150 and killed the loop; the last good `dish.json` stood.
- The mutagen thread no longer dies when the strain it was about to vary went extinct while it waited; an
  unexpected fault in a cycle is logged and backed off instead of ending the thread.
- `biotic probe` without a key says so instead of printing a traceback.
- A reply the endpoint cut short (`http.client.IncompleteRead`, a malformed status line) is a failed call
  like any other — backed off by the mutagen with its status and latency recorded, one more attempt during
  genesis — instead of an exception that escaped `Mind.think` and could end `biotic seed` with a traceback.
- Watching a dish from a smaller terminal than it was seeded in no longer clips the agar, the census,
  the header's heartbeat or the footer's `ctrl-c` hint silently, and a resize no longer repaints a stale
  frame.
- The incubator log panel no longer drops a frame when the dish or the mutagen logs an event while it
  is being drawn.

## [0.1.0] - 2026-09-09

### Added

- The dish: an elliptical agar grid with nutrient diffusion, pheromone, energetics, senescence, and lysis.
- Genomes as `live(me)` functions, gated by the membrane (static AST rules, a wall-clock budget, a smoke test).
- The mutagen: a background thread that asks any OpenAI-compatible model for daughter genomes on division.
- The eyepiece: a live terminal view of the culture, its vitals, census, and incubator log.
- `biotic seed | live | run | status | strains | genome | log | whisper | drop | minds | probe | sterilize`.
- The fossil record: every strain that ever arose is written to `soma/`.

[Unreleased]: https://github.com/oddurs/biotic/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/oddurs/biotic/releases/tag/v0.1.0
