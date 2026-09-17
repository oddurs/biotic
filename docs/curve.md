# the growth curve

`vessel/curve.csv` is the quantitative record of a run: one row every ten ticks,
written by the culture on the main thread just after the dish steps. Plain CSV
with a header; it opens in anything.

    biotic run --ticks 5000 --tick 0
    open vessel/curve.csv

## columns

Columns are only ever appended, so the order below is stable. The first nine are
what 0.1.0 wrote. "cumulative" means since the dish was inoculated, not since the
previous row.

| column | type | meaning |
| --- | --- | --- |
| `tick` | int | the dish clock |
| `population` | int | living cells |
| `strains` | int | living strains: distinct ids in the census |
| `nutrient` | float | mean nutrient over the agar, 0 to 1 |
| `phase` | text | `lag`, `log`, `stationary`, `death` or `sterile`; debounced, see below |
| `births` | int, cumulative | divisions |
| `starved`, `lysed`, `senescent` | int, cumulative | deaths by cause: out of energy; threw or returned nonsense; older than `MAX_AGE` |
| `killed` | int, cumulative | deaths under an antibiotic disc |
| `shannon` | float | Shannon diversity, H = −Σ pᵢ ln pᵢ over the strain census, in nats; 0.0 for a monoculture and for a sterile dish |
| `dominance` | float | share of the commonest strain (the Berger–Parker index); 1.0 for a monoculture, 0.0 for a sterile dish |
| `mean_gen` | float | mean generation of the living cells, weighted by cell. A strain's generation is the number of mutated divisions between it and the founder, which is generation 0: lineage depth, not cell doublings |
| `arisen` | int, cumulative | strains ever created, founder included |
| `extinct` | int, cumulative | strains that have gone extinct |
| `pheromone` | float | mean pheromone over the agar, 0 to 1 |
| `mutations_ready` | int, gauge | prepared daughters waiting in the mutagen's pool at that tick |
| `mutations_taken` | int, cumulative | divisions that produced a new strain; the count of `arose` events |
| `branch` | int | the vessel's timeline: 0 until the first `biotic revive` of a dish sample, one more after each. A coordinate, not a marker: `(branch, tick)` names a row uniquely once a revive has sent `tick` back through values already in the file. Empty in rows written before the column existed; those were all branch 0 |
| `mutations_attempted` | int, cumulative | calls the mutagen made that got an answer or an error, on either clock; not the calls a dormant or exhausted mind refused before any request |
| `mutations_viable` | int, cumulative | daughters that passed the membrane: into the pool on the wall clock, born at once on the tick clock. At most `mutations_attempted`; `docs/experiments.md` |
| `predated` | int, cumulative | cells burst by a lysing neighbour of another strain; 0 unless the `lyse` feature is on (`docs/predation.md`). Appended after `mutations_viable` |
| `arisen_llm` | int, cumulative | strains that arose by the semantic (LLM) mutagen; `docs/mutagen.md` |
| `arisen_random` | int, cumulative | strains that arose by the offline random mutagen (the control arm); `docs/mutagen.md` |

Floats are written to four decimals, `mean_gen` to two. Four decimals resolve
sustained signalling in `pheromone`: one cell emitting 0.2 every tick holds the
mean near 0.001 on a 72×34 dish (1928 agar tiles), and 0.05 every tick near
0.0004. The mean scales with 1/tiles, and `biotic seed` fits the dish to the
terminal, so a smaller dish reads proportionally higher. A single emission
below 0.1 rounds to `0.0000`. The format is not part of the schema; it can be
widened without a migration.

## reading it

The effective number of strains is `e^H`: H = 1.10 means the dish is as diverse
as three equally common strains would be, whatever `strains` says. H counts
strain ids. Two strains that behave identically count as two, and one strain
whose cells carry different `memory` counts as one, so a claim about novelty
needs more than this column.

`dominance` near 1 while `arisen` keeps climbing is a sweep: variants arise and
lose. `dominance` falling while `strains` holds is coexistence. `arisen − extinct`
against `strains` is turnover.

