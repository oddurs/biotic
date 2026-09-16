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
        self.scent = [rng.random() * 0.5 for _ in range(8)]
        self.scent_here = rng.random() * 0.5
        self.memory = {}
        self.strain = "test"
        self.population = rng.randint(1, 900)


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
    two places or inside itself; and written as JSON it is at most MEMORY_MAX_CHARS long. One
    reason per clause. JSON is what a save is, so only what JSON can carry may stay. A save
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


if __name__ == "__main__":
    import sys

    v = admit(sys.stdin.read())
    print(json.dumps({"ok": v.ok, "reasons": v.reasons}))
