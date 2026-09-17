# replicate flasks

The whole methodology of the field is replication. Lenski has twelve flasks, and the citrate
result means something *because* eleven flasks did not do it. One `biotic` install can hold many
dishes, so you can run the same experiment many times and read the spread, not a single line.

## one ancestor, many flasks

    biotic flasks new tide --seed "tide" --n 12
    biotic flasks run tide --ticks 5000 --tick 0 --parallel 4
    biotic flasks curve tide --png tide.png

`flasks new` founds **one** ancestor and pours it into `flasks/tide/{01..12}/`, each a complete,
self-contained vessel. Every flask shares the seed, so their **agar is byte-for-byte identical** —
the same nutrient map, poured from the same seeded generator. What differs is a per-flask salt
mixed into the dynamics RNGs: where the founding cells scatter, the order cells step in, the
direction a division reaches for. So the flasks start from the same clone in the same world and
**diverge as they grow**, exactly as replicate cultures of one strain do. This is the Lenski
analogue: same ancestor, same medium, and whatever happens differently happened by chance and
selection, not by a different starting point.

The ancestor is founded once. Flasks `02`..`NN` reuse flask `01`'s genome verbatim — the mind is
never asked again, and never asked at all when it is dormant (the default; see *no spend* below).

Each flask directory is an ordinary vessel: `biotic live --vessel flasks/tide/03` watches one,
`biotic status --vessel flasks/tide/03` reads it, `biotic curve --vessel flasks/tide/03` plots it
alone. `--vessel DIR` (or `BIOTIC_VESSEL=DIR`) points any command at one dish.

## where flasks live

`flasks/<name>/` under the current working directory, or `--dir DIR`, or `$BIOTIC_FLASKS`. Each
set carries a `flasks.json` manifest: the seed, the flask ids, the dish geometry, the biotic
version, and the ancestor's id, name and note. The default is relative to where you run the
command, not the checkout — once `biotic` is `uv tool install`ed, the checkout is read-only.

## separate processes, never threads

`flasks run` spawns **one subprocess per flask** (`biotic run --vessel <dir>`), at most
`--parallel` at once. This is not an implementation detail you may ignore: flasks **must never**
be run as threads in one process. Two reasons, both fatal:

- The per-cell wall-clock budget is a `SIGALRM` timer, and only the main thread receives it.
- The vessel paths (`config.VESSEL`, `config.CURVE`, …) are process-global module state. Two
  vessels active at once in one process would write each other's files.

Each subprocess owns its own main thread, its own process-global config, and its own
`incubator.lock`, so any number of flasks can run at once without touching each other's files.
Within one process, `config.vessel_scope(dir)` acts on another vessel for the length of a `with`
and restores the globals afterward — it is single-threaded by construction, and `flasks new` uses
it to found each flask in turn.

## no spend, by default

`flasks new` founds the ancestor with a **dormant** mind: the built-in fallback founder, no
network call, no dollar spent. `flasks run` runs every flask with the mind turned off in the child
environment (the API keys are blanked so the child cannot re-read them from `.env`), so no
replicate can spend from the project balance and the mutagen never fires. Replicates therefore run
**without variation** — the founder's lineage grows, competes for agar, and crashes, but nothing
mutates.

Awake replicate runs — twelve flasks each with a live mutagen, and a budget shared or split across
them — are a deliberately separate, later concern, because they spend real money and want an
explicit cap. Item 0006 gives you replication of the *dynamics*; it does not turn the mutagen loose
across a dozen flasks.

## reading the spread

`biotic flasks curve <name>` overlays every flask's growth curve on one plot — one coloured line
per flask, in the terminal (braille) or as a PNG (`--png`, the `plot` extra). `--cols` takes the
same column names as `biotic curve` (population by default; `population,nutrient,shannon`, …), one
panel each. `--since TICK` trims the left. The overlay carries no per-flask event markers; it is
about the shape of the replicates against each other, not the events of any one. To read one
flask's markers, plot it alone with `biotic curve --vessel flasks/<name>/<id>`.

## determinism

A flask is as reproducible as any dish. An empty flask id keys the RNGs exactly the way a lone
dish always has, so nothing about a single-vessel run changes. A named flask keys a different but
fully seeded stream, so the divergence between flasks is itself deterministic: `flasks new` twice
with the same seed and the same ids gives the same flasks — **at the same dish geometry**. The
geometry is fixed once per set (fitted to the terminal, unless a size is passed) and recorded in
the manifest, so every flask in a set shares it; but the agar is poured over that grid and its
features scale with the width and height, so two `flasks new` runs on terminals of different sizes
pour different agar from one seed. The mind is the one source of novelty a seed does not fix, and
`flasks run` keeps it off.