The slope of `arisen` is the rate at which variants are taken up. It is
supply-limited, and what bounds the supply depends on the mutagen's clock
(`docs/experiments.md`). On the tick clock, `biotic run`'s default, the mind is
called at most once every `BIOTIC_MUTAGEN_EVERY_TICKS` ticks, so the bound is a
property of the run and the same on every machine; `mutations_attempted` is how
many calls were actually made. On the wall clock, `biotic live`'s default, the
mind is called at most once every `BIOTIC_MUTAGEN_INTERVAL` seconds, so a run at
`--tick 0` sees far fewer variants per tick than one at half a second, and two
machines differ. Either way the slope is not a rate of adaptive novelty; a
variant that is taken up and starves on the next tick still counts.

`arisen_llm` and `arisen_random` split `arisen` by which mutagen produced each
strain (`docs/mutagen.md`): `arisen_llm + arisen_random + 1` equals `arisen`, the
`+ 1` being the origin-less founder. On a pure `--mutagen llm` dish `arisen_random`
stays 0; on `--mutagen random` `arisen_llm` stays 0; on `mixed` both climb, and
the ratio tracks `BIOTIC_RANDOM_SHARE`. Overlay them (`biotic curve --cols
arisen_llm,arisen_random`) to watch the two arms side by side.

`mutations_taken` counts strains that have a parent. The founder is the only
strain without one, so today it equals `arisen − 1` in every row; the column is
there for when strains can arrive some other way than a mutated division. On
the tick clock it also equals `mutations_viable`, since a viable daughter is
born in the division that asked for it; on the wall clock a pooled daughter can
expire with its strain, so it is at most `mutations_viable`. `mutations_ready`
is the one column that does not read the dish: it samples a pool that a
background thread fills on the wall clock, and is 0 on the tick clock. Under an
exact replay of the admitted genomes at their original ticks, and of any drops
at theirs, every other column reproduces (`phase` too, if the replay is resumed
at the same ticks, since the debounce restarts with the process); this one need
not. On the tick clock the attempt schedule itself reproduces — the ticks at
which the mind was asked are a function of the seed — so a replayed mind is all
such a replay needs. Drops arrive on the wall clock and change the agar, the
population and the mutation rate; `events.jsonl` records each with its tick, so
a replay can place them. The reproduction holds up to the membrane's wall-clock
budget: a genome that runs over `CELL_TIME_BUDGET` lyses on one machine and may
not on another, and `lysed`, `population` and everything downstream follow it.
Without such a replay, two runs from the same seed diverge in every column from
the first variant taken, because the model's replies are not a function of the
dish. Leave `mutations_ready` out when comparing curves.

The death ledger closes. For a dish inoculated once,
`births − (starved + lysed + senescent + killed + predated) = population − INOCULUM`
holds in every row; `killed` is a column so that it still holds after an antibiotic
disc, and `predated` so that it still holds once predation is on (`docs/predation.md`).

`phase` is the phase the culture believes: the raw phase has to hold for 25
ticks before it is logged, so the column lags the population by up to 25 ticks,
and a row that says `log` may already be flattening. Until a first phase has
held that long there is nothing believed yet, and the column carries the raw
reading; that is the earliest rows of a run, and the first rows after a resume,
since the debounce starts over with the process.

Markers are not columns. Drops, whispers, phase changes, extinctions and revives are
in `vessel/events.jsonl`, each with the tick it happened at; join on `tick` within
a branch. A `phase` event carries the phase entered as a `phase` field beside its
message (`culture entered log phase`); events written before the field have only
the message.

`biotic revive` of a dish sample writes no row of its own. The rows that follow
carry the next `branch` number, and `tick` starts again from the sample's tick:

    tick    branch
    5390    0
    5400    0
    4010    1
    4020    1

