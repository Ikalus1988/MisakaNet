#!/usr/bin/env python3
"""A lesson whose slug contains "template" is a lesson, not a template file.

Three readers filtered lessons with `"TEMPLATE" in name.upper()` — a substring test meant to skip
`lessons/TEMPLATE.md`. It also skipped every lesson whose slug happens to contain the word:

* `scripts/evidence_distribution.py` → the trust page said **746** lessons while `docs/_lessons_count.txt`
  said **749** (the audit's F13 numbers that disagree, with a concrete cause);
* `scripts/intake_receipt.py` → those lessons were invisible to the provenance resolver, so an intake
  cited only by one of them could never receive a receipt, and `done_but_open` would never see it
  (`platform-issue-template-commands-need-the-platform-installed` cites #3418 — measurable);
* `scripts/pipeline_status.py` → the heartbeat's conversion numbers understated the corpus the same way.

The three files are real lessons, two of them published before the audit. The fix is to compare the
filename, which is what `misakanet.lesson_index.EXCLUDED_LESSON_FILES` already does.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts import evidence_distribution, intake_receipt, pipeline_status  # noqa: E402


def _template_named_lessons() -> list[Path]:
    return sorted(p for p in (REPO / "lessons").rglob("*.md")
                  if p.name != "TEMPLATE.md" and "template" in p.name.lower())


def test_the_corpus_actually_contains_such_lessons():
    """Guard the guard: with none on disk these tests would pass without testing anything."""
    assert len(_template_named_lessons()) >= 2, _template_named_lessons()


def test_the_evidence_count_sees_them():
    counted = evidence_distribution.collect()
    total = sum(counted.values())
    published = len(__import__("json").loads((REPO / "data" / "lessons.json").read_text(encoding="utf-8")))
    assert total == published, f"evidence table counts {total}, the corpus publishes {published}"


def test_the_provenance_resolver_sees_them():
    """`platform-issue-template-commands-need-the-platform-installed` cites #3418."""
    citing = {lesson["id"] for lesson in intake_receipt.lessons_citing(3418)}
    assert "platform-issue-template-commands-need-the-platform-installed" in citing, citing


def test_the_heartbeat_panel_sees_them():
    records = {Path(record["path"]).stem for record in pipeline_status.lesson_records()}
    for path in _template_named_lessons():
        assert path.stem in records, f"{path.name} is invisible to the pipeline panel"
