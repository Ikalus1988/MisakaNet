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

import hashlib
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


def tracked_content(repo: Path) -> dict[str, str]:
    """Hash of every tracked file's *content* in the working tree.

    Paths are not enough, and this is the difference between the rule working and not: `profile.json`
    was rewritten on every search while it was tracked, so on any checkout that had ever searched the
    file was **already dirty** and a "did the set of dirty paths change?" comparison answers no. The
    first version of this test could only fail from a pristine clone — which is not the state of the
    machine that reported #1991.
    """
    out = subprocess.run(["git", "ls-files", "-z"], cwd=repo, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    digests = {}
    for name in out.stdout.split("\0"):
        if not name:
            continue
        path = repo / name
        if not path.is_file():
            continue
        digests[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


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
    before = tracked_content(REPO)
    result = subprocess.run([sys.executable, str(SEARCH_CLI), "context window exceeded", "--json"],
                            cwd=REPO, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    after = tracked_content(REPO)
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    assert not changed, (
        f"running a search rewrote tracked files: {changed} — that is the state #1991 describes "
        "(and the state this test could not see when it compared path sets)")


def case_insensitive_shadows(repo: Path = REPO) -> list[tuple[str, str]]:
    """Ignore rules that match a tracked file *only* because case is ignored.

    `git ls-files -i -c` answers the local filesystem's question, so on Linux (case-sensitive)
    a bare `STATUS.md` rule looked harmless while macOS and Windows — where matching is
    case-insensitive — reported `docs/integrations/status.md` as tracked-and-ignored. That is
    how #1991's defect came back in a new shape and stayed invisible for days: the check ran
    only on the platform where it cannot fail.

    This walks the rules ourselves, comparing case-insensitively against the case-sensitive
    result, so the answer no longer depends on the host filesystem. Reproduce the real thing
    with `git -c core.ignorecase=true ls-files -i -c --exclude-standard`.
    """
    import fnmatch

    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=repo, capture_output=True, text=True)
    assert tracked.returncode == 0, tracked.stderr
    names = [n for n in tracked.stdout.split("\0") if n]

    findings: list[tuple[str, str]] = []
    for ignore_file in sorted(repo.rglob(".gitignore")):
        if ".git" in ignore_file.parts:
            continue
        # A nested .gitignore's patterns are relative to that directory.
        base = ignore_file.parent.relative_to(repo).as_posix()
        for raw in ignore_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("!"):
                continue
            pattern = line.rstrip("/")
            anchored = pattern.startswith("/")
            pattern = pattern.lstrip("/")
            for name in names:
                rel = name[len(base) + 1:] if base not in (".", "") and name.startswith(f"{base}/") else name
                if base not in (".", "") and not name.startswith(f"{base}/"):
                    continue
                # No slash in the pattern (git's rule): it matches the basename at any depth.
                subject = rel.rsplit("/", 1)[-1] if (not anchored and "/" not in pattern) else rel
                if fnmatch.fnmatch(subject.lower(), pattern.lower()) and not fnmatch.fnmatch(subject, pattern):
                    findings.append((line, name))
    return findings


def test_no_ignore_rule_shadows_a_tracked_file_only_through_case():
    """The platform-independent half of #1991 — a Linux-only suite must still catch this."""
    findings = case_insensitive_shadows(REPO)
    assert not findings, (
        "these ignore rules match a tracked file only because matching is case-insensitive, so "
        "they hide it on macOS/Windows while Linux sees nothing:\n  "
        + "\n  ".join(f"{rule!r} shadows {name}" for rule, name in findings)
        + "\nAnchor the rule to the root (/NAME) so it stops matching nested paths."
    )