A revive to a sample *later* than the dish was at leaves `tick` monotone, so
nothing in that column shows the seam; `branch` shows it either way. Within a
branch `tick` normally climbs, but a crash-resume — which reloads `dish.json` and
re-runs ticks it had already written, without opening a branch — can send it back;
`biotic curve` orders each branch by `tick` before it draws, so every row lands in
its place. Across the file `tick` is not unique, so join events on
`(branch, tick)`. The `revived` dish event — the one with `from` and `was` in its
data — carries the `branch` it opens, and any event's branch is the number of such
events before it in the file, since the log is written in order. When only the
current timeline matters, keep the rows of the last branch. `docs/freezer.md` has
the rest.

## older files

A `curve.csv` written before `killed` and the diversity columns existed has a
nine-column header. The first time the culture appends to such a file it widens
it in place: the missing columns are added to the header in the order above,
every existing row is padded with empty cells, and the file is rewritten through
`curve.csv.tmp` and swapped in, so a crash part-way leaves the original as it
was. It happens once per file and is logged as a `curve` event (`≡` in the
incubator log). Columns the apparatus does not know, from a file a newer version
wrote, keep their place and are written empty from then on.

The file is read as UTF-8 and a leading byte-order mark, which a spreadsheet's
"CSV UTF-8" save prefixes, is ignored, so a curve opened and re-saved in one is
still recognised; a rewrite drops the mark. A file with no header at all, empty
or blank lines only, gets one with the next row. A row with more cells than the
header has no column for the extra ones, and the widening would drop them; such
a file is not widened. It is treated like any other `curve.csv` the culture
cannot read or write (a byte it cannot decode, a disk that refuses), and none of
them stop the dish: the failure is logged once as a `curve` event with the tick
of the first row that was not written and, for a ragged row, its line, every
later row is tried again, and a `resumed` event says when writing works, so a
file repaired while the culture is running picks up from there. The rows in
between are missing.

One process appends to a vessel's curve at a time. Two cultures sharing a vessel
is not supported.

## plotting it

    biotic curve                                   # population and strains living, the last branch
    biotic curve --cols population,shannon,nutrient
    biotic curve --since 4000 --branch 0 --height 16
    biotic curve --png curve.png                   # the same figure through matplotlib

`biotic curve` draws the curve in the terminal. Each column named in `--cols` is
a panel: the first is the tall one (`--height` rows, default 12), the rest are
drawn under it at half that height, all on one tick axis. They are separate
panels rather than traces on one axis because `population` (cells), `shannon`
(nats) and `nutrient` (0 to 1) cannot honestly share a y axis. The default is
`population,strains`. Each y axis runs from 0 to the column's highest value in
the plotted rows; a column that never leaves 0 is drawn on the floor under a
top label of 1. The axis labels use the words of the table above
(`dominance (Berger–Parker)`, `mean generation (lineage depth)`).

The trace is braille, two dots wide and four tall per cell, which needs a font
that has U+2800–U+28FF; the usual monospace fonts do. `--width`
defaults to the terminal's. Piped or redirected, the output is plain text
without colour.

A long curve is downsampled to the width, and the downsampling is chosen so
that it cannot hide anything: every dot column of the plot is a bucket of ticks,
and a bucket keeps its lowest and its highest row, so a one-row crash or spike
is drawn at its full height whether the file has fifty rows or fifty thousand.
The first and the last row are always kept. Buckets are by tick, not by row
count, so a stretch with no rows (the incubator was off, or the curve could not
be written for a while) keeps its share of the axis and is bridged by a straight
line between the rows on either side. Consecutive points are joined by a line
in any case; a single row is a single dot. The PNG plots every row.

Markers come from `events.jsonl`, joined on `(branch, tick)`. A phase change is
a rule (`┆`) through the main panel with the phase's name beside it on the top
row. The rule stands where the culture's *belief* changed, which lags the
population by up to 25 ticks (see `phase` above), and the first believed phase
is never logged, so the segment before the first rule carries no name. When
rules stand closer together than a name's width the name is left out and only
the rule drawn, so a long run with hundreds of transitions shows a thicket of
unnamed rules where they crowd. Under the tick labels is a row of glyphs, the
eyepiece's: `⚗` a drop, `↺` a revive, `⋯` an incubation gap; a column with
several shows the first. Extinctions and strains arising are not drawn: a long
run has thousands, and they are already columns — `--cols extinct,arisen`.

