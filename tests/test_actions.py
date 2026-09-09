"""parse_action: the grammar of what a genome may return.

A genome's return value is untrusted input to the dish. parse_action turns it
into (kind, arg) or None and must never raise, whatever it is handed.
"""

from __future__ import annotations

import math
import random

import pytest

from bio.dish import parse_action

ACCEPTED = [
    ("eat", ("eat", None)),
    ("rest", ("rest", None)),
    ("divide", ("divide", None)),
    (None, ("rest", None)),
    ("split", ("divide", None)),
    ("sleep", ("rest", None)),
    ("wait", ("rest", None)),
    ("stay", ("rest", None)),
    ("feed", ("eat", None)),
    (" EAT ", ("eat", None)),
    (3, ("move", 3)),
    (11, ("move", 3)),
    (-1, ("move", 7)),
    (2.9, ("move", 2)),
    (("move", 11), ("move", 3)),
    (("move", "3"), ("move", 3)),
    (["move", 3], ("move", 3)),
    (("go", 3), ("move", 3)),
    (("divide",), ("divide", None)),
    (("divide", 9), ("divide", 1)),
    (("emit",), ("emit", 0.2)),
    (("emit", 5), ("emit", 1.0)),
    (("emit", -1), ("emit", 0.0)),
    (("eat", 99), ("eat", None)),
]

REJECTED = [
    True,
    False,
    "",
    "photosynthesize",
    "go",  # a bare alias for move has no direction
    ("move", None),
    ("emit", "x"),
    ("lyse", 1),  # flip this row when predation lands
    (),
    (1, 2),
    ("move", 1, 2),
    {},
    set(),
    b"eat",
    float("nan"),
    float("inf"),
    ("move", float("inf")),
    ("divide", float("nan")),
    ("emit", 10**400),
]


@pytest.mark.parametrize("out,expected", ACCEPTED, ids=[repr(a) for a, _ in ACCEPTED])
def test_accepted_forms_parse_to_their_action(out, expected):
    assert parse_action(out) == expected


@pytest.mark.parametrize("out", REJECTED, ids=[repr(r)[:30] for r in REJECTED])
def test_nonsense_parses_to_none(out):
    assert parse_action(out) is None


def test_parse_action_never_raises():
    """A fuzz over the kinds of value a genome can produce. Fixed seed; ~3000 cases."""
    rng = random.Random(2024)
    names = ["eat", "rest", "move", "divide", "emit", "split", "sleep", "wait", "stay", "go", "feed", "lyse", "x", ""]
    odd = [math, random.Random(), ValueError("x"), (i for i in range(3)), range(3), lambda: 1, b"eat", {}, set()]

    def word():
        s = rng.choice(names)
        return rng.choice([s, s.upper(), s.title(), f" {s} ", f"\t{s}\n"])

    def scalar():
        pick = rng.randrange(9)
        if pick == 0:
            return None
        if pick == 1:
            return rng.choice([True, False])
        if pick == 2:
            return rng.randint(-20, 20)
        if pick == 3:
            return rng.choice([10**40, -(10**40), 10**400])
        if pick == 4:
            return rng.uniform(-1e3, 1e3)
        if pick == 5:
            return rng.choice([float("nan"), float("inf"), float("-inf"), 1e308, -0.0])
        if pick == 6:
            return word()
        if pick == 7:
            return rng.choice(odd)
        return frozenset()

    def value(depth=0):
        if depth < 2 and rng.random() < 0.5:
            items = [value(depth + 1) for _ in range(rng.randint(0, 4))]
            if items and rng.random() < 0.6:
                items[0] = word()
            return rng.choice([tuple, list])(items)
        return scalar()

    kinds = {"eat", "rest", "move", "divide", "emit"}
    for _ in range(3000):
        out = parse_action(value())
        if out is None:
            continue
        assert isinstance(out, tuple) and len(out) == 2
        kind, arg = out
        assert kind in kinds
        if kind == "move":
            assert isinstance(arg, int) and 0 <= arg < 8
        elif kind == "divide":
            assert arg is None or (isinstance(arg, int) and 0 <= arg < 8)
        elif kind == "emit":
            assert isinstance(arg, float) and 0.0 <= arg <= 1.0
        else:
            assert arg is None
