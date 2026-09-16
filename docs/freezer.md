# the freezer

Lenski's long-term experiment works because every 500 generations a sample of each flask goes
into a -80 °C freezer. When something unexpected evolves, the question *would it happen again?*
is answered by thawing an ancestor and letting it run a second time. biotic's freezer is the
same instrument: a directory of samples under `vessel/freezer/`, and two verbs, `freeze` and
`revive`.

    biotic freeze [--label L]                      # the whole dish, now
    biotic freeze --strain ID [--label L]          # one strain: its genome and one cell's memory
    biotic revive TICK|SAMPLE [--label L] [--yes]  # replace the dish with a dish sample
    biotic revive --strain ID|SAMPLE [--into fresh|current] [--n N] [--at x,y] [--yes]
    biotic freezer [--json]                        # what is in the freezer
    biotic sterilize [--freezer]                   # the freezer survives an autoclave unless you say so

## what is frozen, and when

A **dish sample** is everything the next tick depends on: every cell with its exact energy, age
and memory; the agar and the pheromone; the dish's random state; every living genome; the strain
registry; and the culture's own state (the random stream that rolls mutations, the phase
detector, a running mutagen boost, the revival chain, the strains under watch). It also carries
the naturalist's last note as it stood at the freeze, because the culture's state is saved
whole; a revive ignores that part — the notebook is the vessel's, and the next entry after a
revive says the dish was replaced (`docs/naturalist.md`). Samples are gzipped JSON, about 25 KB
for a 72×34 dish.

Samples are taken:

- at genesis, as `00000000-genesis` — the ancestor of everything that follows;
- automatically every `BIOTIC_FREEZE_EVERY` ticks (default 2000; `0` disables), as `auto`;
- on `biotic freeze`, as `manual` or whatever `--label` says;
- before every revive, as `pre-revive`, so a revive never loses the dish it replaces.

A sample is named `<tick, eight digits>-<label>.json.gz`. A label is 1–32 characters of
`a-z 0-9 _ -`. Nothing in the freezer is ever overwritten: a second sample with the same tick
and label becomes `-2`, then `-3`. This matters after a revive, when the culture runs through
the same ticks a second time — the original `00006000-auto` and the replay's `00006000-auto-2`
are both kept, and comparing them is the whole point.

A freeze is the state at the *end* of the tick named in the file, after that tick's extinctions
and phase changes have been recorded, so sample N is exactly what the running culture was at
tick N. A freeze draws no random numbers and changes nothing in the dish; it costs a few
milliseconds, which every 2000 ticks is not measurable.

## reviving a dish

    biotic revive 4000
    biotic revive 4000 --label pre-revive     # when there are several samples at that tick
    biotic revive 00004000-auto-2             # or name the sample

`revive` resolves what you typed — a tick, a tick and a label, a sample name, or a path — to
exactly one file, and says which names to choose from if there are several. Unless `--yes` is
given it asks before replacing the dish. Then, in order:

1. Every genome in the sample passes the membrane's static gate again. Samples are files
   anyone can edit; a genome that no longer passes stops the revive before anything changes.
2. The current dish is frozen as `pre-revive`.
3. The sample becomes the dish, the registry and the culture state. Prepared daughters in the
   mutagen's pool belonged to the old dish and are dropped.
4. The log gets a `revived` event, at the revived tick: `revived from tick 4000 (the dish was at
   5400) — 483 cells, 6 strains`, with `from`, `was`, `sample` and `branch` in its data. The
   vessel is saved. No row is written to `curve.csv`; the next row is the next multiple of ten
   ticks, and from there on the rows carry the next `branch` number (see below).

The culture remembers how it got here. Every dish carries a `revivals` chain — one entry per
revive, with the tick revived from, the tick the dish was at, and the sample's name — and
`biotic freezer` shows the last hop in its `from` column. A sample frozen from a revived
dish carries the chain with it, so the branching history of a run is never lost. A strain
under watch when the sample was taken is still under watch after the revive: the observation
belongs to the state it was started in, and concludes in the revived timeline.

### a running incubator

While `biotic live` or `biotic run` holds the vessel, it holds `vessel/incubator.lock` too. The
freezer commands notice and hand the request to the running process through the inbox instead
of touching the files themselves:

    the incubator is running (pid 41712); revive queued — taken within 3 ticks. `biotic log` shows the result

