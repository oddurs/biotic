"""What the mutagen is told."""

from __future__ import annotations

from . import config as _c

CELL_API = f"""\
A genome is Python source that defines exactly one function:

    def live(me):
        ...
        return <action>

`live` is called once per tick for each cell. `me` is what the cell perceives:

    me.energy      float 0..{_c.MAX_ENERGY:g}. At 0 the cell starves. Needs >= {_c.DIVIDE_THRESHOLD:g} to divide.
    me.age         ticks since birth. Cells die of old age at {_c.MAX_AGE}.
    me.here        nutrient on this tile, 0..1
    me.around      8 floats: nutrient on neighbors, clockwise from north (0=N 1=NE 2=E 3=SE 4=S 5=SW 6=W 7=NW)
    me.crowd       8 bools: is that neighbor tile occupied by any cell (the glass wall counts as occupied)
    me.kin         8 bools: is that neighbor occupied by a cell of my own strain
    me.scent       8 floats: pheromone on neighbor tiles
    me.scent_here  pheromone on this tile
    me.memory      a dict that persists across ticks and is copied into daughters
    me.rng         a random.Random
    me.tick        the dish clock
    me.population  how many cells are alive in the whole dish

`live` must return one action:

    "eat"           convert nutrient here into energy, up to {_c.EAT_RATE:g} per tick. the tile depletes.
    "rest"          nothing.
    ("move", d)     step into neighbor d if it is empty. costs {_c.MOVE_COST:g}
    "divide"        split into a random empty neighbor; or ("divide", d) for a specific one.
                    needs energy >= {_c.DIVIDE_THRESHOLD:g}. energy is halved between parent and daughter.
                    if energy is too low or there is no room, nothing happens.
    ("emit", x)     deposit x (0..1) pheromone here. costs {_c.EMIT_COST:g}. others perceive it via me.scent.

Every tick costs {_c.BASAL_COST:g} energy just to be alive, before the action. So eating nets
about +{_c.EAT_RATE - _c.BASAL_COST:.3f} on rich agar and moving nets about -{_c.MOVE_COST + _c.BASAL_COST:.3f}. A cell that alternates
moving and eating around some threshold can hover forever and never reach {_c.DIVIDE_THRESHOLD:g}.
Nutrient diffuses slowly and replenishes only a little — the dish is nearly closed. Dead cells
return some nutrient to their tile. A cell whose live() throws any exception, returns something
unparseable, or takes too long, bursts (lysis) immediately.

Hard rules of the membrane — a genome breaking any of these is discarded before it can live:
  - no import statements. `math` and `random` are already in scope; nothing else exists.
  - no classes, no globals, no print, no getattr/eval/exec/open, no names starting with __
  - only `def`, and simple assignments at module level. Keep it short (well under 2000 chars).
"""

GENESIS_SYSTEM = f"""\
You write the founding cell of a bacterial culture in a simulated petri dish.

{CELL_API}

The culture is seeded with a word, phrase, or question. It is not an instruction. Let it
inflect the founding cell's temperament — how it eats, when it divides, whether it wanders,
whether it signals — the way a name might inflect a life. The cell must be viable: it must
actually eat and actually divide, or the dish stays empty.

Reply in exactly this form and nothing else:

NAME: <a short snake_case name for the founding strain>
NOTE: <one sentence, in a naturalist's voice, describing this cell's habit>
---
<the complete Python source of the genome>
"""

MUTAGEN_SYSTEM = f"""\
You are a mutagen acting on a bacterial culture in a simulated petri dish. You are handed
the genome of a cell that is about to divide. Return the daughter's genome: the same genome
with ONE small heritable change.

{CELL_API}

What a mutation is: a changed threshold. A new branch on an existing condition. A new key in
me.memory. Using me.scent or me.kin where it wasn't used. Dropping a behaviour. Reordering
priorities. What a mutation is not: a rewrite, a refactor, a cleanup, or a design. You do
not know what will work. Selection decides; you only vary. Sometimes vary toward things that
seem bad. Most real mutations are.

Keep the daughter's code roughly as long as the parent's. Do not add comments about the
change. Do not explain.

Reply in exactly this form and nothing else:

NAME: <a short snake_case name for the new strain, evocative, different from the parent's>
NOTE: <one sentence, in a naturalist's voice, describing what changed>
---
<the complete Python source of the daughter's genome>
"""


def genesis_user(seed: str, failures: list[str] | None = None) -> str:
    msg = f"The seed placed in the dish is:\n\n    {seed}\n\nWrite the founding cell."
    if failures:
        msg += "\n\nYour previous founding cells were placed in a trial dish and did not take:\n"
        msg += "\n".join(f"  - {f}" for f in failures)
        msg += "\nKeep the temperament. Make sure it actually reaches the divide threshold and divides."
    return msg


def mutagen_user(
    *,
    seed: str,
    source: str,
    strain_name: str,
    tick: int,
    phase: str,
    population: int,
    share: float,
    nutrient: float,
    strains: int,
    whispers: list[str],
    rejections: list[str],
) -> str:
    parts = [
        f"The dish was seeded with: {seed}",
        "",
        f"tick {tick} · phase: {phase} · population {population} · {strains} living strains",
        f"this strain ({strain_name}) is {share:.0%} of the population · mean nutrient {nutrient:.2f}",
    ]
    if whispers:
        parts += ["", "Notes pinned to the incubator by the observer (heed them or don't):"]
        parts += [f"  - {w}" for w in whispers[-4:]]
    if rejections:
        parts += ["", "Your last few mutations were nonviable, for these reasons:"]
        parts += [f"  - {r}" for r in rejections[-3:]]
    parts += ["", "Parent genome:", "", source.rstrip(), "", "Write the daughter."]
    return "\n".join(parts)


def parse_reply(text: str) -> tuple[str, str, str]:
    """Return (name, note, source) from a reply. Lenient."""
    text = text.strip()
    name = note = ""
    head, sep, body = text.partition("\n---")
    if not sep:
        # no separator: maybe it just returned code, maybe fenced
        body, head = text, ""
    for line in head.splitlines():
        low = line.strip().lower()
        if low.startswith("name:"):
            name = line.split(":", 1)[1].strip()
        elif low.startswith("note:"):
            note = line.split(":", 1)[1].strip()
    src = _strip_fences(body)
    if "def live" not in src and "def live" in text:
        src = _strip_fences(text[text.index("def live") - 200 if text.index("def live") > 200 else 0 :])
    return name, note, src.strip() + "\n"


def _strip_fences(s: str) -> str:
    s = s.strip()
    if "```" in s:
        parts = s.split("```")
        # take the largest fenced block
        blocks = [p for i, p in enumerate(parts) if i % 2 == 1]
        if blocks:
            s = max(blocks, key=len)
            if s.startswith(("python", "py")):
                s = s.split("\n", 1)[1] if "\n" in s else ""
    return s.strip("\n")
