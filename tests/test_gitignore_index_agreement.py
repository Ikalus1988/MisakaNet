#!/usr/bin/env python3
"""A file cannot be ignored and tracked at the same time — six were (#1991).

`.gitignore` has said `misakanet/profile.json` since 2026-08, and the file was **tracked** until
2026-09-21, because gitignore does not apply to paths already in the index. The consequence is not
cosmetic: `increment_search()` rewrites that file on every successful local search, so

* every user's working tree goes dirty the first time they follow the documented command, and
* `git add -A` commits one machine's node counters — which is how this was found: repairing the local
  quota gate (#1986) let a search complete for the first time, and the commit picked up
  `search_count 15 → 22` plus a fresh `last_active`.

Five more files were in the same contradictory state, all from one over-broad pattern: `reports/`
(added for "Local audit working artifacts" at the repository root) also matched `docs/reports/`, so
five deliberately committed documents were simultaneously ignored and tracked.

`git ls-files -i -c --exclude-standard` lists exactly this contradiction, so the rule is one call —
and it is the kind of rule that has to exist, because the two halves are maintained in different
places (a pattern in `.gitignore`, an entry in the index) and nothing compares them.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SEARCH_CLI = REPO / "search_knowledge.py"
LESSONS = REPO / "data" / "lessons.json"


def tracked_but_ignored(repo: Path) -> list[str]:
    """Paths in the index that an ignore pattern also matches — the contradiction, per git itself."""
    out = subprocess.run(["git", "ls-files", "-i", "-c", "--exclude-standard"],
                         cwd=repo, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return sorted(line for line in out.stdout.splitlines() if line.strip())


def dirty_tracked_files(repo: Path) -> list[str]:
    """Tracked paths with working-tree modifications (untracked files are not this rule's business)."""
    out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                         cwd=repo, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return sorted(line[3:] for line in out.stdout.splitlines() if line.strip())


def test_nothing_in_this_repository_is_ignored_and_tracked_at_once():
    problems = tracked_but_ignored(REPO)
    assert not problems, (
        "these files are both tracked and ignored — gitignore does not apply to the index, so the "
        "pattern has no effect while the file keeps being committed:\n  " + "\n  ".join(problems))


def test_the_node_state_file_is_no_longer_tracked():
    out = subprocess.run(["git", "ls-files", "misakanet/profile.json"],
                         cwd=REPO, capture_output=True, text=True)
    assert not out.stdout.strip(), (
        "misakanet/profile.json is per-machine state (stage, referral code, counters) rewritten on "
        "every search; it must not be in the index")


def test_the_reports_pattern_still_means_what_its_comment_says():
    """Root-anchored, so local scratch stays ignored while `docs/reports/` stays tracked."""
    ignore = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert "/reports/" in ignore, "the reports pattern must be root-anchored"
    assert "\nreports/\n" not in ignore, (
        "a bare `reports/` also matches docs/reports/, which is how five tracked documents ended up "
        "ignored and tracked at the same time")


def test_the_contradiction_rule_notices_a_tracked_ignored_file(tmp_path):
    """Mutation on a scratch repository: this is the state the six files were in."""
    scratch = tmp_path / "repo"
    scratch.mkdir()
    for cmd in (["init", "-q"], ["config", "user.email", "t@example.com"],
                ["config", "user.name", "t"]):
        subprocess.run(["git", *cmd], cwd=scratch, check=True, capture_output=True)
    (scratch / ".gitignore").write_text("state.json\n", encoding="utf-8")
    (scratch / "state.json").write_text("{}\n", encoding="utf-8")
    subprocess.run(["git", "add", "-f", "state.json"], cwd=scratch, check=True, capture_output=True)
    assert tracked_but_ignored(scratch) == ["state.json"], "the rule must flag the contradiction"


@pytest.mark.skipif(not LESSONS.exists(), reason="needs data/lessons.json (the local corpus)")
def test_a_search_leaves_no_tracked_file_modified():
    """End-to-end: the documented command must not dirty the tree it runs in."""
    before = dirty_tracked_files(REPO)
    result = subprocess.run([sys.executable, str(SEARCH_CLI), "context window exceeded", "--json"],
                            cwd=REPO, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    after = dirty_tracked_files(REPO)
    assert after == before, (
        "running a search changed tracked files: "
        f"{sorted(set(after) - set(before))} — that is the state #1991 describes")
