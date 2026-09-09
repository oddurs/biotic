"""The membrane: decides what code is allowed to become a cell.

A genome is Python source defining `live(me)`. Before it can run inside the
dish it has to pass through here: no imports, no dunders, no escape hatches,
and it must survive a few dozen simulated ticks without throwing.
"""

from __future__ import annotations

import ast
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
        "set",
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

ALLOWED_TOP_LEVEL = (ast.FunctionDef, ast.Assign, ast.AnnAssign, ast.Expr)


@dataclass
class Verdict:
    ok: bool
    reasons: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.ok


def inspect(source: str) -> Verdict:
    """Static gate. Cheap, strict, and dumb on purpose."""
    reasons: list[str] = []
    if len(source) > config.GENOME_MAX_CHARS:
        reasons.append(f"genome too long ({len(source)} > {config.GENOME_MAX_CHARS} chars)")
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return Verdict(False, [f"SyntaxError: {e.msg} (line {e.lineno})"])

    has_live = False
    for node in tree.body:
        if isinstance(node, ast.Expr) and not isinstance(node.value, ast.Constant):
            reasons.append("module-level expression with side effects")
        elif not isinstance(node, ALLOWED_TOP_LEVEL):
            reasons.append(f"module-level {type(node).__name__} not allowed")
        if isinstance(node, ast.FunctionDef) and node.name == "live":
            has_live = True
            if len(node.args.args) != 1:
                reasons.append("live() must take exactly one argument")
    if not has_live:
        reasons.append("no live(me) function")

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            reasons.append("imports are not allowed (math and random are already in scope)")
        elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            reasons.append(f"forbidden name: {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            reasons.append(f"dunder access: .{node.attr}")
        elif isinstance(node, ast.Name) and node.id.startswith("__"):
            reasons.append(f"dunder name: {node.id}")
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


def compile_genome(source: str):
    """Compile into an isolated namespace. Returns the live() callable."""
    ns = {"__builtins__": SAFE_BUILTINS, "math": math, "random": random}
    code = compile(source, "<genome>", "exec")
    exec(code, ns)
    fn = ns.get("live")
    if not callable(fn):
        raise ValueError("live is not callable")
    return fn


class Lysis(Exception):
    """The cell took too long. It bursts."""


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
    """Dynamic gate: run live() against random situations. Must never throw."""
    try:
        fn = compile_genome(source)
    except Exception as e:  # noqa: BLE001
        return Verdict(False, [f"failed to compile: {type(e).__name__}: {e}"])
    rng = random.Random(12345)
    me = _FakeMe(rng, 0)
    for i in range(rounds):
        me.tick = i
        me.energy = rng.uniform(0.01, 1.9)
        me.here = rng.choice([0.0, rng.random()])
        me.around = [rng.choice([0.0, rng.random()]) for _ in range(8)]
        me.crowd = [rng.random() < (i / rounds) for _ in range(8)]
        me.kin = [c and rng.random() < 0.6 for c in me.crowd]
        try:
            with Budget(config.CELL_TIME_BUDGET * 4):
                out = fn(me)
        except Lysis:
            return Verdict(False, ["too slow: exceeded time budget"])
        except Exception as e:  # noqa: BLE001
            return Verdict(False, [f"threw on tick {i}: {type(e).__name__}: {e}"])
        if not _valid_action(out):
            return Verdict(False, [f"returned an unknown action: {out!r}"])
    return Verdict(True)


def _valid_action(out) -> bool:
    from .dish import parse_action

    return parse_action(out) is not None


def admit(source: str) -> Verdict:
    """Full gate: static then dynamic."""
    v = inspect(source)
    if not v:
        return v
    return smoke_test(source)


def admit_isolated(source: str, timeout: float = 20.0) -> Verdict:
    """admit(), but in a fresh interpreter. Safe to call from any thread."""
    import json
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
    import json
    import sys

    v = admit(sys.stdin.read())
    print(json.dumps({"ok": v.ok, "reasons": v.reasons}))
