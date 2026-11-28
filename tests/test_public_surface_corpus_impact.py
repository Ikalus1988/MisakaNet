#!/usr/bin/env python3
"""What a `_is_command_span` widening actually costs, measured over the whole corpus.

`lesson_gate` is a gate on 1,200+ published lessons, so "does this shape unblock the intake that
motivated it" is only half the question. The other half is "how many lessons start being checked for
different names", and that number is what decides whether a shape belongs in `_DATA_SPAN_PATTERNS`.

The 2026-11-28 additions were each measured this way before landing, and the numbers are recorded in
the gate's own comment block. A comment is not a gate though, so this file re-derives them: if a
future edit widens `_COMPARISON` to any `=` (which was rejected: 48 lessons changed, 51 allowlisted
names dropped), the assertion here goes red with the measured numbers rather than passing review
because the comment still says "measured".

Why a corpus test rather than fixtures: the fixtures pin the *shape* of each rule (that a units cell
is rejected and `pytest -q` is not), while this file pins the *size of the blast radius*. Both are
needed — the first catches "this rule is wrong", the second catches "this rule is right but much
bigger than the comment claims".
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import lesson_gate  # noqa: E402

LESSONS = sorted((REPO / "lessons").rglob("*.md"))


def _identifiers(text: str, body: str) -> set[str]:
    return set(lesson_gate.command_surface_identifiers(text, prose_source=body))


@pytest.fixture(scope="module")
def corpus():
    if not LESSONS:
        pytest.skip("no lessons/ in this checkout")
    rows = []
    for path in LESSONS:
        text = path.read_text(encoding="utf-8")
        _fm, body = lesson_gate.parse_frontmatter(text)
        rows.append((path, text, body))
    return rows


#: The shapes as they were before 2026-11-28. Every number below is measured against this baseline,
#: never against whatever the module currently holds — otherwise a shape would be measured against
#: itself and the difference would always be empty.
BASELINE = (lesson_gate._UNITS_ROW, lesson_gate._SQL_NULL_PREDICATE)


def _impact(corpus, patterns) -> tuple[int, set[str]]:
    """How many lessons change, and which names stop being checked, relative to `BASELINE`."""
    original = lesson_gate._DATA_SPAN_PATTERNS
    try:
        rows = []
        for _path, text, body in corpus:
            lesson_gate._DATA_SPAN_PATTERNS = BASELINE
            before = _identifiers(text, body)
            lesson_gate._DATA_SPAN_PATTERNS = tuple(patterns)
            after = _identifiers(text, body)
            rows.append((before, after))
    finally:
        lesson_gate._DATA_SPAN_PATTERNS = original
    changed = sum(1 for before, after in rows if before != after)
    lost: set[str] = set()
    for before, after in rows:
        lost |= before - after
    return changed, lost


def test_the_units_cell_shape_is_free(corpus):
    """`Tm [Nm]` — measured 0 lessons changed. The comma form was already covering the table."""
    changed, lost = _impact(corpus, BASELINE + (lesson_gate._UNITS_CELL,))
    assert (changed, lost) == (0, set()), (
        f"the units-cell shape changes {changed} lesson(s) and stops checking {sorted(lost)}")


def test_the_approximation_shape_is_free(corpus):
    """`vy ≈ -190` — measured 0 lessons changed."""
    changed, lost = _impact(corpus, BASELINE + (lesson_gate._APPROXIMATION,))
    assert (changed, lost) == (0, set()), (
        f"the approximation shape changes {changed} lesson(s) and stops checking {sorted(lost)}")


def test_the_comparison_shape_stays_small(corpus):
    """`total == 0` — measured 14 lessons, 16 names, every one a predicate head.

    The bound is a ceiling rather than an equality: lessons keep being added, and a few more
    comparisons arriving is expected. What must not happen is the *class* widening — rejecting any
    `=` instead of a comparison against a literal changes 48 lessons and drops 51 names that are not
    allowlisted, and that is the number this assertion exists to separate.
    """
    changed, lost = _impact(corpus, BASELINE + (lesson_gate._COMPARISON,))
    assert changed <= 25, f"comparison shape changes {changed} lessons; measured 14 on 2026-11-28"
    assert len(lost) <= 30, f"comparison shape stops checking {len(lost)} names: {sorted(lost)}"


def test_the_alarm_code_shape_stays_small(corpus):
    """`MEMO-128 parameters are different` — measured 6 lessons, 6 names, all alarm codes."""
    changed, lost = _impact(corpus, BASELINE + (lesson_gate._ALARM_CODE,))
    assert changed <= 15, f"alarm-code shape changes {changed} lessons; measured 6 on 2026-11-28"
    assert len(lost) <= 15, f"alarm-code shape stops checking {len(lost)} names: {sorted(lost)}"
    # The names it stops checking should look like codes, not like programs.
    for name in lost:
        assert any(ch.isdigit() for ch in name), f"{name!r} is not an alarm code"


def test_an_assignment_rule_would_cost_too_much(corpus):
    """The shape that was measured and **rejected**, kept as a recorded decision (#5171, #5895).

    A bare `KEY = value` rule is the obvious next step and it is why those two intakes are still
    open. Re-running it here is the only way to keep that honest: if the cost ever drops (the corpus
    rewrites those spans), this assertion goes red and the decision is worth revisiting. Until then,
    `BS = chr(92)` is treated as a command and the intake needs its span rewritten — not the gate.
    """
    import re

    assignment = re.compile(r"^\$?\s*[A-Za-z_][\w.\[\]]*\s+=\s+\S")
    changed, lost = _impact(corpus, BASELINE + (assignment,))
    assert changed >= 30, (
        f"the assignment rule now changes only {changed} lessons — the recorded cost was 48; "
        f"revisit #5171 / #5895 if that is real")
    assert len(lost) >= 30, (
        f"the assignment rule now stops checking only {len(lost)} names — recorded 51; the trade "
        f"may be affordable now, so re-measure and update the gate's comment")
