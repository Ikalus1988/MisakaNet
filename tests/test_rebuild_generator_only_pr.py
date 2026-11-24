"""The rebuild decision for a contributor's conflicting pull request.

The decision is the part that has failed in automation before (a closure rule that shut ten strangers'
issues came from deciding on the wrong attribute), so it is a pure function here and the CLI defaults
to saying what it would do.

Measured 2026-11-23: of the last 1200 pull requests, 107 were external and only 24 merged; two of the
three open external PRs were stuck on conflicts **entirely in generator-owned files**, which is the one
repair the repository tells maintainers not to do by hand.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.ci.rebuild_generator_only_pr import is_hand_written, plan  # noqa: E402


def test_a_conflict_only_in_generated_paths_is_rebuildable():
    result = plan(
        conflicted=["data/lessons.json", "docs/_redirects", "docs/.generated-pages.json"],
        changed=["data/lessons.json", "docs/_redirects", "lessons/contrib/new-lesson.md"],
    )
    assert result["action"] == "rebuild", result
    assert result["keep"] == ["lessons/contrib/new-lesson.md"]


def test_one_hand_written_conflict_stops_it():
    """A bot must never choose between two versions of a line a human typed."""
    result = plan(
        conflicted=["data/lessons.json", "scripts/lesson_gate.py"],
        changed=["data/lessons.json", "scripts/lesson_gate.py", "lessons/contrib/x.md"],
    )
    assert result["action"] == "leave"
    assert "scripts/lesson_gate.py" in result["reason"]


def test_no_conflict_is_not_a_rebuild():
    assert plan([], ["lessons/contrib/x.md"])["action"] == "leave"


def test_a_pr_with_nothing_hand_written_has_nothing_to_carry():
    """All-generated changes are the automation's own output; replaying it would duplicate work."""
    result = plan(conflicted=["data/lessons.json"],
                  changed=["data/lessons.json", "docs/data/lessons.json"])
    assert result["action"] == "leave"
    assert "nothing hand-written" in result["reason"]


def test_the_generated_allowlist_is_read_from_the_one_authority():
    """`check_dist_diff` owns the list of generator-owned paths; a second copy would drift."""
    assert is_hand_written("data/lessons.json") is False
    assert is_hand_written("docs/topics/index.html") is False
    assert is_hand_written("lessons/index.md") is False, "the index is generated too"
    assert is_hand_written("lessons/contrib/example.md") is True
    assert is_hand_written("docs/maintainer/backoff.md") is True


def test_an_unknown_path_counts_as_hand_written():
    """Conservative on purpose: an unknown file can only block a rebuild, never be discarded by one."""
    assert is_hand_written("somewhere/unheard-of.xyz") is True


def test_the_plan_names_what_it_would_regenerate():
    result = plan(conflicted=["data/lessons.json"],
                  changed=["data/lessons.json", "docs/sitemap.xml", "lessons/contrib/a.md"])
    assert result["regenerate"] == ["data/lessons.json", "docs/sitemap.xml"]
