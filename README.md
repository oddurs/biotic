# biotic

[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A culture of cells that write themselves, in a dish you can watch.

Each cell in the dish carries a genome: a small Python function, `live(me)`, that
runs once per tick and decides whether the cell eats, moves, divides, signals, or
rests. Agar depletes. Cells starve, age, and burst. Cells that gather energy
divide; their daughters inherit the genome. A language model acts as a
**mutagen**: on a small fraction of divisions, the daughter's genome comes back
slightly rewritten. Selection does the rest.

You place a **seed** — a word, a phrase, a question — and the mutagen writes the
founding cell from it. After that you mostly watch. Every strain that ever arises
is written to `soma/` as a fossil record, so the codebase is, literally, whatever
survived.

## install

Python 3.11 or newer and [uv](https://docs.astral.sh/uv/):

    git clone https://github.com/oddurs/biotic
    cd biotic
    uv sync
    cp .env.example .env         # add an OpenRouter key, or point BIOTIC_BASE_URL at Ollama

`uv run biotic` runs it from the checkout; `uv tool install .` puts `biotic` on your PATH.

## quickstart

    biotic seed "tide"      # inoculate
    biotic live             # watch (ctrl-c to incubate; state is saved)

Without a key the dish still grows, from a built-in founder, but nothing ever mutates.

## the dish

```
 biotic   seed “tide”   tick 1204   0h10m02s   ♥
╭─ agar ────────────────────────────────╮ ╭─ vitals ─────────────────────────╮
│          ·:·∷∷∷:·                     │ │ population  483   25% of agar    │
│       ·:∷●●●●●●∷:·                    │ │             ▁▂▃▅▆▇█████▇▇▇▇      │
│     ·:∷●●●●●●●●●●●∷:                  │ │      phase  stationary           │
│    ·∷●●●●●●●●●●●●●●●:·                │ │    strains  6 living · 14 arisen │
│    ∷●●●●●●●●●●●●●●●●●∷                │ │       agar  ████████░░░░ 0.41    │
│    :●●●●●●●●●●●●●●●●●:                │ │    mutagen  ◐ thinking  2 ready  │
│     ·∷●●●●●●●●●●●●∷·                  │ ╰──────────────────────────────────╯
│        ·:∷∷●●●∷∷:·                    │ ╭─ census ─────────────────────────╮
╰───────────────────────────────────────╯ │ ● 3f1a  tide_drift   gen 3  212  │
╭─ incubator log ───────────────────────────────────────────────────────────╮
│ 14:02:11   1180 ✚ tide_drift arose from slack_water — “now leans into …   │
│ 14:01:50   1162 ✖ mutation of slack_water nonviable — threw on tick 7 …   │
│ 13:59:02   1099 † neap arose went extinct after 212 ticks (peak 40)       │
╰───────────────────────────────────────────────────────────────────────────╯
```

Cells are `●`, coloured by strain (daughters get a hue near the parent's;
dim cells are hungry). Agar shows as ` · : ∷` by richness. Pheromone shows
violet. The phase is computed from the population curve the way a
microbiologist would read it: lag, log, stationary, death.

## interventions

You can lean over the bench while it runs:

    biotic whisper "there is more food at the edges"   # a note the mutagen sees. it may or may not heed it.
    biotic drop nutrient [--at 30,12] [--r 5]          # a drop of broth
    biotic drop antibiotic [--at 30,12] [--r 6]        # a disc that clears a region
    biotic drop mutagen                                # ×6 mutation rate for 300 ticks

And look at what has grown:

    biotic strains [--all]     # census, with the mutagen's one-line note per strain
    biotic genome top          # the dominant strain's code and lineage
    biotic log                 # the incubator log
    biotic status
    cat soma/*.py              # the fossil record

## experiments

    biotic run --ticks 5000 --tick 0     # headless, as fast as it goes
    open vessel/curve.csv                # tick, population, strains, nutrient, phase, births, deaths

`BIOTIC_REPLENISH=0` gives a truly closed dish: bloom, crash, done.
`BIOTIC_MUTATION_RATE`, `BIOTIC_MUTAGEN_INTERVAL`, `BIOTIC_TICK`, `BIOTIC_WIDTH`,
`BIOTIC_HEIGHT` are the other knobs. The rest of the physics is in `bio/config.py`.

## the mind

Any OpenAI-compatible endpoint. `.env`:

    OPENROUTER_API_KEY=...
    BIOTIC_MODEL=qwen/qwen3-coder

Fully local later, with no code change:

    BIOTIC_BASE_URL=http://localhost:11434/v1
    BIOTIC_MODEL=qwen2.5-coder:7b

The dish never waits on the mind. The mutagen runs in a background thread with a
minimum interval between calls; divisions that roll a mutation take a prepared
daughter if one is ready, otherwise queue a request and divide faithfully. So the
rate of novelty is bounded by how fast the mind thinks, and the dish keeps its
own time.

## the membrane

Genomes are untrusted code from a language model running on your machine, so
they pass through `bio/membrane.py` before they can live: no imports (only
`math` and `random` exist), no classes, no dunders, no `open`/`eval`/`getattr`,
a size cap, and a wall-clock budget per call. Then forty ticks against random
situations without throwing. A genome that throws inside the dish bursts the
cell; it doesn't touch anything else.

## layout

    bio/          the apparatus — nothing in here evolves
      dish.py       agar, cells, physics
      membrane.py   what code is allowed to become a cell
      mutagen.py    the background thread that asks the mind for variants
      culture.py    dish + strains + mutagen + your interventions; owns vessel/
      strains.py    lineage, colour, the fossil record
      prompts.py    what the mutagen is told
      tui.py        the eyepiece
    soma/         every strain that ever arose. written by the culture. do not edit.
    vessel/       the running state: seed, dish, strains, events, growth curve, whispers

## development

    scripts/setup                       # once: wires the git hooks, runs the full check
    scripts/agent start feat/my-change  # a branch in its own worktree; prints the path to cd into
    scripts/task check                  # format, lint, tests, build: what CI runs
    scripts/agent pr                    # checks, pushes, opens the pull request

`main` only changes through a merged pull request; the hooks and branch protection enforce
that. `CONTRIBUTING.md` has the rest. `scripts/release <x.y.z>` cuts a release.

## license

[MIT](LICENSE).
