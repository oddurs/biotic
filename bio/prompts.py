"""What the mutagen and the naturalist are told."""

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
    me.memory      a dict that persists across ticks and is copied into daughters; the rules below say what it may hold
    me.rng         a random.Random — the dish's own seeded generator. `random` in scope is the same object.
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
  - no classes, no globals, no print, no getattr/eval/exec/open, no names starting with __,
    no attributes starting with _ (nothing like x._private), no .format, no .mro.
  - attributes are read-only: nothing like math.pi = 0 or me.energy = 2. State goes in me.memory.
  - `except` must name one of Exception, ValueError, KeyError, IndexError, ZeroDivisionError,
    TypeError; no bare `except:`, no `finally`, no `with`. Those six names cannot be reused for
    anything else: no `KeyError = ...`, no parameter, loop variable or `as` name called ValueError.
  - no sets: no set(), no {{a, b}}, no set comprehension, no frozenset. Their order depends on the
    interpreter, not the seed. A tuple, a list or a dict does the same job.
  - only `def` and constant assignments at module level: numbers, strings, tuples and arithmetic
    on them. No calls there (no random.random() at module level), no lists, dicts or lambdas, no
    decorators, no mutable or computed default arguments. Module level runs again whenever the
    culture is reloaded, so anything that must persist goes in me.memory. Keep it short (well
    under 2000 chars).
  - me.memory holds only None, True/False, ints, floats, strings, and lists, tuples and dicts of
    those (keys: strings, numbers, bools or None), nested at most {_c.MEMORY_MAX_DEPTH} deep, at most
    {_c.MEMORY_MAX_CHARS} characters as plain JSON (a tuple counts as its list, a numeric key as its
    string; the file's own type tags are not counted), and never the same list or dict in two
    places (copy it: list(x)). That is exactly what a save carries, so a cell resumes as it left
    off. A cell whose memory breaks
    this at the end of a tick (a function, `me`, a range, a trail that is never trimmed, one row
    list repeated eight times) bursts.
  - no resource bombs: no `**` with a huge or computed exponent (2 ** 1000000, 2 ** n),
    no repeating a list or string by a huge constant ([0] * 10**10), and no range() over
    a huge constant (sum(range(10**12))). The time budget cannot interrupt a single
    C-level operation, so these are refused before the cell can live.
  - live() must return within a few milliseconds every tick. A loop that does not end bursts
    the cell, and nothing in the genome can catch that.
"""


# The cell API a genome is written against, plus a clause for every dish rule (feature) that is
# switched on. With no feature on, cell_api() is CELL_API byte-for-byte, so the GENESIS_SYSTEM and
# MUTAGEN_SYSTEM constants below — the ones the leak tests pin — read exactly as they always have.
# A feature's clause appears only when its dish has it on, and only in the mutagen/genesis prompts,
# never in the naturalist's. docs/predation.md.
def _feature_clauses(features: dict[str, bool] | None) -> str:
    out = ""
    if features and features.get("lyse"):
        out += f"""
This dish has predation switched on. One more perception and one more action are available:

    me.threat      8 floats: the energy of each neighbor that is a cell of ANOTHER strain,
                   clockwise from north; 0.0 where the tile is empty, the glass wall, or my own kin.

    ("lyse", d)    attack the neighbor in direction d. Costs {_c.LYSE_COST:g} whatever happens.
                   Only a cell of another strain can be lysed; against an empty tile, the glass wall,
                   or your own kin it does nothing and costs nothing (me.kin marks the kin). The
                   attack bursts the target with probability p = 1 / (1 + exp(-{_c.LYSE_K:g} · (my
                   energy − its energy))): the more energy you hold over it, the likelier the burst.
                   On success the target dies (cause "predated") and you gain {_c.LYSE_YIELD:g} × its
                   energy; on failure you lose a further {_c.LYSE_RECOIL:g}.
"""
    if features and features.get("give"):
        out += f"""
This dish has sharing switched on. One more perception and one more action are available:

    me.neighbor_energy   8 floats: the energy of each neighbouring cell, clockwise from north,
                   KIN INCLUDED; 0.0 where the tile is empty or the glass wall. me.kin marks which
                   of these are your own strain, so you can tell a hungry sister from a stranger.

    ("give", d, x) give energy to the neighbour in direction d. You lose min(x, my energy −
                   {_c.GIVE_RESERVE:g}) and never drop below {_c.GIVE_RESERVE:g}; the neighbour gains
                   {_c.GIVE_EFFICIENCY:g} × what you lose, and the rest is lost as heat. Against an empty tile
                   or the glass wall it does nothing and costs nothing. Any strain can receive —
                   giving to non-kin is possible, and cheaper for the taker than earning it.
"""
    return out


def cell_api(features: dict[str, bool] | None = None) -> str:
    """The cell API with a clause appended for every feature the dish has on. cell_api() == CELL_API."""
    return CELL_API + _feature_clauses(features)


_GENESIS_TEMPLATE = """\
You write the founding cell of a bacterial culture in a simulated petri dish.

{api}

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

_MUTAGEN_TEMPLATE = """\
You are a mutagen acting on a bacterial culture in a simulated petri dish. You are handed
the genome of a cell that is about to divide. Return the daughter's genome: the same genome
with ONE small heritable change.

{api}

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


_HGT_TEMPLATE = """\
You are a mutagen acting on a bacterial culture in a simulated petri dish, but this is not an
ordinary mutation. Two cells of different strains are touching, and a gene is crossing between
them — horizontal gene transfer. You are handed the RECIPIENT's genome and a DONOR's genome
from an unrelated neighbour. Return the recipient's daughter: the recipient with exactly ONE
behaviour borrowed from the donor.

{api}

What a splice is: take one coherent behaviour the donor has and the recipient does not — a way
of foraging, a use of me.scent or me.kin, a division rule, a threshold, a response to crowding —
and graft it into the recipient. Keep the recipient's temperament: it stays the recipient with
a new trick, not the donor with a coat of paint, and not a blend of the two. Borrow one thing,
not several. What a splice is not: a rewrite of the recipient in the donor's image, a merge of
both genomes line by line, a cleanup, or a design. You do not know what will work; selection
decides, you only recombine.

Keep the daughter's code roughly as long as the recipient's. Do not add comments about the
change. Do not explain.

Reply in exactly this form and nothing else:

NAME: <a short snake_case name for the new strain, evocative of both parents, different from either>
NOTE: <one sentence, in a naturalist's voice, naming the behaviour borrowed from the donor>
---
<the complete Python source of the daughter's genome>
"""


def genesis_system(features: dict[str, bool] | None = None) -> str:
    return _GENESIS_TEMPLATE.format(api=cell_api(features))


def mutagen_system(features: dict[str, bool] | None = None) -> str:
    return _MUTAGEN_TEMPLATE.format(api=cell_api(features))


def hgt_system(features: dict[str, bool] | None = None) -> str:
    """The splicing prompt (docs/hgt.md). Used instead of the mutation prompt when a division that
    rolled a mutation also rolled a splice and found a donor. Same feature clauses as the mutagen's."""
    return _HGT_TEMPLATE.format(api=cell_api(features))


GENESIS_SYSTEM = genesis_system()  # the no-feature text; unchanged from before features existed
MUTAGEN_SYSTEM = mutagen_system()  # likewise
HGT_SYSTEM = hgt_system()  # the splicing prompt with no feature clauses


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


def hgt_user(
    *,
    seed: str,
    recipient_source: str,
    recipient_name: str,
    donor_source: str,
    donor_name: str,
    tick: int,
    phase: str,
    population: int,
    share: float,
    nutrient: float,
    strains: int,
    whispers: list[str],
    rejections: list[str],
) -> str:
    """The user turn for a splice: the same header, whispers and rejections as a mutation, then
    the recipient's genome and the donor's, labelled, and a closing instruction. docs/hgt.md."""
    parts = [
        f"The dish was seeded with: {seed}",
        "",
        f"tick {tick} · phase: {phase} · population {population} · {strains} living strains",
        f"the recipient ({recipient_name}) is {share:.0%} of the population · mean nutrient {nutrient:.2f}",
    ]
    if whispers:
        parts += ["", "Notes pinned to the incubator by the observer (heed them or don't):"]
        parts += [f"  - {w}" for w in whispers[-4:]]
    if rejections:
        parts += ["", "Your last few mutations were nonviable, for these reasons:"]
        parts += [f"  - {r}" for r in rejections[-3:]]
    parts += ["", f"Recipient genome ({recipient_name}):", "", recipient_source.rstrip()]
    parts += ["", f"Donor genome ({donor_name}), an unrelated neighbour:", "", donor_source.rstrip()]
    parts += ["", "Write the daughter: the recipient with one behaviour borrowed from the donor."]
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


# --- the naturalist ----------------------------------------------------------
# An observer, not a mutagen: it is shown readings, never a genome, and nothing it writes reaches
# the culture. The cell API and the mutagen's rules are deliberately absent from this prompt.

NATURALIST_SYSTEM = """\
You keep the lab notebook for a bacterial culture growing in a simulated petri dish. At
intervals you are shown what the instruments record: the dish clock, the growth phase, the
population and diversity now and at your last entry, the census of living strains with the
one-line note the mutagen wrote when each arose, births and deaths by cause, the incubator
log since your last entry, a coarse sketch of the dish, and your previous entry.

Write the next entry: three to eight sentences in the plain voice of a field notebook.
Report what is observable and what changed since the last entry, with the numbers that
matter. Where you interpret, mark it as interpretation ("this resembles", "one reading is")
and offer no more than one. Do not invent mechanisms the record does not show: what a strain
does is what its note says and what the counts do, nothing more. Do not rank strains as
better or worse, and do not advise anyone to do anything; you observe, you do not run the
experiment. Continue the record: when the previous entry raised something, say what became
of it. The incubator runs at a fixed pace while it is on; wall-clock time well beyond what
the ticks account for is time it was off, and the dish does not run while it is off. If
nothing changed, say so in two sentences.

Reply with the entry only: no heading, no preamble, no list, no code.
"""


def naturalist_user(p: dict) -> str:
    """Render a composed observation packet (bio.naturalist.compose) as the naturalist's prompt."""
    m = p["metrics"]
    tiles = max(1, int(p.get("tiles") or 1))
    since = p.get("since")
    lines = [
        f"The dish was seeded with: {p['seed']}",
        "",
        f"tick {p['tick']} · phase {p['phase']} · {m['population']} cells ({m['population'] / tiles:.0%} of the agar)"
        f" · {_n(m['strains'], 'living strain')}",
    ]
    vitals = (
        f"diversity H {m['shannon']:.2f} · dominance {m['dominance']:.0%} · mean generation {m['mean_gen']:.1f}"
        f" · agar {m['nutrient']:.2f}"
    )
    if m.get("pheromone", 0.0) >= 0.0005:
        vitals += f" · pheromone {m['pheromone']:.3f}"
    lines += [vitals, ""]
    if since is None:
        lines.append("This is the first entry; there is nothing earlier to compare with.")
    elif since.get("seam"):
        lines.append(
            f"Since the last entry (tick {since['prev_tick']}) the dish was replaced with a frozen sample; "
            "the counts above are not comparable with that entry's."
        )
    else:
        pace = f", about {since['pace']} at the incubator's pace" if since.get("pace") else ""
        lines.append(
            f"Since the last entry (tick {since['prev_tick']}, {since['ticks']} ticks{pace}; "
            f"{since['wall']} of wall-clock time):"
        )
        if since.get("gap"):
            lines.append(f"  the incubator was off for {since['gap']['wall']} of that; the dish did not run then.")
        (pa, pb), (sa, sb) = since["population"], since["strains"]
        (ha, hb), (da, db) = since["shannon"], since["dominance"]
        lines.append(
            f"  population {pa} → {pb} · strains {sa} → {sb} · H {ha:.2f} → {hb:.2f} · dominance {da:.0%} → {db:.0%}"
        )
        deaths = f"{since['starved']} starved, {since['lysed']} lysed, {since['senescent']} of age"
        if since["killed"]:
            deaths += f", {since['killed']} killed"
        if since.get("predated"):
            deaths += f", {since['predated']} predated"
        lines.append(f"  births {since['births']} · deaths {deaths}")
        lines.append(f"  strains arisen {since['arisen']} · gone extinct {since['extinct']}")
        if since.get("given"):  # only when energy was shared; a non-sharing dish shows no line
            lines.append(f"  shared {since['given']:.2f} given · {since['received']:.2f} received")
    if p.get("remarks"):
        lines += ["", "Changes worth noting:"] + [f"  - {r}" for r in p["remarks"]]
    compare = since is not None and not since.get("seam")
    lines += [
        "",
        "Census (share now → share at the last entry; the note is the mutagen's, from when the strain arose):",
    ]
    if not p["census"]:
        lines.append("  (no living cells)")
    for r in p["census"]:
        was = ""
        if compare:
            was = " (new since the last entry)" if r.get("was") is None else f" (was {r['was']:.0%})"
        note = f" — “{r['note']}”" if r.get("note") else ""
        lines.append(
            f"  {r['name']} ({r['id']}) gen {r['generation']} · {_n(r['cells'], 'cell')} · {r['share']:.0%}{was}{note}"
        )
    if p.get("more"):
        k, cells = p["more"]
        lines.append(f"  … {k} more strain{'s' if k != 1 else ''}, {_n(cells, 'cell')} between them")
    lines += ["", "Incubator log since the last entry (oldest first):"]
    if p.get("events"):
        lines += [f"  tick {e['tick']} {e['kind']}: {e['msg']}" for e in p["events"]]
    else:
        lines.append("  (nothing was logged)")
    sk = p["sketch"]
    k = sk["scale"]
    block = "one glyph per tile" if k == 1 else f"each glyph a {k}×{k} block of tiles"
    lines += [
        "",
        f"The dish, {block}; letters are strains by census rank, '.' ':' '#' agar by richness, "
        "blank is bare agar or glass:",
    ]
    if sk["legend"]:
        lines.append("  " + ", ".join(f"{letter} {name}" for letter, name in sk["legend"]))
    lines += ["  " + row for row in sk["rows"]]
    prev = p.get("previous")
    if prev:
        lines += ["", f"Your previous entry (tick {prev['tick']}):"]
        lines += ["  " + ln for ln in prev["text"].splitlines()]
    lines += ["", "Write the next entry."]
    return "\n".join(lines)


def _n(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"
