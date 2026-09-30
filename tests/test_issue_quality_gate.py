#!/usr/bin/env python3
"""`issue-quality-gate.yml` grants `ready` only with an acceptance-criteria section *and* checkboxes.

The rule spent its life half-vacuous. Its AC pattern was `acceptance criteria|AC|验收标准|MANDATORY` with no
word boundaries, so **any** body containing the letters "ac" anywhere — "characters", "exact", "practical" —
satisfied the AC half, and only the checkbox half was doing any work (measured 2026-09-30 with
`re.search(..., "characters", re.I)`, which is truthy).

The mirror image showed up the same day: `## 验收` — the heading this repository's own issues use — was **not**
recognised (only `验收标准` was), so issues carrying real acceptance criteria were labelled `needs-ac`.

These tests extract the pattern **out of the workflow** and drive it, so the rule is checked as it is actually
written (the same approach `tests/test_audit_report_truth.py` takes with the report's expressions): a future
edit that loosens it again fails here rather than in the tracker.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE = REPO / ".github" / "workflows" / "issue-quality-gate.yml"

# Bodies that must count as carrying acceptance criteria, and bodies that must not. The rejects are the
# point: each contains "ac" in a word, which the old pattern accepted.
WITH_AC = (
    "## Acceptance Criteria\n- [ ] the export succeeds\n- [ ] the file is not truncated",
    "## 验收标准\n- [ ] 导出成功",
    "## 验收\n- [ ] 通过",
    "## 完成标准\n- [x] 已复核",
    "This is MANDATORY: see the AC below.\n- [ ] done",
)
WITHOUT_AC = (
    "characters in the log were truncated\n- [ ] reproduce",
    "the exact match failed\n- [ ] fix it",
    "a practical example would help\n- [ ] write one",
    "no criteria here at all\n- [ ] something",
)
CHECKBOXES = re.compile(r"\[ \]|\[x\]|\[X\]", re.I)


def ac_pattern() -> re.Pattern:
    """The gate's acceptance-criteria regex, lifted from the workflow."""
    found = re.search(r"if \(/(.+?)/i\.test\(body\)\)", GATE.read_text(encoding="utf-8"))
    assert found, "the AC pattern moved — this rule must move with it (or the gate's rule was deleted)"
    return re.compile(found.group(1), re.I)


def test_the_gate_pattern_recognises_real_acceptance_criteria():
    pattern = ac_pattern()
    for body in WITH_AC:
        assert pattern.search(body), f"the gate does not see acceptance criteria in:\n{body}"
        assert CHECKBOXES.search(body), "the fixture must also carry checkboxes (the other half of the rule)"


def test_the_gate_pattern_is_not_satisfied_by_the_letters_ac_inside_a_word():
    pattern = ac_pattern()
    offenders = [body for body in WITHOUT_AC if pattern.search(body)]
    assert not offenders, (
        "these bodies contain no acceptance criteria, yet the gate's pattern accepts them — an unbounded "
        "`AC` alternative matches any 'ac' inside a word, which makes this half of the rule decorative:\n  - "
        + "\n  - ".join(body.splitlines()[0] for body in offenders))


def test_the_rule_still_requires_both_halves():
    text = GATE.read_text(encoding="utf-8")
    assert "const satisfied = HAS_AC && HAS_CHECKBOX;" in text, (
        "the gate must require the AC section *and* a checkbox list; one half alone is not a spec")
    assert "labels.push('needs-ac')" in text and "labels.push('ready')" in text, (
        "the two verdicts must both exist, or the label means nothing")


def test_the_label_pair_stays_mutually_exclusive():
    """`needs-ac` next to `ready` was a real complaint; the gate clears the stale one on every event."""
    text = GATE.read_text(encoding="utf-8")
    assert "const stale = satisfied ? 'needs-ac' : 'ready';" in text, (
        "an issue that gains acceptance criteria must lose `needs-ac` (and vice versa), or the tracker shows "
        "missing work that is not missing")
    assert "removeLabel" in text, "the stale label is never removed"


def test_intakes_and_digests_are_exempt_and_the_exemption_is_named():
    """Reports are not specs: an intake has no acceptance criteria to hold (2026-09-13, five of six
    `needs-ac` issues were intakes, including a digest this repository's own workflow opened)."""
    text = GATE.read_text(encoding="utf-8")
    for label in ("intake", "mcp-intake", "salvage-digest", "question-digest"):
        assert f"'{label}'" in text, f"{label} left the exemption list — that label would collect `needs-ac`"
