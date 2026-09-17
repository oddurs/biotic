"""The membrane: decides what code is allowed to become a cell.

A genome is Python source defining `live(me)`. Before it can run inside the
dish it has to pass through here: no imports, no dunders, no escape hatches,
and it must survive a few dozen simulated ticks without throwing. No attribute
beginning with `_`, no `.format`, no `finally`, no `with`, no `except*`, and
`except` may name only the built-in exceptions a genome can see, none of which
a genome may rebind, so nothing in a genome runs on after its time budget
bursts it. Module level holds only `def` and constants, and attributes are
read-only, so everything a genome can change lives in `me.memory` or the dish's
generator, both of which the freezer saves. No sets: a set of strings iterates
in an order the interpreter's hash seed picks, and the dish's seed does not fix
that. What `me.memory` may hold is bounded here too (`memory_fault`), and the
dish applies that rule after every tick, so a save carries memory exactly.
"""

from __future__ import annotations

import ast
import json
import math
import random
import signal
from dataclasses import dataclass, field

from . import config

BANNED_NAMES = {
    "eval",
    "exec",
    "compile",
    "open",
    "input",
    "__import__",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
    "breakpoint",
    "memoryview",
    "type",
    "super",
    "object",
    "classmethod",
    "staticmethod",
    "property",
    "exit",
    "quit",
    "help",
    "dir",
    "id",
    "hash",
    "iter",
    "next",
    "print",
}

# Attributes with no leading underscore that still reach outside the genome.
# .format and .format_map walk attributes through their replacement fields;
# .mro() is the one non-dunder route from an exception class to BaseException and
# object; BaseException is what Lysis derives from, and what a genome must never raise.
BANNED_ATTRS = {"format", "format_map", "mro"}

SAFE_BUILTINS = {
    n: __builtins__[n] if isinstance(__builtins__, dict) else getattr(__builtins__, n)
    for n in (
        "abs",
        "all",
        "any",
        "bool",
        "dict",
        "divmod",
        "enumerate",
        "filter",
        "float",
        "int",
        "isinstance",
        "len",
        "list",
        "map",
        "max",
        "min",
        "pow",
        "range",
        "reversed",
        "round",
        "sorted",
        "str",
        "sum",
        "tuple",
        "zip",
        "True",
        "False",
        "None",
        "Exception",
        "ValueError",
        "KeyError",
        "IndexError",
        "ZeroDivisionError",
        "TypeError",
    )
}

# What an `except` clause may name: the exception classes in SAFE_BUILTINS and nothing
# else, derived from the namespace so the two cannot drift apart. Every one of them is a
# subclass of Exception, so none of them sees a Lysis.
ALLOWED_EXCEPTIONS = frozenset(
    n for n, v in SAFE_BUILTINS.items() if isinstance(v, type) and issubclass(v, BaseException)
)
_EXCEPT_RULE = "except may only name " + ", ".join(sorted(ALLOWED_EXCEPTIONS))

# What a module-level value may be made of. Module-level code runs when a genome is compiled,
# and a dish compiles its genomes again when it is loaded from the freezer, so nothing there
# may draw from the generator or leave behind a container a cell could change between ticks:
# no calls, no lists, dicts, sets or lambdas. Numbers, strings, tuples of them, names and
# arithmetic are enough. The same holds for a `def`'s defaults and annotations, which are
# evaluated when the `def` runs, and for decorators, which are calls.
_CONSTANT_NODES = (
    ast.Constant,
    ast.Tuple,
    ast.Name,
    ast.Attribute,
    ast.Subscript,
    ast.Slice,
    ast.Starred,
    ast.UnaryOp,
    ast.BinOp,
    ast.BoolOp,
    ast.Compare,
    ast.IfExp,
    ast.JoinedStr,
    ast.FormattedValue,
    ast.expr_context,
    ast.operator,
    ast.unaryop,
    ast.boolop,
    ast.cmpop,
)
_SIGNATURE_NODES = _CONSTANT_NODES + (ast.arguments, ast.arg)
_CONSTANT_RULE = "module-level values must be constants (numbers, strings, tuples; no calls, lists or dicts)"

