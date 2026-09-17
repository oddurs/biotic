# horizontal gene transfer

Mutation acts on one lineage at a time: the mutagen is handed a genome and hands
back the same genome with one heritable change. Real bacteria do more than that —
they trade genes across lineages through plasmids, transformation and phage, and
that is how a trait crosses from one species to another in a season. Horizontal
gene transfer (`hgt`) is that second channel. With a semantic mutagen it is not
bit-level crossover but *splicing by meaning*: take one behaviour a neighbouring
strain has, and graft it into a strain that does not. It is the largest single
lever the project has on the rate of novelty, and the fast lane for coevolution.
It is the third of the biotic rules in `CONCEPT.md` §1, after predation (`lyse`)
and sharing (`give`).

Like predation, `hgt` is a **feature**: an opt-in rule a dish keeps off unless
you turn it on. A dish that predates this change is untouched, and follows the
exact trajectory it always did — with the feature off no extra random number is
drawn, so a seeded run is byte-for-byte what it was. You switch it on at seeding
or mid-run (below).

Unlike predation, `hgt` adds no cell perception and no cell action. A cell cannot
sense or trigger a splice; it only divides as it always has. Splicing happens on
the mutagen's side, so an hgt-only dish's cell API and mutation prompt are exactly
what they were.

## how a splice happens

On a division that rolls a mutation (probability `MUTATION_RATE`, as ever), a
second roll decides whether that mutation is a splice:

- with probability `HGT_RATE` (0.3) the mutation becomes an HGT request;
- the recipient is the dividing cell's strain, and the **donor** is one random
  adjacent non-kin cell — a cell of another strain in any of the eight
  neighbouring tiles, picked uniformly, so a strain that touches on more sides is
  the likelier donor (contact-weighted);
- if there is **no non-kin neighbour** whose genome the mutagen knows, there is no
  donor, and the request is an ordinary mutation. No contact, no transfer.

When a donor is found, the mutagen is given a second prompt — `HGT_SYSTEM`
instead of the mutation prompt — that hands it the recipient's genome *and* the
donor's, and asks for the recipient's daughter with exactly one behaviour borrowed
from the donor, keeping the recipient's temperament. The reply is parsed and
admitted through the same membrane as any other genome (`docs/membrane.md`): a
splice that comes back identical to the recipient is silent and counts nonviable,
exactly like a silent mutation.

The two rolls and the donor pick are drawn from the culture's own seeded RNG, in a
fixed order — mutation roll, then splice roll, then donor pick — and the last two
sit behind the feature gate. So an hgt-off dish draws exactly what it always did,
and an hgt-on dish's stream is a stable, reproducible extension of it: a saved
dish resumes bit-for-bit, and a seeded run replays.

## what a splice records

A new strain records its `parent` as ever, and now a `donor` too —
`Strain.donor: str | None`, the strain a gene was spliced from. It rides in
`strains.json` and in every freezer sample; an old record without the field loads
with `donor = None`.

- **The fossil.** The header under `vessel/soma/` reads `from <parent> (<id>),
  with a gene from <donor> (<id>).` A strain with no donor keeps the old wording,
  and a revived splice whose donor never existed in this vessel falls back to the
  parent-only line rather than raising.
- **Lineage stays a tree.** `lineage_of` and the `biotic genome` lineage line
  follow `parent` only — a strain has one line of descent. The donor is a separate
  edge, which makes the whole graph a DAG; `biotic genome` prints it as a
  `# donor:` line, and `biotic strains` prints `⇄ gene from <donor>` under the
  strain's note.
- **The census colour** of a splice is the shortest-arc midpoint of its parents'
  hues on the colour circle (so a splice of a red and a blue strain reads as the
  purple between them, and the midpoint of two hues either side of the 0/1 wrap is
  taken the short way), plus the same small jitter every new strain gets. An
  ordinary mutation stays near its parent's hue, as before.

## the two clocks

