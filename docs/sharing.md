# sharing

Predation made one cell's code matter to another's by taking. Sharing is the
other half: `("give", d, x)` hands energy to a neighbour. With `me.kin` this is
the seed of cooperation — feed your sisters and the colony outlasts a dish that
each cell hoards — and because a stranger can receive as easily as a sister, it
is also the seed of cheating: a strain that takes gifts and gives none pays
nothing for the help. It is the second of the biotic rules in `CONCEPT.md` §1,
after predation (`docs/predation.md`); horizontal gene transfer (`hgt`) comes
next.

Sharing is a **feature**: an opt-in rule a dish keeps off unless you turn it on.
A dish that predates this change is untouched, and behaves exactly as it did.
You switch it on at seeding or mid-run (below).

## the action

    ("give", d, x)   give up to x energy to the neighbour in direction d
                     (0=N 1=NE … 7=NW)

The amount `x` is required — a bare `("give", d)` names no quantity and is
discarded like any unparseable action. It is clamped to `0..MAX_ENERGY` (2.0)
when parsed; the dish then decides how much of it a cell can actually spare.

A giver never gives itself below `GIVE_RESERVE` (0.05): the energy that moves is

    amount = min(x, my energy − GIVE_RESERVE)

If that is zero or less — the cell is already at or below the reserve, or asked
for nothing — the action does nothing and costs nothing, a silent no-op. Against
an empty tile or the glass wall it is likewise free: there is no one to give to.
There is **no kin check**. Kin and non-kin both receive, which is the whole
point: giving to a stranger has to be possible, or there is nothing for a cheat
to exploit.

The transfer loses energy to heat, at efficiency `GIVE_EFFICIENCY` (0.9):

- The giver loses `amount`.
- The neighbour gains `GIVE_EFFICIENCY × amount`.
- The difference, `(1 − GIVE_EFFICIENCY) × amount`, is lost — as in a real
  metabolic hand-off, moving energy is never free.

The recipient is **not** capped at the moment it receives; like a predator's
kill yield, any excess over `MAX_ENERGY` is trimmed on the recipient's own tick,
when the usual clamps run. A gift makes no random roll, so it consumes none of
the dish's RNG.

The two constants live in `bio/config.py`. Unlike `LYSE_K`, neither is a
sigmoid steepness or a probability; they are a reserve floor and a transfer
efficiency, and changing them changes every dish that runs afterwards.

## what a cell perceives

Sharing adds one perception, present on every cell whether or not the feature is
on (it costs one list append in the neighbour scan) but only documented to the
mutagen when it is:

    me.neighbor_energy   8 floats: the energy of each neighbouring cell,
                         clockwise from north, KIN INCLUDED; 0.0 where the tile
                         is empty or the glass wall.

This is a **new** perception, not a rename of `me.threat`. `me.threat` (from
predation) is deliberately blind to kin — it reports a non-kin neighbour's
energy and zero for a sister — because its job is to mark prey and danger. A
giver needs the opposite: it has to see how hungry its own kin are. So
`me.neighbor_energy` reports every occupied neighbour's energy, and `me.kin`
tells the cell which of those are its own strain. A genome that wants to feed
the hungriest sister reads the minimum of `me.neighbor_energy[d]` over the `d`
where `me.kin[d]` is true. Nothing else about a neighbour is exposed.

## turning it on

Off by default. Two ways to switch it on:

    biotic seed "a commons" --with give        # on from the founding cell
    biotic seed "wolves and sheep" --with lyse,give   # both, comma-separated
    biotic drop feature give                    # on mid-run, like any drop

`--with` takes a comma-separated list; a name the dish does not know is refused
before anything is poured, so a typo never autoclaves a dish.

`drop feature give` is an intervention like `drop nutrient`: it goes through the
inbox, so it takes effect when a running incubator next drains it. On an idle
dish it is queued, not applied. Enabling a feature already on is a no-op that
says so.

Either way it is logged as a `drop` event, so it is marked on the growth curve
(`⚗` at that tick, labelled `feature give`; `docs/curve.md`), shows in the
eyepiece's incubator log, and is one of the changes the naturalist is shown.
Seeding with `--with give` writes that mark at tick 0.

When the feature is on, the mutagen's and the genesis prompts gain a clause
documenting `me.neighbor_energy`, `("give", d, x)`, the reserve and the
efficiency, so a strain can evolve to use it. With the feature off the prompts
are exactly what they were.

## reading a sharing dish

- **`given`** and **`received`** are two new cumulative columns in
  `vessel/curve.csv`, appended after `predated` (`docs/curve.md`). They are
  dish-wide floats, to four decimals: `given` is the gross energy that has left
  givers, `received` the smaller amount that has reached recipients. Their gap,
  `given − received`, is the heat sharing has cost the dish. Both are 0.0 unless
  the `give` feature is on.
- The eyepiece adds a `sharing` row to the vitals — `1.25 given · 1.12
  received` — but only once the first gift has been made. Until then the row is
  hidden, the same omit-when-none rule the deaths line follows for `predated`,
  so a dish that never shares shows no empty sharing line. This is by design, not
  a missing reading.

Energy is conserved to the documented loss. In a closed dish (`REPLENISH=0`,
nothing eaten) the total energy after any run equals the starting total minus
basal costs minus `given − received`; there is no other sink.

## persistence

`given` and `received` ride in `dish.json` and in every freezer sample, so a
resumed or thawed dish keeps its running totals. A dish frozen before sharing
existed thaws with both at 0.0 — the keys' absence means zero — and
`dish.features` carries the `give` flag the same way `lyse` rides (a flag a
newer apparatus wrote survives the round trip even where this build has no rule
for it; `docs/predation.md`).

## determinism and safety

A gift is a pure function of dish state and touches no RNG, so a sharing dish is
as replayable as any other, and with the feature off the give branch returns
before it moves an electron — a non-sharing dish's stream is byte-for-byte what
it always was. `me.neighbor_energy` is a read-only list of floats and `("give",
d, x)` is an ordinary parsed action, so sharing adds no new escape surface: a
giving genome passes the same membrane — the static gate and forty smoke rounds
— as everything else (`docs/membrane.md`). The membrane's stand-in cell exposes
`me.neighbor_energy` on the same 0..`MAX_ENERGY` scale a live neighbour would, so
a genome whose giving branch is gated on an energy-scale threshold is actually
exercised before it is admitted.
