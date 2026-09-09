# biotic — where this goes

*Written 2026-09-08, after the first dish.*

## The empty quadrant

Everything that evolves code sits on two axes.

**How mutation happens.** Tierra (1991) and Avida (1993) flipped random bits in
self-replicating machine code. Real things emerged — parasites, hyperparasites,
complex logic features absent from the ancestor — and then stopped. The verdict
of the field is that they "rapidly adapt to and exhaust the possibilities of a
fairly simple environment." In 2022, *Evolution through Large Models* (Lehman,
Stanley et al.) showed that an LLM makes a categorically different mutation
operator: the neighbours of a program in mutation space become *meaningful*
programs. A bit-flip on "follow the scent" gives garbage. An LLM step gives
"follow the scent, but only your kin's."

**What selects.** AlphaEvolve, ShinkaEvolve, OpenEvolve, FunSearch, the
Darwin Gödel Machine: all LLM-mutation, all driven by an objective. A score, an
archive, a best-so-far. They produce software because they are search. They are
not alive and do not try to be. On the other side, Tierra, Avida, Lenia, and the
whole of artificial life: no objective, only an environment. Whatever persists,
persists.

|                          | random mutation      | semantic mutation (LLM)                  |
|--------------------------|----------------------|------------------------------------------|
| **objective / score**    | genetic programming  | AlphaEvolve, FunSearch, DGM, ShinkaEvolve |
| **ecology / no score**   | Tierra, Avida, Lenia | **biotic**                               |

The bottom-right cell is empty. Semantic mutation, ecological selection. A
mutagen that understands what code means, and nobody telling it what is good.
Only the dish decides.

That is the claim, and it is also a research question: *Tierra plateaued because
random mutation in a simple environment runs out of reachable novelty. Does a
mutagen with a prior over all of human programming push past that plateau — or
does the prior canalise everything toward sensible foraging and kill the
weirdness that made Tierra's parasites interesting?* Nobody knows. The dish is
the instrument that finds out.

## What the field already knows about the plateau

The 2016 York workshop on open-ended evolution catalogued the hallmarks the
field is chasing: ongoing novelty, ongoing adaptation, new kinds of interaction,
major transitions in organisation. Tierra's own history points at the mechanism:
the bulk of its evolution was adaptation to the *biotic* environment, not the
physical one. Parasites arose because other programs were there to be
parasitised. The environment that generates novelty is other organisms.

And Lenski's long-term E. coli experiment says what patience looks like. Twelve
flasks since 1988. For 31,500 generations, none of them could eat the citrate
that had been in the medium the whole time. Then one did — and only after
earlier, invisible, *potentiating* mutations had made it possible. Replay from
frozen ancestors before the potentiation and it doesn't happen again. That is
historical contingency, and it is the texture this project should have: long
stretches where the curve is flat, and then something that could not have been
scheduled.

## The arc

Each stage is a different kind of thing to *watch*, not a feature list.

### 0 · Metabolism — what exists now

Cells versus agar. Growth curves with real phases. Selection on foraging
strategy. In the first run, a mutant that ignored pheromone and moved toward
food more aggressively swept from one cell to 91% of the dish. Output: a growth
curve, a fossil record, an incubator log. Not yet software.

### 1 · The biotic environment

Make cells matter to each other, so the environment stops being a nutrient field
and starts being other code.

- **Predation.** `("lyse", d)` — burst a neighbour, take some of its energy.
  Now there is a reason to be armoured, to be fast, to be poisonous.
- **Sharing.** `("give", d, x)` — energy to a neighbour. With `me.kin` this is
  the seed of cooperation, and with cheaters, of its collapse.
- **Horizontal gene transfer.** The big one. On division, with some
  probability, the mutagen is handed a *neighbour's* genome too and asked to
  splice: take the scent-following from that strain and the division rule from
  this one. This is exactly how antibiotic resistance crosses species in real
  microbiology, and with a semantic mutagen it becomes semantic recombination.
  Now coevolution has a fast lane, and arms races become possible.

### 2 · The agar becomes chemistry — this is where the output becomes software

The answer to "is it software?" without turning into AlphaEvolve.

Real agar is not "nutrient." It is glucose, and lactose, and citrate, and each
one needs a different metabolic pathway to eat. A bacterium that evolves a new
pathway does not win a leaderboard; it opens a **niche** nobody else occupies.

So: the dish holds several **substrates**, laid down in patches like the agar
blobs are now. Each substrate is a small computational task — a stream to
predict, a structure to parse, a sequence to sort, a string to compress, a
function to approximate. A tile of substrate *X* offers a sample. A cell
metabolises it by returning `("digest", answer)`; energy comes back in
proportion to how correct the answer is. Wrong answers cost. The physical
nutrient stays as the cheap, contested baseline.

What this does:

- **The genome of a strain that eats substrate X is a working program for X.**
  Found by ecology, not optimisation: it arose when a niche was empty, it
  competes, it gets displaced, it coexists. `soma/` becomes a library.
- **No global fitness.** Specialists and generalists. Speciation by diet. A
  strain that solves *X* badly but eats it alone can outlive one that solves
  *X* well in a crowd.
- **The citrate experiment, in an evening.** `biotic drop substrate <task>`
  while the dish runs. Does anything evolve to eat it? How long? Which strain?
  Did it need a potentiating mutation first? Freeze the ancestor, replay,
  see if it happens again.
- **The seed finally has teeth.** Today it inflects temperament. Here the mind
  derives the *substrate chemistry* from it. "tide" gives periodic streams to
  predict. A question as a seed gives substrates that are the sub-problems of
  answering it. A seed is a world, not a mood.

### 3 · Secretions — the dish, not the cell, is the program

