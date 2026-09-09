"""The membrane must admit viable genomes and reject escape hatches."""

from bio.culture import FALLBACK_GENESIS
from bio.membrane import admit, inspect


def test_fallback_genesis_is_admitted():
    assert admit(FALLBACK_GENESIS)


def test_imports_are_rejected():
    v = inspect("import os\n\ndef live(me):\n    return 'rest'\n")
    assert not v
    assert any("imports are not allowed" in r for r in v.reasons)


def test_missing_live_is_rejected():
    v = inspect("def grow(me):\n    return 'eat'\n")
    assert not v
    assert "no live(me) function" in v.reasons


def test_banned_names_and_dunders_are_rejected():
    v = inspect("def live(me):\n    return eval('1').__class__\n")
    assert not v
    assert "forbidden name: eval" in v.reasons
    assert "dunder access: .__class__" in v.reasons


def test_genome_that_throws_fails_the_smoke_test():
    v = admit("def live(me):\n    return me.around[99]\n")
    assert not v
    assert v.reasons[0].startswith("threw on tick")
