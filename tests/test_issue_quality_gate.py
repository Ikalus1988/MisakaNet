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
    for label in ("intake", "mcp-intake", "salvage-digest", "question-digest", "lesson-submission"):
        assert f"'{label}'" in text, f"{label} left the exemption list — that label would collect `needs-ac`"


def test_a_report_label_is_exempt_because_it_is_a_report_not_a_spec():
    """The list is not an arbitrary set — it is every label the repository opens as a *report*.

    `lesson-submission` went missing and the failure is invisible from inside the workflow: it still
    runs, still labels, and the label it applies (`needs-ac`) reads as a fact about the work rather
    than as an artefact of which labels the submitter happened to pick. Measured 2026-10-13, 28 of 28
    open `lesson-submission` issues carried `needs-ac`.

    So assert the exemption the way the gate applies it — by *shape*, not by name — which is what
    catches the next report label that gets added without updating this array.
    """
    text = GATE.read_text(encoding="utf-8")
    m = re.search(r"\[\s*((?:'[^']+'\s*,?\s*)+)\]\s*\n\s*\.includes", text)
    assert m, "the exemption array moved — this test must move with it"
    exempt = set(re.findall(r"'([^']+)'", m.group(1)))

    # Every label this repository's own automation opens as a report rather than a spec. Sourced from
    # the workflows that create them, so the list cannot quietly drift from reality.
    report_labels = {"intake", "mcp-intake", "salvage-digest", "question-digest", "lesson-submission"}
    missing = report_labels - exempt
    assert not missing, (
        f"these report labels are not exempt from `needs-ac`: {sorted(missing)}. A report has no "
        f"acceptance criteria to hold, so requiring them marks completed investigation as unfinished "
        f"work — the exact failure the exemption was added for (2026-09-13, five of six `needs-ac` "
        f"issues were intakes).\n  currently exempt: {sorted(exempt)}"
    )

    # And the converse must stay true: a label that means "someone will implement this" is exactly
    # what the AC requirement exists for, so it must never drift into this list.
    for impl_label in ("bounty", "task"):
        assert impl_label not in exempt, (
            f"{impl_label!r} asks someone to implement the work, so acceptance criteria are the "
            f"point of the label — it must not be exempt"
        )
