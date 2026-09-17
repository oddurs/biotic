# predation

Until now a cell could act on the agar and on itself — eat, move, divide, emit,
rest — but never on another cell. Predation is the first rule that makes one
cell's code matter to another's: `("lyse", d)` bursts the neighbour in direction
`d` and takes some of its energy. Now there is a reason to be armoured, to be
fast, to flee, to be worth less than the attack costs. It is the first of the
biotic rules in `CONCEPT.md` §1; sharing (`give`) and horizontal gene transfer
(`hgt`) come next, and coevolution — the arms race — is item 0016.

Predation is a **feature**: an opt-in rule a dish keeps off unless you turn it
on. A dish that predates this change is untouched, and behaves exactly as it
did. You switch it on at seeding or mid-run (below).

## the action

    ("lyse", d)     attack the neighbour in direction d (0=N 1=NE … 7=NW)

The attacker pays `LYSE_COST` (0.05) whatever happens. Only a cell of **another
strain** can be lysed; against an empty tile, the glass wall, or a cell of the
attacker's own strain the action does nothing and costs nothing — a silent
no-op that never even rolls. That is `me.kin` earning its keep: kin are immune.

When the target is a valid prey, the attack bursts it with probability

    p = 1 / (1 + exp(-LYSE_K · (E_attacker − E_defender)))

a sigmoid on the energy difference, with `LYSE_K` (2.0) the steepness. The more
energy the attacker holds over the target, the likelier the burst; equal energy
is a coin flip. Energies run 0 to `MAX_ENERGY` (2.0), so the argument stays
within ±4 and `p` within about 0.02 to 0.98 — there is always a chance either
way, and no overflow. The odds use the energies as the genome perceived them,
before the cost is charged.

- **On a burst:** the target dies with cause `"predated"` and its tile returns
  the usual necromass to the agar (as any death does). The attacker gains
  `LYSE_YIELD` (0.6) times the target's energy — a fraction, not all of it; the
  rest is lost, as in a real lysis.
- **On a miss:** the attacker loses a further `LYSE_RECOIL` (0.03) on top of the
  cost. Attacking up is expensive.

The attacker is an ordinary cell taking its turn, so the tick's usual clamps
apply to it afterwards: energy at or below 0 starves it, energy over `MAX_ENERGY`
is capped. A target burst earlier in the same tick is simply gone when its own
turn would have come; nothing acts twice.

The four constants live in `bio/config.py`. `LYSE_K` is a physics constant like
the others there: changing it changes every dish that runs afterwards.

## what a cell perceives

Predation adds one perception, present on every cell whether or not the feature
is on (it costs one list append in the neighbour scan) but only documented to
the mutagen when it is:

    me.threat      8 floats: the energy of each neighbour that is a cell of
                   another strain, clockwise from north; 0.0 where the tile is
                   empty, the glass wall, or a cell of my own strain.

`me.threat` is the perceptual basis for both attacking and fleeing: the argmax
is the richest prey and the nearest danger at once. Nothing else about a
neighbour is exposed — not its strain, not its age, not its genome. A cell knows
a stranger is there and how much energy it holds, and that is all.

## turning it on

Off by default. Two ways to switch it on:

    biotic seed "wolves and sheep" --with lyse    # on from the founding cell
    biotic drop feature lyse                       # on mid-run, like any drop

`--with` takes a comma-separated list (`--with lyse` today; `give` and `hgt`
join it in later items). A name the dish does not know is refused before
anything is poured, so a typo never autoclaves a dish.

`drop feature lyse` is an intervention like `drop nutrient` or `drop mutagen`:
it goes through the inbox, so it takes effect when a running incubator next
drains it — the same timing every drop has. On an idle dish it is queued, not
applied, so `biotic status` will not show it enabled until the next `biotic
live` or `biotic run`. Enabling a feature already on is a no-op that says so.

Either way it is logged as a `drop` event, which means it is marked on the
growth curve (`⚗` at that tick, labelled `feature lyse`; `docs/curve.md`), shows
in the eyepiece's incubator log, and is one of the changes the naturalist is
shown. Seeding with `--with lyse` writes that mark at tick 0.

When the feature is on, the mutagen's and the genesis prompts gain a clause
documenting `me.threat`, `("lyse", d)`, the odds and the four constants, so a
strain can evolve to use it. With the feature off the prompts are exactly what
they were, so a dish that never enabled predation gets the founding cell and the
variants it always would have.

## reading a predatory dish

- **`predated`** is a new death cause. `biotic status` prints it in the deaths
  dict, the vitals panel adds `· N predated` to the deaths line when there are
  any (and shows nothing when there are none), and `vessel/curve.csv` gains a
  cumulative `predated` column, appended after `mutations_viable`
  (`docs/curve.md`). The death ledger still closes:
  `births − (starved + lysed + senescent + killed + predated) = population −
  INOCULUM`.
- The naturalist counts predation deaths since its last entry alongside the
  others. It observes; it is never told to encourage or discourage it.

## persistence

`dish.features` rides in `dish.json` and in every freezer sample, so a resumed
or thawed dish keeps its rules. A dish frozen before features existed thaws with
every feature off — the flag's absence means off. A flag a newer apparatus wrote
survives the round trip even where this one has no rule for it, so a sample does
not silently lose a feature it does not recognise; the reverse — a dish frozen
now and thawed by an older binary that predates features — drops the flag, since
that binary does not read it. Within one repo checkout that does not arise.

## determinism and safety

The burst roll uses the dish's own seeded RNG, and `me.threat` is a pure
function of dish state, so a predatory dish is as replayable as any other. With
the feature off the lyse branch returns before it touches the RNG, so a
non-predatory dish's stream is byte-for-byte what it always was.

`me.threat` is a read-only list of floats and `("lyse", d)` is an ordinary
parsed action, so predation adds no new escape surface: a lysing genome passes
the same membrane — the static gate and forty smoke rounds — as everything else
(`docs/membrane.md`).
