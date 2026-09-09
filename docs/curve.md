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
| `dominance` | float | share of the commonest strain; 1.0 for a monoculture, 0.0 for a sterile dish |
| `mean_gen` | float | mean generation of the living cells, weighted by cell; the founder is generation 0 |
| `arisen` | int, cumulative | strains ever created, founder included |
| `extinct` | int, cumulative | strains that have gone extinct |
| `pheromone` | float | mean pheromone over the agar, 0 to 1 |
| `mutations_ready` | int, gauge | prepared daughters waiting in the mutagen's pool at that tick |
| `mutations_taken` | int, cumulative | divisions that produced a new strain; the count of `arose` events |

Floats are written to four decimals, `mean_gen` to two.

## reading it

The effective number of strains is `e^H`: H = 1.10 means the dish is as diverse
as three equally common strains would be, whatever `strains` says. H counts
strain ids. Two strains that behave identically count as two, and one strain
whose cells carry different `memory` counts as one, so a claim about novelty
needs more than this column.

`dominance` near 1 while `arisen` keeps climbing is a sweep: variants arise and
lose. `dominance` falling while `strains` holds is coexistence. `arisen − extinct`
against `strains` is turnover.

The slope of `arisen` is the rate at which variants are taken up. Until the
mutagen is clocked in ticks it is supply-limited and bound to the wall clock:
the mind is called at most once every `BIOTIC_MUTAGEN_INTERVAL` seconds, so a
run at `--tick 0` sees far fewer variants per tick than `biotic live` does. It is
not a rate of adaptive novelty; a variant that is taken up and starves on the
next tick still counts.

`mutations_taken` counts strains that have a parent. The founder is the only
strain without one, so today it equals `arisen − 1` in every row; the column is
there for when strains can arrive some other way than a mutated division.
`mutations_ready` is the one column that is not a function of the dish: it
samples a pool filled by a background thread on the wall clock, so two replays
of the same run can differ in it and nowhere else. Leave it out when comparing
curves.

The death ledger closes. For a dish inoculated once,
`births − (starved + lysed + senescent + killed) = population − INOCULUM` holds
in every row; `killed` is a column so that it still holds after an antibiotic
disc.

`phase` is the phase the culture believes, not the raw reading: the raw phase
has to hold for 25 ticks before it is logged, so the column lags the population
by up to 25 ticks, and a row that says `log` may already be flattening.

Markers are not columns. Drops, whispers, phase changes and extinctions are in
`vessel/events.jsonl`, each with the tick it happened at; join on `tick`.

## older files

A `curve.csv` written before `killed` and the diversity columns existed has a
nine-column header. The first time the culture appends to such a file it widens
it in place: the missing columns are added to the header in the order above,
every existing row is padded with empty cells, and the file is rewritten through
`curve.csv.tmp` and swapped in, so a crash part-way leaves the original as it
was. It happens once per file and is logged as a `curve` event. Columns the
apparatus does not know, from a file a newer version wrote, keep their place
and are written empty from then on.

One process appends to a vessel's curve at a time. Two cultures sharing a vessel
is not supported.

## in code

    from bio import curve
    rows = curve.read()                          # vessel/curve.csv
    rows = curve.read(Path("flask-2/curve.csv"))

Every row is a dict with every name in `curve.COLUMNS` as a key: ints and floats
parsed, `phase` a string, and `None` where the file has no value, which is what
an older file's rows hold in the new columns. Reading never widens a file. With
pandas, `pd.read_csv("vessel/curve.csv")` gives the same table with `NaN` in
those cells.

`Dish.metrics()` returns what the dish knows on its own: size, diversity, the
death ledger. `Culture.metrics()` adds phase, lineage, turnover and the state of
the mutagen's supply. Both only read; calling either changes nothing in the
dish. `Culture.snapshot()` carries the result under `"metrics"`, which is what
the vitals panel and `biotic status` show.
