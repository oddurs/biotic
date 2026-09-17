# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). `scripts/release`
turns the `Unreleased` section into a dated release.

## [Unreleased]

### Added

- Sharing, the second biotic rule: a cell can hand energy to a neighbour with `("give", d, x)`.
  The giver loses `min(x, its energy − GIVE_RESERVE)` and never drops below `GIVE_RESERVE` (0.05);
  the neighbour gains `GIVE_EFFICIENCY` (0.9) × that, and the rest is lost as heat. There is no kin
  check — a stranger receives as readily as a sister, which is what makes cheating possible — and a
  gift makes no random roll. Cells gain `me.neighbor_energy`: eight floats, every occupied
  neighbour's energy, kin included (0.0 for empty or glass), so a giver can find a hungry sister
  (a new perception, not a rename of `me.threat`, which stays blind to kin). Sharing is an opt-in
  **feature**, off by default so no existing dish is altered; `biotic seed "…" --with give` turns it
  on from the founding cell and `biotic drop feature give` mid-run (logged and marked on the curve
  like any drop). `vessel/curve.csv` gains cumulative `given` and `received` columns after
  `predated` (net below gross by the heat), and `dish.json` records both totals. `GIVE_EFFICIENCY`
  and `GIVE_RESERVE` are physics constants in `bio/config.py`. See `docs/sharing.md`.
- Predation, the first biotic rule: a cell can burst a neighbour of another strain with
  `("lyse", d)`. The attacker pays `LYSE_COST` (0.05) whatever happens; with probability
  `p = 1 / (1 + exp(-LYSE_K · (E_attacker − E_defender)))` the target bursts (death cause
  `predated`) and the attacker gains `LYSE_YIELD` (0.6) × the target's energy, otherwise it loses
  a further `LYSE_RECOIL` (0.03). Kin are immune (a silent, free no-op), and cells gain `me.threat`:
  eight floats, a non-kin neighbour's energy or 0. Predation is an opt-in **feature**, off by default
  so no existing dish is altered; `biotic seed "…" --with lyse` turns it on from the founding cell and
  `biotic drop feature lyse` mid-run (logged and marked on the curve like any drop). `dish.json` now
  records `dish.features`, and `vessel/curve.csv` gains a cumulative `predated` column after
  `mutations_viable`. `LYSE_K` (2.0) is a physics constant in `bio/config.py`. See `docs/predation.md`.
- A random mutagen — the control arm. `bio/mutagen_random.py` rewrites a genome at the syntax-tree
  level with no mind, no thread and no network: perturb a numeric constant by ±10–50%, flip a
  comparison (`<`↔`>`) or a boolean operator (`and`↔`or`), swap two subscript indices, drop one
  branch of an `if`, duplicate a statement, or swap two return actions — one change per division, at
  one random eligible site. The daughter passes the membrane like any other genome; one that does
  not (a bomb, a throw, or a genome identical to its parent) is refused and the division is faithful.
  `BIOTIC_MUTAGEN=llm|random|mixed` (default `mixed`) and `--mutagen` on `biotic live`, `biotic run`
  and `biotic flasks new` choose the arm, remembered in `dish.json` like `--clock`; in `mixed`,
  `BIOTIC_RANDOM_SHARE` (default 0.25) of rolls go to the random arm. A `--mutagen random` dish
  evolves entirely offline and reproduces on any machine from its seed. Every strain records its
  origin (`llm`, `random`, `hgt`, or null for the founder) in `strains.json` and in the fossil
  header (`arose … by the random mutagen`); the census counts it, `biotic status` shows the arm the
  last run used, and `curve.csv` gains `arisen_llm` and `arisen_random`. See `docs/mutagen.md`.
- Incubation gaps: a dish resumed after more than ten minutes away logs one `gap` event (`incubation resumed after 12h04m`), which `biotic curve` draws as `⋯` at the resume tick; the naturalist's first note after the gap is told the measured off-time, and `biotic status` shows `last active`. `dish.json` now records `saved_at`. Tune with `BIOTIC_INCUBATION_GAP` (seconds). See `docs/curve.md`.
- Replicate flasks: `biotic flasks new <name> --seed "…" [--n 12]` founds one ancestor and pours it
  into `flasks/<name>/{01..NN}/`, each a self-contained vessel of the same seed (so the agar is
  identical) with a per-flask salt in the dynamics RNG (so the trajectories diverge) — Lenski's
  twelve flasks. `biotic flasks run <name> --ticks N [--tick 0] [--parallel P]` runs every flask
  headless, one subprocess each, dormant and spending nothing. `biotic flasks curve <name>` overlays
  their growth curves in the terminal or as a PNG. Flasks live under `flasks/` (or `--dir`, or
  `$BIOTIC_FLASKS`). See `docs/flasks.md`.
- `--vessel DIR` on every command, and `BIOTIC_VESSEL`, to act on one dish among many — e.g.
  `biotic live --vessel flasks/tide/03`.