# A set of strings (or of tuples holding one) iterates in an order that depends on the
# interpreter's hash seed, which differs from process to process, so a genome that walks one
# is not reproducible across a resume. Dicts keep insertion order and are unaffected.
_SET_NAMES = ("set", "frozenset")
_SET_RULE = "sets not allowed (their order depends on the interpreter, not the seed; use a tuple, list or dict)"

# Python 3.12 type parameters (`def f[T](): ...`) bind a name too; absent on 3.11.
_TYPE_PARAMS = tuple(getattr(ast, n) for n in ("TypeVar", "ParamSpec", "TypeVarTuple") if hasattr(ast, n))

# --- resource bombs the time budget cannot interrupt ----------------------------
# The budget (Budget, below) is a SIGALRM delivered between bytecodes, so a single C-level
# operation holds the interpreter until it finishes and no alarm, thread or exception can
# pre-empt it: `2 ** 10**9`, `[0] * 10**10`, `sum(range(10**12))`. The static gate refuses their
# literal and constant forms here, regardless of the tick that would run them, so a bomb hidden
# behind `if me.tick > 40:` is refused at admission rather than stalling the dish; the isolated
# child (admit_isolated) caps its own memory and CPU for the forms whose size is only known at
# runtime. These are membrane rules, not dish physics, so they live here and not in config.py.
POW_MAX_EXP = 1024  # largest constant integer exponent a genome may write (2 ** 1024 is ~300 digits)
MAX_LITERAL_COUNT = 1_000_000  # largest constant range() or repeat count a genome may write
_FOLD_CAP = 10**18  # the constant folder collapses to None past this, so folding stays cheap
CHILD_AS_LIMIT = 2 * 1024**3  # bytes; address space the isolated child may map (best-effort)
CHILD_CPU_LIMIT = 15  # seconds of CPU the isolated child may burn, under its 20 s wall timeout
_POW_RULE = "** with a non-constant or oversized exponent (a resource bomb the budget cannot interrupt)"
_REPEAT_RULE = "sequence repeated by a large constant (a resource bomb the budget cannot interrupt)"
_RANGE_RULE = "range() over a huge constant (a resource bomb the budget cannot interrupt)"
# What a constant arithmetic expression is made of: literals and `+ - * **` on them, nothing
# a name, attribute, call or subscript could make depend on the running dish.
_CONST_EXPR_NODES = (ast.Constant, ast.UnaryOp, ast.BinOp, ast.operator, ast.unaryop)


@dataclass
class Verdict:
    ok: bool
    reasons: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.ok


def _names_only(t: ast.expr) -> bool:
    """True if an except clause names only whitelisted exceptions, alone or as a tuple."""
    names = t.elts if isinstance(t, ast.Tuple) else [t]
    return bool(names) and all(isinstance(n, ast.Name) and n.id in ALLOWED_EXCEPTIONS for n in names)


def _binds(node: ast.AST) -> str | None:
    """The name a node binds, if it binds one.

    An assignment, loop, comprehension or walrus target, a `del`, a parameter, a `def`,
    an `except ... as`, a match capture, a type parameter. What `except` may name is
    checked by identifier, so the identifier has to keep meaning the builtin: a rebound
    `KeyError` is a TypeError raised while a Lysis is being matched, and that one an outer
    `except Exception:` would catch.
    """
    if isinstance(node, ast.Name):
        return None if isinstance(node.ctx, ast.Load) else node.id
    if isinstance(node, ast.arg):
        return node.arg
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.ExceptHandler)):
        return node.name
    if isinstance(node, (ast.MatchAs, ast.MatchStar)):
        return node.name
    if isinstance(node, ast.MatchMapping):
        return node.rest
    if isinstance(node, ast.alias):
        return node.asname or node.name
    if _TYPE_PARAMS and isinstance(node, _TYPE_PARAMS):
        return node.name
    return None


