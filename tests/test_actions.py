"""parse_action: the grammar of what a genome may return.

A genome's return value is untrusted input to the dish. parse_action turns it
into (kind, arg) or None and must never raise, whatever it is handed.
"""

from __future__ import annotations

import math
import random

import pytest

from bio import config
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
    (("lyse", 1), ("lyse", 1)),
    (("lyse", 9), ("lyse", 1)),  # wraps mod 8, like move and divide
    (("lyse", "3"), ("lyse", 3)),
    (("lyse", -1), ("lyse", 7)),
    (("give", 2, 0.4), ("give", (2, 0.4))),
    (("give", 9, 0.4), ("give", (1, 0.4))),  # the direction wraps mod 8
    (("give", "2", "0.4"), ("give", (2, 0.4))),  # both coerce
    (("give", 2, 5), ("give", (2, 2.0))),  # the amount clamps up to MAX_ENERGY
    (("give", 2, -1), ("give", (2, 0.0))),  # and down to 0
    (("share", 1, 0.2), ("give", (1, 0.2))),  # alias
    (["give", 2, 0.4], ("give", (2, 0.4))),  # a list is a tuple
]

REJECTED = [
    True,
    False,
    ("move", True),  # int(True) is 1, but a bool is not a direction
    ("divide", False),
    ("emit", True),  # nor an amount
    "",
    "photosynthesize",
    "go",  # a bare alias for move has no direction
    ("move", None),
    ("emit", "x"),
    ("lyse",),  # a bare lyse names no neighbour
    ("lyse", None),
    ("lyse", True),  # int(True) is 1, but a bool is not a direction
    ("give", 1),  # give needs both a direction and an amount
    ("give",),
    ("give", True, 0.5),  # a bool is not a direction
    ("give", 2, True),  # nor an amount
    ("give", 2, float("nan")),  # nan is nonsense, not "give everything"
    ("give", float("inf"), 0.5),  # int(inf) does not exist
    ("give", 2, 10**400),  # float(that) overflows
    (),
    (1, 2),
    ("move", 1, 2),  # move takes at most one argument
    ("give", 2, 0.4, 0.4),  # four elements is nonsense
    {},
    set(),
    b"eat",
    float("nan"),
    float("inf"),
    ("move", float("inf")),
    ("divide", float("nan")),
    ("emit", float("nan")),  # nan is nonsense, not "emit everything"
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
    names = [
        "eat",
        "rest",
        "move",
        "divide",
        "emit",
        "split",
        "sleep",
        "wait",
        "stay",
        "go",
        "feed",
        "lyse",
        "give",
        "share",
        "x",
        "",
    ]
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

    kinds = {"eat", "rest", "move", "divide", "emit", "lyse", "give"}
    for _ in range(3000):
        given = value()
        out = parse_action(given)
        if out is None:
            continue
        assert isinstance(out, tuple) and len(out) == 2
        kind, arg = out
        assert kind in kinds
        if isinstance(given, (tuple, list)) and len(given) == 2 and isinstance(given[1], bool):
            assert kind in ("eat", "rest"), (given, out)  # a bool never becomes a direction or an amount
        if kind in ("move", "lyse"):
            assert isinstance(arg, int) and 0 <= arg < 8
        elif kind == "divide":
            assert arg is None or (isinstance(arg, int) and 0 <= arg < 8)
        elif kind == "emit":
            assert isinstance(arg, float) and 0.0 <= arg <= 1.0
        elif kind == "give":
            assert isinstance(arg, tuple) and len(arg) == 2
            assert isinstance(arg[0], int) and 0 <= arg[0] < 8
            assert isinstance(arg[1], float) and 0.0 <= arg[1] <= config.MAX_ENERGY
        else:
            assert arg is None