- The project site at https://oddurs.github.io/biotic/: a StyleX design system, docs with search and a generated CLI reference, the specimen library, field notes with RSS, and Open Graph images. Lives in `web/` and is checked by the same `scripts/task check`.
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
- `biotic curve [--cols population,strains] [--since TICK] [--branch N] [--png OUT] [--width N] [--height N]`:
  the growth curve drawn in the terminal as small multiples — one braille panel per column, population and
  strains living by default — with phase transitions as named rules through the main panel and drops and
  revives as a marker row, joined from `events.jsonl` on `(branch, tick)`; the last branch by default. A long
  curve is downsampled to the lowest and highest row per column of the plot, so no crash or spike is smoothed
  away. `--png` writes the same figure with matplotlib, installed as the optional `plot` extra
  (`uv sync --extra plot`); without it the command says how to install it. It reads `curve.csv`,
  `events.jsonl` and `seed.txt` only and takes no lock, so it runs beside a live incubator.
  `bio.curve.branches()`, `bio.curve.events()` and `bio.plot` are the library form. See `docs/curve.md`.
- The naturalist: every `BIOTIC_NOTES_EVERY` ticks (default 600; `0` turns it off) an observer call to the
  mind writes a field note — three to eight hedged sentences on what changed since the last entry — to
  `vessel/fieldnotes.md` under `## tick N · date time`, logged as a `note` event (`¶` in the incubator log).
  It is shown the readings, the census with the mutagen's notes, births and deaths by cause, the dish's own
  events since the last entry, a coarse sketch of the dish and its own previous entry; never a genome, and
  nothing it writes reaches the mutagen. A sweep — a strain under 10 % at the last entry and over 70 % now —
  is put in its prompt as a computed fact. `biotic notes [-n N]` prints the notebook, `biotic status` counts
  it, and the eyepiece's footer shows the latest entry's first sentence in place of the command help. The
  naturalist runs on its own thread, never touches the dish (a culture with notes walks the same trajectory
  as one without), replaces a look it has not yet written rather than queueing it, takes no look sooner than
  two minutes after the last, backs off from a failing mind like the mutagen, and continues its record across
  a resume and a hard kill; after a revive its next entry says the dish was replaced and compares nothing
  across the seam. Its calls count against the dish budget like any other, about a tenth of a cent each.
  See `docs/naturalist.md`.
- `call` events carry `role`: `genesis`, `mutagen`, `naturalist` or `probe`, so an observer's spend can be
  told from the mutagen's. A call that names no role is logged as `unknown` — unattributed, never folded
  into another role's spend.
- The mutagen's clock. `--clock wall|tick` on `biotic live` and `biotic run`, `BIOTIC_MUTAGEN_CLOCK` per
  process, and `BIOTIC_MUTAGEN_EVERY_TICKS` (default 40). On the tick clock the dish calls the mind itself,
  from the division that rolled the mutation, at most once every that many ticks, and the daughter is born
  in that division; the backoff after a failed call is 2, 4, … 50 intervals in ticks, and a `Retry-After`
  is a floor on the wall clock. The flag sticks to the dish like `--budget`; the environment variable does
  not. `biotic run` prints `mutagen clock: tick, every 40 ticks`, logs it as a `mind` event at every run
  start, `biotic status` shows what the last run used, and the vitals name the clock on the mutagen rows.
  See `docs/experiments.md`.
- `vessel/curve.csv` gains `mutations_attempted` and `mutations_viable` after `branch`: cumulative calls
  made and daughters that passed the membrane. Older files are widened with the rest. The counters, with
  `nonviable` and the tick schedule, are saved in `dish.json`, so they are monotone across a resume.
- `docs/experiments.md`: why the two clocks exist, which command defaults to which, what a value of
  `BIOTIC_MUTAGEN_EVERY_TICKS` means in attempts per flask, and what two flasks must share to be compared.

### Changed

- The default mutagen arm is `mixed`: unless `BIOTIC_MUTAGEN=llm` or `--mutagen llm` is set, a dish
  now sends a fraction (`BIOTIC_RANDOM_SHARE`, default 0.25) of its mutation rolls to the offline
  random mutagen. An existing dish therefore changes trajectory on its next run, and replicate flasks
  (which run dormant) now vary where before they could not. Set `--mutagen llm` to keep the pure-LLM
  behaviour. `strains.json` and strain samples carry a `mutagen` field (older records load with it
  null; a hand-written sample with an unknown origin is refused). `curve.csv` gains two appended
  columns, `arisen_llm` and `arisen_random`; an older curve is widened in place on the next run.
- The fossil record now lives at `vessel/soma/` instead of a top-level `soma/`, so a flask is one
  self-contained directory. `biotic sterilize` and the `vessel/` layout are otherwise unchanged;
  publish a fossil record with `git add -f vessel/soma/`.
- The generated CLI reference now descends into subcommand groups, so `flasks new`, `flasks run` and
  `flasks curve` list their own flags rather than only the top-level `flasks` entry.
