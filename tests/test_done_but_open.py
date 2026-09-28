#!/usr/bin/env python3
"""`done_but_open` must find the intakes that are done, and must not invent any (#2040).

The rule it exists to enforce is the one that was broken seven times on 2026-09-21: work merged,
issue left open, reporter told nothing. A report that lists *everything* is as useless as one that
lists nothing, so the false-positive direction is tested as hard as the true-positive one.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.done_but_open import _age_days, findings, render  # noqa: E402


def _lesson(tmp_path: Path, name: str, frontmatter: str, body: str = "## Problem\n\nx\n") -> None:
    (tmp_path / name).write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")


def test_an_intake_with_a_merged_lesson_is_reported(tmp_path):
    _lesson(tmp_path, "a.md", 'title: t\ndomain: devops\nstatus: published\nevidence_level: E1\nsource: "intake-7777"\n')
    report = findings([{"number": 7777, "title": "the reported gap", "created_at": ""}], tmp_path)
    assert [r["intake"] for r in report] == [7777]
    assert report[0]["lessons"] == ["a.md"]
    assert report[0]["evidence_levels"] == ["E1"]


def test_an_intake_that_is_only_mentioned_is_not_reported(tmp_path):
    """A number in a lesson body is not a citation — otherwise the report is noise."""
    _lesson(tmp_path, "b.md", "title: t\ndomain: devops\nstatus: published\nevidence_level: E1\nsource: \"elsewhere\"\n",
            body="## Problem\n\nthis resembles #8888 but is a different failure.\n")
    assert findings([{"number": 8888, "title": "", "created_at": ""}], tmp_path) == []


def test_the_canonical_and_free_text_forms_both_resolve(tmp_path):
    _lesson(tmp_path, "c.md", 'title: t\ndomain: devops\nstatus: published\nevidence_level: E2\nsource: "intake #1234 — described in prose"\n')
    _lesson(tmp_path, "d.md", 'title: u\ndomain: devops\nstatus: published\nevidence_level: E3\nprovenance:\n  issue: "#5678"\n')
    got = findings([{"number": 1234, "title": "", "created_at": ""},
                    {"number": 5678, "title": "", "created_at": ""}], tmp_path)
    assert sorted(r["intake"] for r in got) == [1234, 5678]


def test_age_is_computed_and_missing_dates_do_not_crash(tmp_path):
    assert _age_days("2026-09-01T00:00:00Z") is not None
    assert _age_days("") is None
    assert _age_days("not a date") is None
    report = findings([{"number": 1, "title": "t", "created_at": ""}], tmp_path)
    assert report == []  # no lesson citing it; the point is that it did not raise


def test_an_empty_report_says_so_instead_of_looking_reassuring():
    text = render([])
    assert "没有发现" in text
    assert "请确认" in text, "an always-empty check and an always-green check are equally suspect"


def test_the_report_names_the_lesson_and_the_age():
    text = render([{"intake": 1472, "title": "t", "age_days": 17,
                    "lessons": ["lessons/contrib/vertex-gemini-model-id-naming.md"], "evidence_levels": ["E3"]}])
    assert "#1472" in text and "17" in text
    assert "vertex-gemini-model-id-naming.md" in text
    assert "回执" in text, "the report must say what to do, not only what it found"


def test_it_finds_a_real_one_in_the_real_corpus():
    """Against the live corpus, an intake whose lesson exists must be reported.

    #1472's lesson is on main and cites it, so this is the true-positive direction against real data
    rather than a fixture — the failure mode being guarded (finding nothing) looks identical to
    "everything is fine".
    """
    report = findings([{"number": 1472, "title": "", "created_at": ""}])
    assert [r["intake"] for r in report] == [1472], (
        "the resolver found no lesson for a real intake that has one — check lessons/ is readable"
    )
