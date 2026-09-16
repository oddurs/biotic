"""What the mutagen is told must match the rule the membrane enforces.

CELL_API is prose handed to a language model; the membrane is code. When the two drift the
prompt teaches a rule that is not the one applied, and a genome that follows the prompt is
either refused for something it was told was fine or told a bound it does not actually have.
These pin the clauses that had drifted.
"""

from __future__ import annotations

from bio.membrane import _MEMORY_KEYS
from bio.prompts import CELL_API


def test_cell_api_lists_the_memory_key_types_the_rule_admits():
    """`_walk` admits str, int, float, bool and None keys; `_MEMORY_KEYS` and docs/membrane.md
    both name those four JSON key types. CELL_API once said only 'strings or numbers', narrower
    than the rule. It must carry the same wording as the refusal string, so the three places the
    rule is described agree."""
    key_types = _MEMORY_KEYS.split("keys must be ", 1)[1]
    assert key_types == "strings, numbers, bools or None"
    assert key_types in CELL_API


def test_cell_api_puts_the_memory_cap_on_the_plain_json_form():
    """The cap is measured on the plain JSON of the memory itself, not on the tagged on-disk
    form. CELL_API once said 'characters when written as JSON', which a reader takes to mean the
    saved file; the saved file can be larger. The prompt must not imply the on-disk size."""
    assert "as plain JSON" in CELL_API
    assert "when written as JSON" not in CELL_API
