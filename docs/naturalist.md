# the naturalist

The incubator log is a list of events; nobody reads four thousand lines of `arose` and
`extinct`. What a person reads is what a microbiologist writes in the lab book: what changed
since the last look, what it might mean, hedged. The naturalist is a second use of the mind,
as an observer rather than a mutagen. Every `BIOTIC_NOTES_EVERY` ticks it is shown what the
instruments record and writes the next entry in `vessel/fieldnotes.md`.

    biotic notes [-n N]        # the last N entries (default 5; 0 for the whole notebook)
    biotic status              # notes  3 · last at tick 1800 (2026-09-16 14:02)

## what it is, and is not

It observes. It is told the readings, the census, the dish's own history and its own previous
entry, and asked for three to eight sentences in the plain voice of a field notebook: what is
observable, what changed, with the numbers that matter; interpretation marked as interpretation
and at most one; no mechanisms the record does not show; no ranking of strains; no advice. It
does not grade, and nothing it writes reaches the mutagen — not as a whisper, not as context,
not as a prompt. The observer whispers; the observer does not grade (`CONCEPT.md`).

It never touches the dish. The main thread builds a packet of copies at the look; a daemon
thread named `naturalist` makes the call and writes the entry. The dish does not wait on it,
and a culture with notes walks exactly the same trajectory as one without: building the packet
reads the dish and draws nothing from it, and the suite checks the twins tick for tick.

## the cadence

A look is taken on every tick that is a multiple of `BIOTIC_NOTES_EVERY` (default 600, five
minutes at the default half-second tick) while the mind is awake. `BIOTIC_NOTES_EVERY=0` turns
the naturalist off, and a dormant mind — no key — writes no notes; the mutagen's `dormant`
event already says why.

Two rules bound the cost:

- **One slot, no queue.** A look the thread has not yet written is replaced by the next one,
  never queued behind it. If the mind is slow, notes are fewer, not later.
- **A wall-clock floor.** No look is taken sooner than `NOTES_MIN_SECONDS` (120 s, a constant
  in `bio/config.py`) after the last. At the default cadence and tick this never binds — a
  look every five minutes is well over the floor. At `--tick 0` a dish steps hundreds of ticks
  a second, and the cadence alone would mean one call per reply; the floor caps a headless run
  at thirty notes an hour. A headless experiment that wants none sets `BIOTIC_NOTES_EVERY=0`.

So the number of notes a run produces is a function of wall time and call latency, not of the
seed. Two twins of one seed have identical dishes and can have different notebooks.

## the packet

What the naturalist is shown, field by field, as `Culture._packet` builds it and
`bio.naturalist.compose` sets it against the previous entry:

- the seed; the tick, the phase, the population and its share of the agar, the living strain
  count; diversity `H`, dominance, mean generation, mean agar richness, and the mean pheromone
  when there is any;
- **since the last entry**: the previous tick, the ticks between, what that is at the
  incubator's pace, and the wall-clock time between the two looks; population, strain count,
  `H` and dominance then and now; births and deaths by cause (starved, lysed, of age, killed)
  in the interval; strains arisen and gone extinct in it. On the first entry the prompt says
  there is nothing earlier to compare with;
- **changes worth noting**: computed by the apparatus, not left to the model. Today one
  detector: a *sweep*, a strain under 10 % of the population at the last entry (absent counts
  as nothing) and over 70 % now. Detectors the roadmap adds later extend `remarks()` here;
- the **census**: name, id, generation, cells, share now and share at the last entry (or *new
  since the last entry*), and the one-line note the mutagen wrote when the strain arose; twelve
  strains at most, then one line counting the rest;
- the **incubator log since the last entry**, oldest first, the last twenty of the dish's own
  events: `genesis`, `arose`, `nonviable`, `extinct`, `phase`, `drop`, `whisper`, `frozen`,
  `revived`. Apparatus bookkeeping — `call`, `prepared`, `mind`, `curve`, `freezer`,
  `eyepiece`, and `note` itself — is not shown; it would pull the prose toward the apparatus;
- a **sketch** of the dish, at most 48 glyphs wide, each glyph a k×k block of tiles: letters
  are strains by census rank (`a` the largest; the dominant strain in a block, ties to the
  smaller id, as the eyepiece draws it), `.` `:` `#` agar by richness, blank for bare agar or
  glass, with a legend;
- the **previous entry**, in full, with its tick.

Deliberately absent: every genome. The naturalist never sees code, the cell API, or the rules
of the membrane. Whispers reach it only as `whisper` events in the log, which is what they
are: notes on the bench. `tests/test_naturalist.py` holds the prompt to that.

## the notebook

`vessel/fieldnotes.md` is Markdown, one title and one heading per entry:

    # field notes — “tide”

    ## tick 600 · 2026-09-16 13:57

    Five cells of tide_drifter were placed at the centre of rich agar and have grown to 212 in
    six hundred ticks; the culture entered log phase at tick 340. Nothing has arisen yet. The
    population sits in one colony in the middle of the dish with agar still rich at the edges.

    ## tick 1200 · 2026-09-16 14:02

    The colony has doubled to 483 cells and the phase reads stationary since tick 1040; births
    (900) now run only a little ahead of deaths (412, nearly all starved). Two strains arose:
    slack_water, which by its note drifts when the tile is bare, is 40 cells; tide_drift is 3.
    One reading is that the centre is exhausted and the edge is where the growth is. The agar
    reading has fallen from 0.61 to 0.41.

The heading's time is when the look was taken (local time, to the minute). An entry is one
append, so `biotic notes` beside a running incubator sees whole entries. A reply that comes
back fenced, quoted or under a heading of its own is cleaned to prose, and a line inside an
entry that starts with `#` loses its hashes: `## tick` inside a note would otherwise forge a
heading when the notebook is read back.

