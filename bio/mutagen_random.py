"""The random mutagen: the control arm.

The project's claim is that a *semantic* mutagen — an LLM that understands what a
genome means — escapes the plateau that random bit-flipping reached in Tierra. That
claim is untestable without the thing it is compared to, and the honest risk in
CONCEPT.md is the opposite one: that the LLM prior canalises, so every mutant is a
sensible variation on sensible foraging and the weird things never appear. This is
both the control and the countermeasure — a mutagen that needs no model.

It rewrites the genome at the level of the syntax tree: perturb a numeric constant,
flip a comparison or a boolean operator, swap two subscript indices, drop one branch
of an `if`, duplicate a statement, or swap two return actions. One change per call, at
one randomly chosen eligible site. The result passes the membrane like anything else;
a daughter that does not (a bomb, a genome that throws, one identical to its parent) is
simply refused, and the division is faithful. No mind, no thread, no network — a run on
this arm alone makes zero API calls, and given a seeded RNG it reproduces on any
machine. docs/mutagen.md.

`ast.unparse` reformats and drops comments, so even a one-constant change comes back
reindented: a reader diffing fossils sees the reflow, not the single token. That is
accepted — the membrane admits the genome, and the change is the same one.
"""

from __future__ import annotations

import ast
import copy
import random

from .membrane import admit