def _constant(roots, allowed: tuple[type, ...]) -> bool:
    """True if every node under `roots` is one the module level may evaluate."""
    return all(isinstance(n, allowed) for root in roots for n in ast.walk(root))


def _is_const_expr(node: ast.expr) -> bool:
    """True if `node` is built only from number and string literals and arithmetic on them, with
    no name, attribute, call or subscript. This is what tells a value that is constant but may be
    huge (`10**12`) apart from one only the running dish knows (`me.age`, `len(me.around)`)."""
    return all(isinstance(n, _CONST_EXPR_NODES) for n in ast.walk(node))


def _fold_number(node: ast.expr) -> int | float | None:
    """Evaluate a constant arithmetic tree to a number, or None if it is not one, uses an operator
    this folder does not carry, or is too large to hold. A manual recursive descent over
    `+ - * / // % **` on int and float literals: it never uses eval, compile or ast.literal_eval,
    so the checker runs no genome-derived code and cannot itself detonate. Integer `**` is computed
    only for a small exponent (0..64) over a bounded base, and every intermediate past `_FOLD_CAP`
    collapses to None, so folding is always cheap and never a bomb of its own; a `**` with a float
    operand is an ordinary O(1) float power. Because the folder carries all the everyday numeric
    operators, a None result reliably means "oversized or unrepresentable" and not merely "not a
    plain literal" — which is what lets the Pow, repeat and range rules treat None as a bomb rather
    than wave it through. `bool` is not a number here (a genome that writes `[0] * True` meant the
    int)."""
    if isinstance(node, ast.Constant):
        v = node.value
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
        return v
    if isinstance(node, ast.UnaryOp):
        v = _fold_number(node.operand)
        if v is None:
            return None
        if isinstance(node.op, ast.USub):
            v = -v
        elif not isinstance(node.op, ast.UAdd):
            return None
        return None if abs(v) > _FOLD_CAP else v
    if isinstance(node, ast.BinOp):
        left = _fold_number(node.left)
        right = _fold_number(node.right)
        if left is None or right is None:
            return None
        op = node.op
        try:
            if isinstance(op, ast.Add):
                v = left + right
            elif isinstance(op, ast.Sub):
                v = left - right
            elif isinstance(op, ast.Mult):
                v = left * right
            elif isinstance(op, ast.Div):
                v = left / right  # always a float; a zero divisor is caught below
            elif isinstance(op, ast.FloorDiv):
                v = left // right
            elif isinstance(op, ast.Mod):
                v = left % right
            elif isinstance(op, ast.Pow):
                if isinstance(left, int) and isinstance(right, int):
                    if not (0 <= right <= 64 and abs(left) <= MAX_LITERAL_COUNT):
                        return None  # a large integer power: oversized, and never computed here
                    v = left**right
                else:
                    v = float(left) ** float(right)  # a float power is O(1) and never a bomb
            else:
                return None
        except (ZeroDivisionError, OverflowError, ValueError):
            return None
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            return None  # a complex, say, from a negative float raised to a fractional power
        if isinstance(v, float) and not math.isfinite(v):
            return None
        return None if abs(v) > _FOLD_CAP else v
    return None