`biotic notes` reads the file and nothing else — no dish is loaded, so it works beside a live
dish. With no notes it says so and why: `BIOTIC_NOTES_EVERY=0 — the naturalist is off`, or the
cadence and that the mind must be awake.

## the note event

Every entry is also a `note` event in `vessel/events.jsonl` (`¶` in the eyepiece's incubator
log), with the entry's first sentence as its message and, in its data, `tick` and `at` (the
tick and time of the look, not of the reply), `text`, `branch`, `metrics` and `census` — the
whole baseline the next entry is compared with. That is deliberate: the baseline is also saved
under `culture.naturalist` in `dish.json` every 150 ticks, and a process killed between saves
leaves its last note in the log and the notebook but not in `dish.json`. The next load takes
the baseline from the last `note` event when it observed later than the saved one, as the
ledger is caught up from `call` events; loading writes nothing. The log is read from its tail
only for this — a note the save missed is within 150 ticks of the end — so a dish with no
notes never reads its whole log for them.

## the eyepiece

Once a note exists, the footer of `biotic live` shows the latest entry's first sentence —
`¶ 1800  The colony has doubled to 483 cells…` — in place of the command help (the commands
are in the README and `biotic --help`). The `ctrl-c` hint stays to the right while there is
room; in a narrow window the hint yields first and the note is cut with an ellipsis. No vitals
row shows the naturalist's state: a note that failed or ended is a `mind` event in the log, and
`biotic status` counts the notebook.

## what it costs

One note is one call: about 2 k prompt tokens (the census and the sketch are most of it) and
at most 400 completion tokens. With `qwen/qwen3-coder` at OpenRouter's list price that is
about $0.001 a note, about $0.30 a day at the default cadence. It comes out of the same dish
budget as the mutagen (`BIOTIC_BUDGET_USD`, default $2.00), so a dish with notes exhausts its
mutagen sooner than its twin without, by roughly that much a day. If that bites, a separate
budget for the observer is a small follow-up; today `BIOTIC_NOTES_EVERY=0` is the lever.

`call` events carry `role`: `genesis`, `mutagen`, `naturalist` or `probe`, so the observer's
spend can be summed apart from the mutagen's (`docs/budget.md`).

When the budget is spent the naturalist stops with the mutagen. If its own call finds the
budget gone it says so once — `field notes end at tick 4200 — budget spent ($2.003 / $2.00)`
— and takes no look again in that process; a raised budget (`biotic live --budget 5`) arrives
with a new process, which starts fresh. A failed call is backed off as the mutagen's is, 15 s
doubling to 10 min with `Retry-After` honoured up to an hour, one `mind` event per failure:
`field note at tick 4200 not written: HTTP 503 … — no note before 2m00s`. An empty reply and a
notebook that cannot be written are each one `mind` event and no backoff; the baseline stays
at the last entry that was written, so the record has no gap in its comparisons. A call in
flight at `ctrl-c` is lost: the thread is a daemon and the process exits; the note is neither
in the file nor in the log, and the money is spent, the same gap the ledger documents.

## resume, revive, sterilize

- **Resume.** `ctrl-c` and `biotic live` continue the notebook: the baseline comes back from
  `dish.json` or the log, and the next entry compares with the last one written, however long
  the incubator was off. The prompt gives both the ticks and the wall-clock time between looks
  and says that wall time beyond the ticks is time the incubator was off.
- **Revive.** The notebook is the vessel's, not the sample's. A dish sample carries the
  baseline the culture had when it was frozen, and a revive ignores it: the baseline stays the
  vessel's last entry, marked with a *seam*. The next entry is composed with no deltas and no
  share comparison, and its prompt says the dish was replaced with a frozen sample since the
  last entry; writing that entry clears the seam and comparisons resume from it. A look pending
  when the dish is replaced is dropped; it described the old dish.
- **Sterilize.** The notebook is in the vessel and goes with it. A fresh dish from a strain
  sample (`biotic revive --strain ID`) is a germination and starts a new notebook, as it starts
  a new log.

## the prompt

`NATURALIST_SYSTEM` and `naturalist_user()` are in `bio/prompts.py`, beside the mutagen's. The
prose — hedged, continuous, no advice — is the whole point of the item and is the one thing
the suite cannot check against a live model; the prompt is the only control. Read the first
day's notebook and adjust the system prompt; a prompt change needs no code. What the suite does
check: every prompt after the first carries the previous entry and its tick, a sweep is in the
prompt as a computed fact, the seam sentence replaces the deltas after a revive, and nothing
from the culture's prompts leaks into the observer's.

## in code

    from bio.naturalist import compose, read_notes, remarks, sketch
    read_notes(config.FIELDNOTES)            # [Note(tick, when, text), ...]
    remarks({"a": 95, "b": 5}, census_rows)  # ["b went from 5% to 80% of the population"]
    compose(packet, previous)                # what naturalist_user() renders; pure
    culture.naturalist.latest()              # {"tick", "t", "text"} or None
    culture.naturalist.baseline()            # what dish.json saves under culture.naturalist

The constants — `SWEEP_FROM`, `SWEEP_TO`, `CENSUS_ROWS`, `LOG_LINES`, `SKETCH_W`, `MAX_TOKENS`,
`TEMPERATURE`, `NOTE_EVENTS` — are at the top of `bio/naturalist.py`; `NOTES_EVERY` and
`NOTES_MIN_SECONDS` are in `bio/config.py` with the other bookkeeping, not among the physics.