Bacteria secrete enzymes. An extracellular enzyme breaks a complex substrate
into simpler pieces the secretor and its neighbours can eat. It is a public
good, which invites cheaters, which invites policing — the whole drama of
cooperation runs on secretions.

In biotic: `("secrete", partial)` leaves an *intermediate* on the tile — the
output of a step toward digesting the substrate. Other cells can digest the
intermediate. Nobody has to solve the whole task; a strain can live by doing one
step of it well and leaving the rest.

This is compositional software emerging from ecology. A pipeline of strains,
each doing a stage, none of them designed to fit together. The dish as a whole
computes something no cell can. The map of who-eats-whose-secretions **is the
architecture** — and it was grown, not drawn. This is the point at which the
first sentence of the project, "an app that slowly builds itself," becomes
literally true, and in a way no orchestrator could produce.

### 4 · Major transitions — make them possible and wait

The York hallmark nobody has convincingly hit. Don't build these; remove the
obstacles and observe.

- **Multicellularity.** Kin that pool energy and memory and move as one. A
  biofilm. If `give` and `kin` exist, the question is whether it evolves.
- **Endosymbiosis.** A genome incorporating another's as a subroutine — HGT
  taken to its limit. The mutagen can already do this; the question is whether
  selection keeps it.
- **Plasmids.** Genes that travel separately from the genome. Selfish code.

### 5 · The mutagen evolves

ELM's third component was fine-tuning the model on what survived. The cheap
version: the mutagen's context includes the fossil record, so it learns the
dish's dialect. The deep version: strains carry heritable *mutator* traits —
rate, temperature, which model — and the evolution of evolvability becomes
visible. Mutator strains are real; in Lenski's flasks several lineages evolved
hundred-fold higher mutation rates and paid for it later.

And, straight from Sakana's ASAL: a foundation model as the **observer**. A
naturalist that periodically looks at the dish and writes field notes. *"At
tick 41,200 a strain in the northeast began emitting only when starving. Within
a few ticks its kin were moving toward it. This resembles a distress signal."*
Hedged, anthropomorphic, and exactly how a microbiologist reads a plate. The lab
notebook writes itself, and it is the one output a human will actually read.

## What a run produces, in the end

1. **A strain library** — `soma/`, every genome that ever lived, and for each
   one what it ate. With substrates, this is working code, indexed by problem.
2. **A lab notebook** — the incubator log plus the naturalist's field notes.
3. **Curves** — population, diversity, substrate uptake, by tick. Figures.
4. **A freezer** — `biotic freeze` snapshots a strain or the whole dish;
   `biotic revive <id> --at <tick>` replays from it. Lenski's frozen fossil
   record. The thing that makes contingency testable.
5. Eventually, **pipelines** — grown architectures, readable as
   who-eats-what graphs.

That is a paper-shaped object: a question (the seed), a method (the dish
config), observations, figures, and a claim. Runs are cheap — one small-model
call every few seconds — so runs can be weeks long, and there can be twelve
flasks.

## What it must never become

A leaderboard. The moment there is a global score, this is AlphaEvolve with
extra steps and worse sample efficiency. Its entire value is being the other
thing: the place where you find out what code does when nobody tells it what
to do. Interventions are drops on the agar, not reward functions. The observer
whispers; the observer does not grade.

## The honest risk

The LLM's prior may be a canaliser, not a liberator. Every mutant may be a
sensible variation on sensible foraging, and the dish may converge to one
reasonable strain and sit there — the opposite of Tierra, which produced things
no human would write. Countermeasures exist (high temperature, "vary toward
things that seem bad," a fraction of random-token mutations, different models
as different mutagens — UV versus chemical), but whether they suffice is
unknown. That uncertainty is not a flaw in the project. It is the experiment.

## Next, concretely

1. **Substrates** (stage 2). One substrate type first — a numeric stream to
   predict — as a second layer over the existing agar. Smallest change that
   makes `soma/` contain software.
2. **HGT** (stage 1). Nearly free: hand the mutagen a neighbour's genome some
   fraction of the time.
3. **Freeze / revive.** The dish is already serialisable; this is bookkeeping.
4. **The naturalist.** One extra model call every few hundred ticks, writing to
   `vessel/fieldnotes.md`.
5. Then secretions.

## Sources

- Lehman, Gordon, Jain, Ndousse, Yeh, Stanley — *Evolution through Large Models* (2022). https://arxiv.org/abs/2206.08896
- Zhang, Hu, Lu, Lange, Clune — *Darwin Gödel Machine* (2025). https://arxiv.org/abs/2505.22954
- Lange et al. — *ShinkaEvolve* (2025). https://arxiv.org/pdf/2509.19349 · AlphaEvolve: https://en.wikipedia.org/wiki/AlphaEvolve
- Taylor, Bedau, Channon et al. — *Open-Ended Evolution: Perspectives from the OEE Workshop in York* (2016). https://direct.mit.edu/artl/article/22/3/408/2841
- Blount, Borland, Lenski — *Historical contingency and the evolution of a key innovation in an experimental population of E. coli* (2008). https://www.pnas.org/doi/full/10.1073/pnas.0803151105
- Ray — Tierra; parasites and hyperparasites. https://tomray.me/pubs/news/LocalCopy/OutOfControl15.html
- Avida and complex features. https://alife.org/encyclopedia/digital-evolution/avida/
- Kumar, Lu, Kirsch, Tang, Stanley, Isola, Ha — *Automating the Search for Artificial Life with Foundation Models* (ASAL, 2024). https://sakana.ai/asal/
- *OpenLife: Toward Open-World Artificial Life with Autonomous LLM Agents* (2026). https://arxiv.org/html/2606.31046v1