class RandomMutagen:
    """An offline, deterministic AST mutagen driven by one shared RNG."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng  # the culture's persisted mutation RNG (Culture.rng_mut)

    def mutate(self, source: str) -> tuple[str, str, str] | None:
        """One AST-level change to `source`. Returns an admitted daughter (name, note, source),
        or None when no transform found an eligible site, the result was identical, or the
        membrane refused it. Never raises: a fault in the apparatus must not lyse the dividing
        cell (parity with Mutagen.mutate_now)."""
        try:
            tree = ast.parse(source)
            transforms = list(_TRANSFORMS)
            self.rng.shuffle(transforms)  # uniform among the transforms that can fire
            fired = None
            for op, fn in transforms:
                note = fn(tree, self.rng)
                if note is not None:
                    fired = (op, note)
                    break
            if fired is None:
                return None
            op, note = fired
            src = ast.unparse(tree) + "\n"
            if src.strip() == source.strip():
                return None  # the change made no difference (a rounded constant, a same-for-same swap)
            if not admit(src):  # in-process: _on_divide is the main thread, after the Budget block closes
                return None
            return self._name(op), note, src
        except Exception:  # noqa: BLE001 — never raise into the dividing cell
            return None

    def _name(self, op: str) -> str:
        """A strain name for a mutation of kind `op`: the operator plus four hex of entropy, e.g.
        `perturb_3f1a`. Passes strains._NAME; the registry dedupes ids, so the suffix is only to
        tell one `perturb` from the next in the census."""
        return f"{op}_{format(self.rng.randrange(1 << 16), '04x')}"


# --- the transforms -----------------------------------------------------------
# Each fn(tree, rng) -> str | None mutates one randomly chosen eligible site in place and
# returns a plain, factual note describing the change, or None when it found no site. `mutate`
# shuffles the list and takes the first that fires.


def _numeric_constants(tree: ast.AST) -> list[ast.Constant]:
    """Every numeric (int or float, not bool) Constant that is safe to perturb: not the exponent
    of a `**`, not an index into a subscript, not an argument of `range()`, and not a factor
    multiplying a sequence literal. Perturbing any of those would tend to make a genome the
    membrane rejects (a resource bomb, or a shifted index) rather than a living variant."""
    excluded: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            excluded.update(id(c) for c in ast.walk(node.right) if isinstance(c, ast.Constant))
        elif isinstance(node, ast.Subscript):
            excluded.update(id(c) for c in ast.walk(node.slice) if isinstance(c, ast.Constant))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
            for arg in node.args:
                excluded.update(id(c) for c in ast.walk(arg) if isinstance(c, ast.Constant))
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            if _is_seq_literal(node.left) or _is_seq_literal(node.right):
                for side in (node.left, node.right):
                    excluded.update(id(c) for c in ast.walk(side) if isinstance(c, ast.Constant))
    return [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant)
        and isinstance(n.value, (int, float))
        and not isinstance(n.value, bool)
        and id(n) not in excluded
    ]


def _is_seq_literal(node: ast.expr) -> bool:
    return isinstance(node, (ast.List, ast.Tuple)) or (
        isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes))
    )


def _perturb_constant(tree: ast.AST, rng: random.Random) -> str | None:
    consts = _numeric_constants(tree)
    if not consts:
        return None
    node = rng.choice(consts)
    factor = rng.choice([-1, 1]) * rng.uniform(0.10, 0.50)
    value = node.value
    if isinstance(value, int):
        new = int(value * (1.0 + factor))
        if new == value:  # a small int the factor rounded away: nudge it so the change is real
            new = value + (1 if factor > 0 else -1)
        if new == 0:  # keep a magnitude of at least 1
            new = 1 if factor > 0 else -1
    else:
        new = value * (1.0 + factor)
    node.value = new
    return f"a constant shifted by {round(factor * 100):+d}%"


_COMPARE_FLIP = {
    ast.Lt: (ast.Gt, "<", ">"),
    ast.Gt: (ast.Lt, ">", "<"),
    ast.LtE: (ast.GtE, "<=", ">="),
    ast.GtE: (ast.LtE, ">=", "<="),
}


def _swap_compare(tree: ast.AST, rng: random.Random) -> str | None:
    sites = [
        (node, i)
        for node in ast.walk(tree)
        if isinstance(node, ast.Compare)
        for i, op in enumerate(node.ops)
        if type(op) in _COMPARE_FLIP
    ]
    if not sites:
        return None
    node, i = rng.choice(sites)
    new_op, was, now = _COMPARE_FLIP[type(node.ops[i])]
    node.ops[i] = new_op()
    return f"a comparison flipped from {was} to {now}"


def _flip_boolop(tree: ast.AST, rng: random.Random) -> str | None:
    sites = [node for node in ast.walk(tree) if isinstance(node, ast.BoolOp)]
    if not sites:
        return None
    node = rng.choice(sites)
    if isinstance(node.op, ast.And):
        node.op = ast.Or()
        return "an and became or"
    node.op = ast.And()
    return "an or became and"


def _swap_subscript_index(tree: ast.AST, rng: random.Random) -> str | None:
    sites = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Subscript)
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, int)
        and not isinstance(node.slice.value, bool)
        and 0 <= node.slice.value <= 7
    ]
    if not sites:
        return None
    if len(sites) >= 2 and rng.random() < 0.5:
        a, b = rng.sample(sites, 2)
        a.slice.value, b.slice.value = b.slice.value, a.slice.value
        return "two subscript indices were swapped"
    node = rng.choice(sites)
    current = node.slice.value
    node.slice.value = rng.choice([v for v in range(8) if v != current])
    return f"a subscript index changed from {current} to {node.slice.value}"


def _stmt_lists(tree: ast.AST) -> list[list[ast.stmt]]:
    """Every statement body in the tree — the `.body`, `.orelse` and `.finalbody` of modules,
    functions, ifs, loops and try blocks. Statement-list transforms edit these lists directly;
    `ast` cannot splice a node into its parent on its own."""
    out: list[list[ast.stmt]] = []
    for node in ast.walk(tree):
        for attr in ("body", "orelse", "finalbody"):
            seq = getattr(node, attr, None)
            if isinstance(seq, list) and seq and all(isinstance(s, ast.stmt) for s in seq):
                out.append(seq)
    return out


def _delete_if_branch(tree: ast.AST, rng: random.Random) -> str | None:
    sites = [(seq, i) for seq in _stmt_lists(tree) for i, s in enumerate(seq) if isinstance(s, ast.If)]
    if not sites:
        return None
    seq, i = rng.choice(sites)
    node = seq[i]
    if node.orelse and rng.random() < 0.5:
        node.orelse = []  # drop the else; the if itself stays
        return "an else branch was dropped"
    seq[i : i + 1] = node.body  # splice the if's body up in its place; the body is never empty
    return "an if condition was removed"


def _duplicate_statement(tree: ast.AST, rng: random.Random) -> str | None:
    lists = _stmt_lists(tree)
    if not lists:
        return None
    seq = rng.choice(lists)
    i = rng.randrange(len(seq))
    seq.insert(i + 1, copy.deepcopy(seq[i]))
    return "a statement was duplicated"


def _swap_returns(tree: ast.AST, rng: random.Random) -> str | None:
    returns = [node for node in ast.walk(tree) if isinstance(node, ast.Return) and node.value is not None]
    if len(returns) < 2:
        return None
    a, b = rng.sample(returns, 2)
    a.value, b.value = b.value, a.value
    return "two return actions were swapped"


_TRANSFORMS: tuple[tuple[str, object], ...] = (
    ("perturb", _perturb_constant),
    ("swapcmp", _swap_compare),
    ("flipbool", _flip_boolop),
    ("swapidx", _swap_subscript_index),
    ("dropif", _delete_if_branch),
    ("dup", _duplicate_statement),
    ("swapret", _swap_returns),
)
