"""Panel 5: who is contributing — the row the digest never had.

The digest measures lessons daily and contributors never, so "activity" came to mean "commits", and
in this repository 396 of 408 commits in 90 days are one person's. Measured 2026-11-23 over the last
1200 pull requests: 107 external, 24 merged, 80 closed, and 75% of the merges came from one author.

These tests pin the classification, because the classification is the whole panel: counting the
maintainer's own PRs as external would report a healthy funnel that does not exist, and counting bots
would report a contributor base made of Dependabot.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import heartbeat_report as hr  # noqa: E402


def pr(login: str, state: str, created: str = "2026-11-10T00:00:00Z",
       merged: str | None = None, closed: str | None = None, labels: list[str] | None = None) -> dict:
    return {"number": 0, "author": {"login": login}, "state": state,
            "createdAt": created, "mergedAt": merged, "closedAt": closed,
            "labels": [{"name": name} for name in (labels or [])]}


def test_the_maintainers_own_prs_are_not_the_external_funnel():
    prs = [pr("Ikalus1988", "MERGED", merged="2026-11-10T06:00:00Z"),
           pr("zsxh1990", "MERGED", merged="2026-11-10T06:00:00Z")]
    stats = hr.contribution_stats(prs, "2026-11-23")
    assert stats["external"] == 1, stats
    assert stats["merged"] == 1


def test_bots_are_not_contributors():
    prs = [pr("app/dependabot", "MERGED", merged="2026-11-10T06:00:00Z"),
           pr("dependabot[bot]", "MERGED", merged="2026-11-10T06:00:00Z"),
           pr("some-bot[bot]", "CLOSED", closed="2026-11-10T06:00:00Z")]
    stats = hr.contribution_stats(prs, "2026-11-23")
    assert stats["external"] == 0
    assert stats["merged"] == 0 and stats["closed"] == 0


def test_the_outcomes_and_the_concentration_are_counted():
    prs = [
        pr("a", "MERGED", merged="2026-11-10T06:00:00Z"),
        pr("a", "MERGED", merged="2026-11-11T12:00:00Z"),
        pr("b", "MERGED", merged="2026-11-12T00:00:00Z"),
        pr("c", "CLOSED", closed="2026-11-12T03:00:00Z"),
        pr("d", "OPEN"),
    ]
    stats = hr.contribution_stats(prs, "2026-11-23")
    assert (stats["external"], stats["merged"], stats["closed"], stats["open"]) == (5, 3, 1, 1)
    assert stats["authors"] == 4
    assert stats["top_author"] == "a"
    assert stats["merge_share_top"] == 67, "two of three merges from one author"
    # 6h, 36h and 48h after opening; the middle value is the median.
    assert stats["median_hours_to_merge"] == 36.0


def test_the_signoff_share_is_counted_on_closed_prs_only():
    prs = [pr("a", "CLOSED", closed="2026-11-12T03:00:00Z", labels=["needs-dco"]),
           pr("b", "CLOSED", closed="2026-11-12T03:00:00Z"),
           pr("c", "MERGED", merged="2026-11-12T03:00:00Z", labels=["needs-dco"])]
    stats = hr.contribution_stats(prs, "2026-11-23")
    assert stats["closed_with_needs_dco"] == 1, "a merged PR carrying the label is not a close"


def test_the_window_excludes_older_prs():
    prs = [pr("a", "CLOSED", created="2026-09-01T00:00:00Z", closed="2026-09-02T00:00:00Z"),
           pr("b", "MERGED", created="2026-11-20T00:00:00Z", merged="2026-11-20T06:00:00Z")]
    stats = hr.contribution_stats(prs, "2026-11-23")
    assert stats["external"] == 1 and stats["merged"] == 1


def test_an_unreadable_source_is_not_a_quiet_month():
    lines = "\n".join(hr.panel_contribution(None, "gh: not authenticated", "2026-11-23"))
    assert "Could not be read" in lines
    assert "not a quiet month" in lines


def test_the_signoff_sentence_appears_only_when_it_is_true():
    half = [pr("a", "CLOSED", closed="2026-11-12T03:00:00Z", labels=["needs-dco"]),
            pr("b", "CLOSED", closed="2026-11-12T03:00:00Z"),
            pr("c", "MERGED", merged="2026-11-13T03:00:00Z")]
    assert "/fix-dco" in "\n".join(hr.panel_contribution(half, "", "2026-11-23"))
    fine = [pr("a", "CLOSED", closed="2026-11-12T03:00:00Z"),
            pr("b", "MERGED", merged="2026-11-13T03:00:00Z"),
            pr("c", "MERGED", merged="2026-11-13T03:00:00Z")]
    assert "/fix-dco" not in "\n".join(hr.panel_contribution(fine, "", "2026-11-23"))


def test_the_panel_is_reachable_from_the_digest():
    digest = hr.render_digest(
        day="2026-11-23", counters=None, analytics=None, funnel=None,
        prs=[pr("a", "MERGED", merged="2026-11-13T03:00:00Z")])
    assert "## 5 · Who is contributing" in digest
    assert "external PRs" in digest