The running culture freezes or revives itself on its next inbox check and logs what happened.
A queued request carries the pid of the incubator it was meant for: if that run stops before
the request is taken, the next incubator drops it and says so in the log, rather than freezing
or reviving days later, unannounced. Whispers and drops are not stamped; those are notes on the
bench and keep. When nothing is running, the commands act on the vessel directly.

The same lock means a second `biotic live` or `biotic run` on one vessel refuses to start, and
`biotic seed` and `biotic sterilize` refuse while the incubator is running. The lock is an
advisory `flock`, released by the kernel when the process ends however it ends; there is no
stale pid to clean up. Like the cell time budget it is Unix-only, and on a network filesystem
it may not hold. The file stays behind after a run; it is the lock on it, not its presence,
that means an incubator is running.

### the seed rule

The agar is a function of the seed and the dish size. A vessel that holds a dish keeps its
seed: a dish sample from another seed is refused with `sterilize first`. An empty vessel
(`biotic sterilize` keeps the freezer; the dish is gone) takes the seed of whatever is revived
into it. So a sample carried over from another installation is revived in two steps: autoclave,
then revive. Replicate flasks — several vessels from one install — are their own item on the
roadmap.

## strain samples

    biotic freeze --strain 3f1a
    biotic freeze --strain 3f1a --label before-drop

A strain sample is small and plain JSON: `vessel/freezer/strain-<id>[-<label>].json`. It holds
the strain's record from the registry (id, name, note, genome, generation, hue), the names of
its lineage from the founder down, and the memory of its most energetic living cell — the
closest thing a cell has to a life history. An extinct strain can be frozen too; its memory is
then empty. The sample also records the vessel's seed and dish size, which is what makes a
fresh dish from it the same dish.

The memory is JSON with two tags: a tuple is `{"~t": [items]}`, and a dict with non-string
keys, or a key beginning with `~`, is `{"~d": [[key, value], ...]}` (`docs/membrane.md` has
the format). A sample written by hand with plain lists and string keys is fine and comes back
as JSON gives it. One whose memory breaks the rule the dish applies after every tick — over
2048 characters as JSON, nested past 16, a tuple as a key — is refused by name
(`strain-3f1a: memory over 2048 chars as JSON`), before the pre-revive freeze.

## reviving a strain

    biotic revive --strain 3f1a                      # a fresh dish: same seed, same size, same agar
    biotic revive --strain 3f1a --into current --n 5 --at 30,12   # an invader in the running dish

The genome passes the whole membrane again — the static gate and the smoke test — before it
touches a dish.

Into a **fresh** dish is a germination with a given founder: what `biotic seed` does, with the
sample's strain in place of what the mind would write. The dish that is there is frozen as
`pre-revive`, then the vessel is autoclaved (the freezer is kept), a dish of the sample's seed
and size is poured — the same agar the strain was frozen from — and `--n` cells of the strain
(default 5) are inoculated at the centre exactly as a founder is, each carrying the sampled
memory. The log, the growth curve and the fossil record start over, as they do for any new
culture, and tick 0 goes in the freezer as `genesis`. Because the vessel is autoclaved this
needs a stopped incubator: with `biotic live` running the command says so and does nothing. A
fresh culture starts every random stream from the seed, so reviving the same sample into the
same seed gives the same trajectory every time.

Into the **current** dish, the strain is placed on the `--n` free tiles nearest `--at`
(default: the centre; `--at` goes with `--into current` only, and a point outside the dish is
refused rather than rounded to the rim), the dish's random stream is not touched, and the dish
is frozen first as `pre-revive` all the same — the dish before the invasion is what you will
want to compare against. A strain whose id is already in the registry with the same genome is
simply marked living again; the same id with a different genome is refused. This form works
while the incubator runs, through the inbox.

Either way the culture then **watches** the strain for 300 ticks (`REVIVE_WATCH` in
`bio/config.py`) and writes one more `revived` event:

    revived tide_drift took — 212 cells after 300 ticks
    revived tide_drift did not take — extinct after 41 ticks

*Took* means the strain was still alive when the watch ended; the counts are there so you can
tell a strain that lingered from one that spread. The watch is bookkeeping only. Nothing about
the dish is different for being watched, and the watch list is saved with the dish, so it
survives `ctrl-c` and `biotic live` — the usual way a revived strain is watched.