The mutagen runs on one of two clocks (`docs/experiments.md`), and `hgt` works on
both.

- **The tick clock** (`biotic run`'s default): the dish calls the mind itself,
  synchronously, from the division that rolled the splice. The donor is picked
  from the neighbours present at that instant, so it is always a cell that is
  there. This is the deterministic path, and the one the tests exercise.
- **The wall clock** (`biotic live`'s default): the mutagen is a background thread
  and the dish never waits on it. A division that wants a splice takes a prepared
  one from the pool if the exact `(recipient, donor)` pair is waiting, otherwise it
  queues a request keyed by that pair and divides faithfully. The thread prepares
  it later, and it is taken only when that same pair divides next to each other
  again — real conjugation needs contact. A prepared or pending splice whose pair
  never touches again **lapses after `HGT_EXPIRY_TICKS` (500 ticks)**; on the wall
  clock the mutagen reads the dish clock only about every three ticks, so the
  cutoff is approximate to within a few ticks. Ordinary mutations are pooled by a
  bare strain key and are unaffected.

## turning it on

Off by default. Two ways to switch it on:

    biotic seed "the commons" --with hgt        # on from the founding cell
    biotic drop feature hgt                      # on mid-run, like any drop

`--with` takes a comma-separated list, so `--with lyse,hgt` turns both on. A name
the dish does not know is refused before anything is poured, so a typo never
autoclaves a dish. `drop feature hgt` goes through the inbox like any drop, so on
a running incubator it takes effect when it next drains the inbox, and enabling a
feature already on is a no-op that says so.

Either way it is logged as a `drop` event, marked on the growth curve (`⚗` at that
tick, labelled `feature hgt`; `docs/curve.md`), shown in the eyepiece's incubator
log, and is one of the changes the naturalist is shown.

A splice needs two strains in contact, so `hgt` only does anything once a dish has
diverged into more than one strain and they meet. On a young monoculture it draws
its rolls and finds no donor; the interesting behaviour starts when lineages
collide.

## reading a spliced dish

- **`spliced`** is a new event kind, glyph `⇄`, one per splice, alongside the
  `arose` events ordinary mutations log.
- **`vessel/curve.csv`** gains a cumulative `spliced` column, appended after
  `received` (`docs/curve.md`): the number of strains carrying a donor. Because a
  splice has a parent as well as a donor, it also counts in `mutations_taken` — a
  splice is a kind of mutation — so the two columns are **not disjoint**; do not
  add them together for a total, or splices are counted twice. `biotic curve
  --cols spliced` plots it.
- **`biotic strains`** prints `⇄ gene from <donor>` under a living splice's note,
  and **`biotic genome <id>`** prints a `# donor:` line beside the lineage.
- The naturalist counts `spliced` among the events it may cite; per-interval splice
  tallies in its metrics are a later item (0016, 0041).

## persistence and determinism

`Strain.donor` and `dish.features` both ride in `dish.json` and in every freezer
sample, so a resumed or thawed dish keeps its splices and its rules. The `spliced`
metric is counted from the registry, not a separate counter, so it survives a save
and revives with the strains. The wall-clock pool and its expiry clock are the
running thread's state, not persisted: a resume starts with an empty pool and
re-queues requests as divisions roll them, exactly as a fresh start would.

With the feature off, the splice rolls are never drawn, so a non-hgt dish's RNG
stream is byte-for-byte what it always was. With it on, the draws are seeded and
ordered, so an hgt dish is as replayable as any other.

## a caveat on quality

Whether a splice actually borrows *one coherent behaviour* — rather than blending
the two genomes or rewriting the recipient in the donor's image — is a property of
the mind, not of the plumbing. The tests here prove the plumbing: that a splice
arises on contact and not without it, that it records both parents, that its colour
sits between theirs, and that the curve counts it. What the splices *are* can only
be judged by reading the fossils from a live two-strain dish, which spends real
budget.
