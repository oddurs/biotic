"""Tests for the pure metric helpers of the 0041 model-comparison analysis."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "exp0041", Path(__file__).resolve().parent.parent / "scripts" / "exp0041.py"
)
assert _spec and _spec.loader
exp0041 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exp0041)


def test_pass_rate() -> None:
    assert exp0041.pass_rate(7, 10) == 0.7
    assert exp0041.pass_rate(0, 5) == 0.0
    assert exp0041.pass_rate(3, 0) is None
    assert exp0041.pass_rate(1, -1) is None


def test_slope_per_1000_linear() -> None:
    # arisen climbing by 2 per tick -> 2000 per 1000 ticks
    pts = [(float(t), 2.0 * t) for t in range(0, 100, 10)]
    assert exp0041.slope_per_1000(pts) == 2000.0


def test_slope_per_1000_flat_and_degenerate() -> None:
    assert exp0041.slope_per_1000([(t, 5.0) for t in range(5)]) == 0.0
    assert exp0041.slope_per_1000([(3.0, 9.0)]) is None
    assert exp0041.slope_per_1000([(2.0, 1.0), (2.0, 8.0)]) is None


def test_diff_changed_lines() -> None:
    a = "def live(me):\n    return me.eat()\n"
    b = "def live(me):\n    return me.eat()\n"
    assert exp0041.diff_changed_lines(a, b) == 0
    c = "def live(me):\n    return me.divide()\n"
    # one line removed, one added
    assert exp0041.diff_changed_lines(a, c) == 2


def test_classify_size_boundaries() -> None:
    assert exp0041.classify_size(0) == "small"
    assert exp0041.classify_size(3) == "small"
    assert exp0041.classify_size(4) == "medium"
    assert exp0041.classify_size(12) == "medium"
    assert exp0041.classify_size(13) == "rewrite"


def test_percentile() -> None:
    assert exp0041._percentile([], 0.95) is None
    assert exp0041._percentile([4.0], 0.95) == 4.0
    assert exp0041._percentile([0.0, 10.0], 0.5) == 5.0