def _mult_factors(node: ast.expr) -> list[ast.expr]:
    """Flatten a tree of `*` into its operands, descending only through `Mult` BinOps, so a
    left-associative chain like `[0] * 1000 * 1000` yields `[[0], 1000, 1000]`. An operand that is
    not itself a `*` (a literal, a name, a `+` expression) is returned whole. This is what lets the
    repeat rule fold the product of every constant factor in a chain, not just one multiply."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        return _mult_factors(node.left) + _mult_factors(node.right)
    return [node]


def _is_seq_literal(node: ast.expr) -> bool:
    """A list or tuple display, or a string or bytes literal — the operands `*` repeats into a
    larger sequence. A name that happens to hold a list is not one: its size is not in the source."""
    return isinstance(node, (ast.List, ast.Tuple)) or (
        isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes))
    )


def inspect(source: str) -> Verdict:
    """Static gate. Cheap, strict, and dumb on purpose."""
    if len(source) > config.GENOME_MAX_CHARS:  # before parsing: parsing megabytes is itself a cost
        return Verdict(False, [f"genome too long ({len(source)} > {config.GENOME_MAX_CHARS} chars)"])
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return Verdict(False, [f"SyntaxError: {e.msg} (line {e.lineno})"])

    reasons: list[str] = []
    has_live = False
    for node in tree.body:
        if isinstance(node, ast.Expr):
            if not isinstance(node.value, ast.Constant):  # a docstring is fine
                reasons.append("module-level expression with side effects")
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            if not _constant(ast.iter_child_nodes(node), _CONSTANT_NODES):
                reasons.append(_CONSTANT_RULE)
        elif isinstance(node, ast.FunctionDef):
            # defaults and annotations are evaluated when the def runs, which is module level
            if not _constant([node.args] + ([node.returns] if node.returns else []), _SIGNATURE_NODES):
                reasons.append(_CONSTANT_RULE)
            if node.name == "live":
                has_live = True
                if len(node.args.args) != 1:
                    reasons.append("live() must take exactly one argument")
        else:
            reasons.append(f"module-level {type(node).__name__} not allowed")
    if not has_live:
        reasons.append("no live(me) function")

    for node in ast.walk(tree):
        bound = _binds(node)
        if bound in ALLOWED_EXCEPTIONS:
            reasons.append(f"cannot rebind {bound}")
        if isinstance(node, ast.Attribute) and not isinstance(node.ctx, ast.Load):
            reasons.append(f"attributes are read-only: .{node.attr}")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            reasons.append("imports are not allowed (math and random are already in scope)")
        elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            reasons.append(f"forbidden name: {node.id}")
        elif isinstance(node, ast.Name) and node.id in _SET_NAMES:
            reasons.append(_SET_RULE)
        elif isinstance(node, (ast.Set, ast.SetComp)):
            reasons.append(_SET_RULE)
        elif isinstance(node, ast.Name) and node.id.startswith("__"):
            reasons.append(f"dunder name: {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            reasons.append(f"dunder access: .{node.attr}")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            reasons.append(f"private attribute: .{node.attr}")
        elif isinstance(node, ast.Attribute) and node.attr in BANNED_ATTRS:
            reasons.append(f"forbidden attribute: .{node.attr}")
        elif isinstance(node, (ast.Try, ast.TryStar)):
            if node.finalbody:
                reasons.append("finally not allowed")
            if isinstance(node, ast.TryStar):
                reasons.append("except* not allowed")
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            reasons.append("with not allowed")
        elif isinstance(node, ast.FunctionDef) and node.decorator_list:
            reasons.append("decorators not allowed")
        elif isinstance(node, ast.ExceptHandler):
            if node.type is None:
                reasons.append("bare except not allowed")
            elif not _names_only(node.type):
                reasons.append(_EXCEPT_RULE)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            reasons.append("global/nonlocal not allowed")
        elif isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.Yield, ast.YieldFrom)):
            reasons.append("async/generators not allowed")
        elif isinstance(node, ast.ClassDef):
            reasons.append("classes not allowed")
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            # The base is free (energy ** 2, x ** 0.5 are fine); only the exponent makes a bomb.
            exp = node.right
            if not _is_const_expr(exp):
                reasons.append(_POW_RULE)  # 2 ** me.age: the exponent is only known at runtime
            else:
                v = _fold_number(exp)
                # None means the exponent folded past the cap or is otherwise unrepresentable — a
                # constant bomb (2 ** 10**19, 2 ** 2**100), banned like the range and repeat rules
                # below; a small int, or any float (x ** 0.5, energy ** (1/2)), is not one.
                if v is None or (isinstance(v, int) and v > POW_MAX_EXP):
                    reasons.append(_POW_RULE)  # 2 ** 10**9, 2 ** 10**19: an oversized exponent
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            # A sequence literal repeated by constant factors, directly ([0] * 10**10) or through a
            # chain ([0] * 1000 * 1000 * 1000): fold the product of the factors and ban it if the
            # whole product is oversized. A factor the source does not fix ([0] * len(me.around))
            # leaves the product unknown and is left to the child's caps.
            factors = _mult_factors(node)
            seqs = [f for f in factors if _is_seq_literal(f)]
            others = [f for f in factors if not _is_seq_literal(f)]
            if len(seqs) == 1 and others and all(_is_const_expr(f) for f in others):
                product: int | None = 1
                for f in others:
                    v = _fold_number(f)
                    if v is None or not isinstance(v, int):
                        product = None  # unfoldable or non-integer factor: treat as oversized
                        break
                    product *= v
                    if product > MAX_LITERAL_COUNT:
                        break
                if product is None or product > MAX_LITERAL_COUNT:
                    reasons.append(_REPEAT_RULE)  # [0] * 10**10, [0] * 1000 * 1000 * 1000
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
            # range(n) / range(len(x)) is non-constant and left to the child. When every bound is a
            # constant integer the exact length is known, so compute it and ban a huge one — which
            # catches a negative-step form (range(0, -10**12, -1)) that comparing bounds in
            # isolation would miss. A bound past the fold cap is oversized however the rest read.
            folded = [_fold_number(a) if _is_const_expr(a) else None for a in node.args]
            oversized = any(v is None for a, v in zip(node.args, folded) if _is_const_expr(a))
            all_const_ints = bool(node.args) and not node.keywords and all(isinstance(v, int) for v in folded)
            if oversized:
                reasons.append(_RANGE_RULE)  # range(10**19): a bound past the fold cap
            elif all_const_ints:
                try:
                    length = len(range(*folded))
                except (TypeError, ValueError):
                    length = 0  # range(x, y, 0): a runtime error the smoke test surfaces, not a bomb
                if length > MAX_LITERAL_COUNT:
                    reasons.append(_RANGE_RULE)  # range(10**12), range(0, -10**12, -1)
    # dedupe, keep order
    seen = set()
    reasons = [r for r in reasons if not (r in seen or seen.add(r))]
    return Verdict(not reasons, reasons)


def compile_genome(source: str, rng: random.Random):
    """Compile into an isolated namespace. Returns the live() callable.

    `random` inside the genome is `rng` — the dish's own seeded generator — and
    not the module, so a genome reaches neither the module's private state nor
    an unseeded source of randomness.
    """
    ns = {"__builtins__": SAFE_BUILTINS, "math": math, "random": rng}
    code = compile(source, "<genome>", "exec")
    exec(code, ns)
    fn = ns.get("live")
    if not callable(fn):
        raise ValueError("live is not callable")
    return fn


class Lysis(BaseException):
    """The cell took too long. It bursts.

    A BaseException, not an Exception: `Exception` is the widest name a genome
    can catch, so nothing inside a genome can swallow the budget.
    """


_armed = False
_installed = False


def _alarm(signum, frame):
    if _armed:
        raise Lysis("time budget exceeded")


class Budget:
    """Context manager: a wall-clock budget for a single live() call.

    Signal-based, so it only works on the main thread — which is where the
    dish runs. Anything off the main thread must use admit_isolated().
    """

    def __init__(self, seconds: float):
        self.seconds = seconds

    def __enter__(self):
        global _armed, _installed
        if not _installed:
            signal.signal(signal.SIGALRM, _alarm)
            _installed = True
        _armed = True
        # One shot. Nothing in a genome can run after Lysis is raised (no finally, no
        # with, no bare or foreign except, no rebound exception name), and a second
        # alarm could land while the first is still unwinding through the dish's
        # handler, where it would escape the tick.
        signal.setitimer(signal.ITIMER_REAL, self.seconds)

    def __exit__(self, *exc):
        global _armed
        _armed = False
        signal.setitimer(signal.ITIMER_REAL, 0)
        return False


class _FakeMe:
    """A stand-in cell for smoke-testing a genome outside the dish."""

    def __init__(self, rng: random.Random, tick: int):
        self.rng = rng
        self.tick = tick
        self.age = rng.randint(0, 200)
        self.energy = rng.uniform(0.05, 1.8)
        self.here = rng.random()
        self.around = [rng.random() for _ in range(8)]
        self.crowd = [rng.random() < 0.4 for _ in range(8)]
        self.kin = [c and rng.random() < 0.6 for c in self.crowd]
        self.threat = self._threat(rng, self.crowd, self.around)
        self.neighbor_energy = self._neighbor_energy(self.crowd, self.around)
        self.scent = [rng.random() * 0.5 for _ in range(8)]
        self.scent_here = rng.random() * 0.5
        self.memory = {}
        self.strain = "test"
        self.population = rng.randint(1, 900)

    @staticmethod
    def _threat(rng: random.Random, crowd: list[bool], around: list[float]) -> list[float]:
        # a non-kin neighbour's energy on some occupied tiles, 0.0 elsewhere; scaled to 0..MAX_ENERGY
        # like a live neighbour's energy (Me.threat holds a cell's energy, not a nutrient), so a genome
        # that reads me.threat (a lyser, or a cell that flees) exercises its branch across the real
        # interval an energy-scale threshold would gate on
        return [e * config.MAX_ENERGY * (c and rng.random() < 0.6) for c, e in zip(crowd, around)]

    @staticmethod
    def _neighbor_energy(crowd: list[bool], around: list[float]) -> list[float]:
        # any occupied neighbour's energy, KIN INCLUDED, on the 0..MAX_ENERGY scale, 0.0 elsewhere,
        # so a genome that reads me.neighbor_energy (a giver) exercises its branch across the real
        # interval an energy-scale threshold would gate on. No rng draw: an occupied tile (crowd[d])
        # always carries an energy, so admission stays byte-for-byte what it was before sharing.
        return [e * config.MAX_ENERGY * c for c, e in zip(crowd, around)]


def smoke_test(source: str, rounds: int = 40) -> Verdict:
    """Dynamic gate: run live() against random situations. Must never throw.

    Module-level code and every round run under four times the cell's budget,
    so a genome that is merely slow on the stand-in is still admitted.
    """
    budget = config.CELL_TIME_BUDGET * 4
    rng = random.Random(12345)
    try:
        with Budget(budget):
            fn = compile_genome(source, rng)
    except Lysis:
        return Verdict(False, ["too slow: module level exceeded time budget"])
    except Exception as e:  # noqa: BLE001
        return Verdict(False, [f"failed to compile: {type(e).__name__}: {e}"])
    me = _FakeMe(rng, 0)
    for i in range(rounds):
        me.tick = i
        me.energy = rng.uniform(0.01, 1.9)
        me.here = rng.choice([0.0, rng.random()])
        me.around = [rng.choice([0.0, rng.random()]) for _ in range(8)]
        me.crowd = [rng.random() < (i / rounds) for _ in range(8)]
        me.kin = [c and rng.random() < 0.6 for c in me.crowd]
        me.threat = _FakeMe._threat(rng, me.crowd, me.around)
        me.neighbor_energy = _FakeMe._neighbor_energy(me.crowd, me.around)
        try:
            with Budget(budget):
                out = fn(me)
        except Lysis:
            return Verdict(False, ["too slow: exceeded time budget"])
        except Exception as e:  # noqa: BLE001
            return Verdict(False, [f"threw on tick {i}: {type(e).__name__}: {e}"])
        if not _valid_action(out):
            return Verdict(False, [f"returned an unknown action: {out!r}"])
        fault = memory_fault(me.memory)  # one dict across the rounds, so counters and trails grow as in the dish
        if fault:
            return Verdict(False, [f"{fault} (tick {i})"])
    return Verdict(True)


def _valid_action(out) -> bool:
    from .dish import parse_action

    return parse_action(out) is not None


# --- what a cell may keep: me.memory ------------------------------------------
_MEMORY_VALUES = "only None, bools, numbers, strings, lists, tuples and dicts may stay in it"
_MEMORY_KEYS = "keys must be strings, numbers, bools or None"
_MEMORY_ALIAS = "memory holds one list or dict in two places, or inside itself; keep a copy in each"


class _Fault(Exception):
    """Raised inside _walk with the reason; memory_fault returns it."""


def memory_fault(memory: dict) -> str | None:
    """The one rule the dish applies to `me.memory` after every `live()`: the reason the memory
    breaks it, or None.

    After a tick a cell's memory may hold only None, bools, ints, floats, strings, and lists,
    tuples and dicts of those, with string, number, bool or None keys; it may nest no deeper
    than MEMORY_MAX_DEPTH (the memory dict itself is depth 1); no list or dict in it may sit in
    two places or inside itself; and written as plain JSON (json.dumps of the memory itself, a
    tuple as a list and a numeric key as its string, before the file's type tags) it is at most
    MEMORY_MAX_CHARS long. One reason per clause. JSON is what a save is, so only what JSON can
    carry may stay. A save
    separates a list that sits in two places (a write to one shows in both before the save
    and in one after), so a shared list or dict is refused where a shared tuple, immutable,
    is not. `copy.deepcopy`, which a daughter's memory goes through, and the codec both
    recurse, so nesting stops where neither can run out of stack. And the check runs on every
    cell every tick, so its cost is bounded by the cap: one walk that keeps a lower and an
    upper bound on the JSON length and stops as soon as the lower one passes the cap, then
    `json.dumps` only for the few memories whose upper bound does not settle it.

    A cell whose memory breaks the rule bursts (lysis, before its action applies), so a
    daughter's memory is always a copy of one that passed; the smoke test refuses a genome
    that breaks it within its forty rounds and tells the mutagen the reason and the round.
    """
    if type(memory) is not dict:
        return f"memory is {_name(memory)}, not a dict"
    if not memory:
        return None
    cap, deepest = config.MEMORY_MAX_CHARS, config.MEMORY_MAX_DEPTH
    try:
        lo, hi = _walk(memory, 1, {id(memory)}, 0, 0, cap, deepest)
        if hi <= cap:  # certainly under: most memories, and no json.dumps for them
            return None
        n = len(json.dumps(memory))
    except _Fault as f:
        return f.args[0]
    except ValueError:  # an int json refuses (past 4300 digits) is over any cap this dish has run with
        return _too_large(cap)
    return _too_large(cap) if n > cap else None


def _too_large(cap: int) -> str:
    return f"memory over {cap} chars as JSON"


def _walk(v, depth: int, seen: set, lo: int, hi: int, cap: int, deepest: int) -> tuple[int, int]:
    """Walk one admitted container (a list, tuple or dict at `depth`): its leaves inline, its
    containers by recursion. Returns two running figures that bracket the length of the JSON so
    far, `lo <= len(json.dumps(...)) <= hi` (a seeded test pins both): per element 2 for brackets
    and separators; per string len + 2 below and 12 * len + 2 above (ensure_ascii writes an
    astral character as twelve); per key 4 more; per int a quarter of its bits below and a third
    plus a sign above; 3 to 24 per float, 4 to 5 per bool or None. The walk stops as soon as `lo`
    passes the cap, so it can only say "too large" earlier than json.dumps would, never
    differently, and the work it does is bounded by the cap and not by the memory. Raises _Fault
    with the reason for anything the rule refuses."""
    n = len(v)
    lo += 2 * n
    hi += 2 * n or 2
    if lo > cap:
        raise _Fault(_too_large(cap))
    if type(v) is dict:
        for k in v:
            tk = type(k)
            if tk is str:
                m = len(k)
                lo += m + 4
                hi += 12 * m + 4
            elif tk is int:
                b = k.bit_length()
                lo += (b >> 2) + 4
                hi += b // 3 + 7
            elif tk is float:
                lo += 7
                hi += 28
            elif tk is bool or k is None:
                lo += 7
                hi += 9
            else:
                raise _Fault(f"memory has {_name(k)} as a key; {_MEMORY_KEYS}")
        if lo > cap:
            raise _Fault(_too_large(cap))
        v = v.values()
    for x in v:
        tx = type(x)
        if tx is int:
            b = x.bit_length()
            lo += b >> 2
            hi += b // 3 + 3
        elif tx is str:
            m = len(x)
            lo += m + 2
            hi += 12 * m + 2
        elif tx is float:
            lo += 3
            hi += 24
        elif tx is bool or x is None:
            lo += 4
            hi += 5
        elif tx is list or tx is dict:
            if depth >= deepest:
                raise _Fault(f"memory nested deeper than {deepest}")
            if id(x) in seen:
                raise _Fault(_MEMORY_ALIAS)
            seen.add(id(x))
            lo, hi = _walk(x, depth + 1, seen, lo, hi, cap, deepest)
        elif tx is tuple:  # immutable, so one tuple in two places is no different from two copies
            if depth >= deepest:
                raise _Fault(f"memory nested deeper than {deepest}")
            lo, hi = _walk(x, depth + 1, seen, lo, hi, cap, deepest)
        else:
            raise _Fault(f"memory holds {_name(x)}; {_MEMORY_VALUES}")
    if lo > cap:
        raise _Fault(_too_large(cap))
    return lo, hi


def _name(v) -> str:
    """What to call a value the rule refuses: `me` for the cell itself, `a function` for
    anything callable, otherwise its type."""
    kind = type(v).__name__
    if kind in ("Me", "_FakeMe"):
        return "me"
    if callable(v):
        return "a function"
    return f"an {kind}" if kind[:1].lower() in "aeiou" else f"a {kind}"


def admit(source: str) -> Verdict:
    """Full gate: static then dynamic."""
    v = inspect(source)
    if not v:
        return v
    return smoke_test(source)


def admit_isolated(source: str, timeout: float = 20.0) -> Verdict:
    """admit(), but in a fresh interpreter. Safe to call from any thread."""
    import subprocess
    import sys

    try:
        r = subprocess.run(
            [sys.executable, "-m", "bio.membrane"],
            input=source,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(config.ROOT),
        )
    except subprocess.TimeoutExpired:
        return Verdict(False, ["too slow: smoke test timed out"])
    try:
        d = json.loads(r.stdout.strip().splitlines()[-1])
        return Verdict(d["ok"], d["reasons"])
    except (json.JSONDecodeError, IndexError, KeyError):
        return Verdict(False, [f"membrane crashed: {(r.stderr or r.stdout)[-200:]}"])


def _limit_resources() -> None:
    """Cap the isolated child's address space and CPU, so a resource bomb the smoke test runs
    cannot exhaust the box before the wall-clock timeout reaps it. Best-effort: macOS refuses to
    lower RLIMIT_AS/RLIMIT_DATA below an infinite hard limit, so there the static gate and the
    wall timeout are the backstop, while RLIMIT_CPU works on both. Called once inside the child,
    after exec, where the process is fresh and single-threaded so setrlimit is fork-safe — this
    is deliberately not a subprocess preexec_fn, which would run in a fork of the multithreaded
    mutagen process and can deadlock on the fork-with-threads interaction."""
    try:
        import resource
    except ImportError:  # not a POSIX platform; the wall timeout is the only backstop there
        return

    for name in ("RLIMIT_AS", "RLIMIT_DATA"):
        limit = getattr(resource, name, None)
        if limit is None:
            continue
        try:
            _, hard = resource.getrlimit(limit)
            cap = CHILD_AS_LIMIT if hard == resource.RLIM_INFINITY else min(CHILD_AS_LIMIT, hard)
            resource.setrlimit(limit, (cap, hard))
        except (ValueError, OSError):
            pass
    try:
        _, hard = resource.getrlimit(resource.RLIMIT_CPU)
        cap = CHILD_CPU_LIMIT if hard == resource.RLIM_INFINITY else min(CHILD_CPU_LIMIT, hard)
        resource.setrlimit(resource.RLIMIT_CPU, (cap, hard))
    except (ValueError, OSError):
        pass


if __name__ == "__main__":
    import sys

    _limit_resources()
    v = admit(sys.stdin.read())
    print(json.dumps({"ok": v.ok, "reasons": v.reasons}))