## what a revive reproduces exactly, and what it does not

Reproduced: the physics. Cells, energies, ages, memories, agar, pheromone, the dish's and the
culture's random streams, the registry's counter and colour stream. A revived dish with a
dormant mind — or any deterministic source of mutations — continues on precisely the trajectory
the original took from that tick, cell for cell, and so does a dish resumed from `dish.json`
after `ctrl-c`. Two things made this true and are worth knowing about: `dish.json` and every
sample store energies at full precision (rounded to four decimals, a saved dish parted from its
twin within a few ticks), and a daughter's memory is a deep copy of her mother's, so kin never
share a list or a dict that a save would then separate.

Not reproduced: the mind. A language model's replies are not a function of the dish, so from
the first mutation onward a live culture diverges from its earlier self. That is the
experiment, not a defect — the same ancestor, replayed, tells you which outcomes were
contingent. `mutations_ready` in the curve samples the mutagen's pool on the wall clock and
differs between replays for the same reason; the timestamps in the log are of course new. The
membrane is applied again on the way in, so a sample from before a rule was tightened may be
refused. A manifest that also replays a run's mutations is its own roadmap item.

What a cell may keep in memory is a rule of the dish, applied after every tick
(`docs/membrane.md`): `None`, bools, numbers, strings, and lists, tuples and dicts of those, at
most 2048 characters as JSON, nested at most 16 deep, never one list or dict in two places. A
cell that breaks it bursts, so at every save every memory is one the sample carries exactly,
and a replay is exact whatever a genome keeps. A vessel saved before this rule resumes as it
did: memory the old save had already flattened to a string stays a string, and a cell whose
memory is over the cap bursts on the first tick.

## reading curve.csv after a revive

`curve.csv` has no marker column; markers live in `events.jsonl`. What a revive leaves in the
curve is a coordinate: the `branch` column is 0 from genesis and one more after every dish
revive, whatever branch the sample itself was taken on. `tick` starts again from the sample's
tick and climbs through values the file already holds:

    tick    branch
    5380    0
    5390    0
    5400    0
    4010    1
    4020    1

A revive to a sample *later* than the dish was at leaves `tick` monotone, so nothing in that
column shows the seam; `branch` shows it either way. Within a branch `tick` is unique and
climbs; across the file it is not, so a join on `tick` alone picks up rows from another
timeline. Join on `(branch, tick)`: the `revived` dish event (the one with `from` and `was` in
its data) carries the `branch` it opens, and any event's branch is the number of such events
before it in the file, since the log is written in order. When only the current timeline
matters, keep the rows of the last branch. `biotic freezer`'s `from` column is a different
thing — the tick a sample's dish was last revived from — and a sample's own `culture.branch`
says which branch it was taken on.

## housekeeping

- `biotic freezer` reads every sample; fine up to a few hundred. `biotic status` shows the count
  and the latest tick from the file names alone.
- `biotic freezer --json` prints the same listing as a list of objects, one per sample.
- An automatic sample the culture cannot write (a full disk, a permissions problem, a file
  where the directory should be) does not stop the dish: it is logged once as a `freezer`
  event, tried again at the next cadence, and the log says when the freezer is writable again.
  A `biotic freeze` you asked for fails loudly instead.
- `biotic sterilize` keeps `vessel/freezer/` (the freezer is not in the flask). `biotic
  sterilize --freezer` empties it too. `biotic seed --fresh` keeps it as well; samples from an
  earlier seed are listed with their seed and cannot be revived into a dish that exists.
- A sample is checked field by field when it is read, and a strain record inside one field by
  field before it is adopted: a hand edit that leaves a field of the wrong shape (a tick that
  is text, a hue outside 0 to 1, an id that is not four hex characters) is refused by name,
  before the pre-revive freeze, and the listing skips a sample it cannot read.
- `soma/` keeps the fossils of every strain that ever arose, including strains of a timeline
  you have since revived away from; the registry in `vessel/strains.json` says which strains
  the current dish knows.
- A 72×34 dish is about 25 KB per sample; at the default cadence a week-long run at two ticks
  a second adds roughly 600 samples, 15 MB.
- `dish.json` now stores cell energies at full precision and the culture's own state under a
  `culture` key. A vessel saved before this change loads, but its first resume is not
  bit-for-bit.