- `phase` events in `events.jsonl` carry the phase entered as a `phase` field beside the message.
- `biotic run` defaults to the tick clock and waits for the mind's reply on every attempt: a headless run
  at `--tick 0` is now as long as its calls to the model, minutes to tens of minutes for 5,000 ticks with
  a live endpoint, where before the dish ran past a mind that was called once per several thousand ticks.
  `--clock wall` restores the old behaviour. `ctrl-c` during a call ends the run at the tick boundary.
- The mutagen's `produced` count is `viable` in `Culture.snapshot()`; `viable` and `nonviable` now persist
  across resumes. The vitals' second mutagen row carries the clock as its label; on the tick clock the
  state row reads `every 40 ticks` in place of the pool figures, and the retry countdown is in ticks.
- A `curve.csv` written before this release is widened in place the first time the culture appends to
  it: older rows keep their values and have empty cells in the new columns. Logged once as a `curve` event
  (`≡` in the incubator log). A file re-saved by a spreadsheet, with a byte-order mark, is recognised. A
  file with a row wider than its header is not widened; the culture says so once and leaves it as it is.
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
  for any genome the membrane admits.
- The membrane refuses sets: `set()`, `frozenset`, set displays and set comprehensions, and `set` is no longer in a
  genome's namespace. A set of strings iterates in an order the interpreter's hash seed picks, which differs from
  process to process, so a genome that walked one was the one admitted thing that could diverge from its twin
  across a resume. Dicts are unaffected.
- A thawed dish is held against the static gate again when the culture starts to run: a strain the current rules
  refuse (a bare `except`, a `finally`, a set, a module-level draw, from a vessel saved under 0.1.0) is lysed
  before it can run, its genome leaves the dish, and one `nonviable` event names the strain and the reason.
  `biotic status` and the other readers do not screen, so they show the dish as it is on disk.
- `dish.json` carries the culture's own generator, which rolls the mutations, so a resumed culture rolls them
  at the divisions the running one would have.
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
- What a cell may keep in `me.memory` is a rule of the dish, applied after every `live()`: None, bools, ints,
  floats, strings, and lists, tuples and dicts of those with keys that are strings, numbers, bools or None,
  nested at most `MEMORY_MAX_DEPTH` (16) deep, never the same list or dict in two places, and at most
  `MEMORY_MAX_CHARS` (2048) characters as plain JSON (a tuple as a list, a numeric key as its string; the
  on-disk `~t`/`~d` tags are not counted). A cell that breaks it bursts, before its action applies, and the smoke test refuses a
  genome that does so within its forty rounds with the reason and the round (`memory over 2048 chars as JSON
  (tick 21)`, `memory holds a function; …`, `memory holds one list or dict in two places, …`). `dish.json` and
  freezer samples carry tuples and numeric keys under `~t`/`~d` tags and ints of any width the cap admits, so a
  resumed or revived dish is an exact twin for every admitted genome, whatever it keeps in memory. The 64-key,
  200-character-per-value and `[-2**63, 2**63)` limits are gone. Both constants are physics: a vessel saved
  before this change loads, memory it had already flattened stays flat, and a cell whose memory already breaks
  the rule (aliased rows, nesting past 16, over 2 KB) bursts on the first tick after upgrading. A strain
  sample whose memory breaks it is refused by name before the pre-revive freeze. The mutagen's prompt states
  the rule. See `docs/membrane.md`.
- `biotic sterilize` keeps `vessel/freezer/`; `biotic sterilize --freezer` empties it too.

### Fixed

- Resource bombs the time budget cannot interrupt: the membrane now refuses their literal and
  constant forms statically, regardless of the tick that would run them. The static gate rejects
  `**` with a non-constant exponent (`2 ** me.age`) or a constant one over 1024, whether it folds
  to a number (`2 ** 10**9`) or is too large to carry (`2 ** 10**19`, `2 ** (2 ** 100)`); a
  sequence literal repeated by a large constant in one multiply or a chain of them (`[0] * 10**10`,
  `[0] * 1000 * 1000 * 1000`); and `range()` whose constant length is huge, including a negative
  step (`sum(range(10**12))`, `range(0, -10**12, -1)`) — so a bomb hidden behind `if me.tick > 40:`
  is refused at admission instead of stalling the dish. A float or small integer exponent stays
  legal (`x ** 0.5`, `energy ** 2`, `energy ** (1 / 2)`). The isolated smoke-test child also caps
  its address space and CPU (RLIMIT_AS/RLIMIT_DATA/RLIMIT_CPU; best-effort — macOS cannot lower the
  address-space limit), so a memory bomb whose size is computed at runtime cannot exhaust the box.
  `bio/prompts.py` states the new rules. See `docs/membrane.md`.
- `biotic drop mutagen` no longer shortens the mutagen's call interval for the rest of the run: the ×6
  boost now expires with its 300 ticks on the interval as it always did on the mutation rate, and
  `dish.json` no longer carries `boost: 6.0` forever after.
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
- A genome that kept a tuple, a dict keyed by direction, a list over 200 characters, one row list repeated
  (`[[0] * 8] * 8`) or a counter past 2**63 in `me.memory` came back changed after `ctrl-c` and `biotic live`,
  and lysed or drifted on the first tick.
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