The `⋯` is a `gap` event the culture logs on resume when the dish was away —
between a save and the next `biotic live` — for longer than `BIOTIC_INCUBATION_GAP`
(default 600 s, ten minutes). It is drawn at the resume tick, the tick the dish
left off at: no tick is faked for the time it was off, so the gap is a mark on the
curve, not a stretch of it. The event carries the measured absence
(`incubation resumed after 12h04m`); `docs/naturalist.md` has how the naturalist
is told the same figure.

The plot is of one branch: the last by default, `--branch N` for another (the
error names the branches the file has). A branch's own `revived` event, the one
with `from` in its data, is logged at the sample's tick, before the branch's
first row; it is drawn as `↺` at the left edge, unless `--since` is past its
tick. A strain revived into the current dish is `↺` at its tick; whether it
took is in the log, not the plot. Rows and events of a vessel whose
`events.jsonl` holds dish revives from before the `branch` column existed do
not agree on branch numbers (the rows all read 0); no such vessel is known.

`--png OUT` writes the same figure with matplotlib, one axis per panel at full
resolution with the same markers, and prints `wrote OUT` and nothing else.
matplotlib is the optional `plot` extra: `uv sync --extra plot` in the checkout,
or `pip install 'biotic[plot]'`. Without it the command says so, in those words,
and nothing else in biotic wants it: the organism stays a one-dependency thing.

`biotic curve` only reads, and only `curve.csv`, `events.jsonl` and `seed.txt`:
never `dish.json` or the inbox, and it takes no lock, so it runs beside a live
incubator and beside `biotic live`. A last line torn by a write in progress is
left out of either file. A torn numeric cell that still parses (`12` of `123`)
cannot be told from a whole one and shows as a smaller value for that instant;
the write is one small append, so the window is narrow, and the next run has
the whole row. A file with the original nine columns plots its nine columns
and says `no values for shannon in this file` for a column it does not have.

## in code

    from bio import curve
    rows = curve.read()                          # vessel/curve.csv
    rows = curve.read(Path("flask-2/curve.csv"))

Every row is a dict with every name in `curve.COLUMNS` as a key: ints and floats
parsed, `phase` a string, and `None` where the file has no value, which is what
an older file's rows hold in the new columns. Reading never widens a file, and
cells beyond the header, which have no name to return them under, are left out.
A cell that is not the number its column says, from a hand-edited or truncated
file, raises `ValueError` naming the line and column. That, with the file
errors (`OSError`, `UnicodeDecodeError`, `csv.Error`), is `curve.ERRORS`: what
`reconcile`, `append` and `read` raise for a damaged file, and what a caller
that must not stop on one catches. With pandas,
`pd.read_csv("vessel/curve.csv")` gives the same table with `NaN` in the empty
cells.

    rows = curve.read()
    by = curve.branches(rows)                    # {0: [...], 1: [...]}; a row with no branch is 0
    evs = curve.events()                         # events.jsonl as dicts, each stamped with `branch`

    from bio import plot
    fig = plot.figure(rows, evs, plot.parse_cols("population,shannon"), since=None, branch=None, seed="tide")
    plot.render(fig, width=100, height=12)       # rich.text.Text, ready to print
    plot.png(fig, Path("curve.png"))             # PlotUnavailable, with the install line, without matplotlib

`curve.events()` stamps every event with its branch: the number of dish `revived`
events before it in the file, the opener keeping the branch it carries; a line it
cannot parse is skipped. `plot.figure()` is what `biotic curve` builds: one
`Panel` per column, each holding a list of `Trace`s (one today; an overlay of
several flasks is one per flask), the `Marker`s of the branch, and the tick
range. `render` and `png` are pure functions of it.

`Dish.metrics()` returns what the dish knows on its own: size, diversity, the
death ledger. `Culture.metrics()` adds phase, lineage, turnover and the state of
the mutagen's supply. Both only read; calling either changes nothing in the
dish. `Culture.snapshot()` carries the result under `"metrics"`, which is what
the vitals panel and `biotic status` show.
