#!/usr/bin/env python3
"""A release's notes must not list the same change twice.

`release-please` builds a release's notes from the conventional commits between two tags. A merge commit
whose subject is *also* conventional therefore appears **next to** the branch commit it merged, and the entry
is duplicated. This repository has now hit that twice:

* `pr-checks.yml`'s auto-merge used to pass `gh pr merge --subject "Auto-merge #N: <title>"`, and
  "every auto-merged PR appeared twice in the next release's notes (#1820 was listed twice in the 2.31.0 PR)"
  — fixed there by dropping `--subject`, since GitHub's default merge subject is not conventional;
* on 2026-09-20 the maintainer's agent merged PRs through the API with `commit_title` set to the PR title,
  i.e. reintroduced exactly that shape: the 2.32.0 release PR arrived with **91 bullet lines covering 61
  changes — 30 duplicated**.

The fix belongs in the merge practice (do not give a merge commit a conventional subject). This test exists
because the practice is easy to get wrong silently, and because the failure is only visible in a file nobody
reads until release day: it fails when the newest release section lists the same entry twice.

Duplicates *within* one release are the signal. The same wording appearing in *different* releases is normal
(a bug fixed again after a regression is a new change).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHANGELOG = REPO / "CHANGELOG.md"

# `* **scope:** subject ([#123](…)) ([abc1234](…))` — the trailing reference groups are what differ
# between the two copies of one change, so they are stripped before comparing. Peeled one group at a time
# (allowing a single nesting level, which is what a linked issue inside a reference group looks like) rather
# than matched with one clever pattern: the first version of this left a trailing `))` behind.
_TRAILING_GROUP = re.compile(r"\s*\((?:[^()]|\([^()]*\))*\)\s*$")


def _normalise(entry: str) -> str:
    text = entry.strip()
    while True:
        peeled = _TRAILING_GROUP.sub("", text)
        if peeled == text:
            return text
        text = peeled


def newest_section(text: str) -> str:
    """The most recent release block of a changelog (up to the next `## ` heading)."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("## ")), None)
    if start is None:
        return ""
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def duplicate_entries(section: str) -> list[str]:
    seen: dict[str, int] = {}
    for line in section.splitlines():
        if not line.strip().startswith("* "):
            continue
        seen[_normalise(line)] = seen.get(_normalise(line), 0) + 1
    return sorted(entry for entry, count in seen.items() if count > 1)


def test_the_newest_release_section_has_no_duplicate_entries():
    duplicates = duplicate_entries(newest_section(CHANGELOG.read_text(encoding="utf-8")))
    assert not duplicates, (
        "the newest release lists these changes more than once, which means a merge commit carried a "
        "conventional subject next to the branch commit it merged (see this module's docstring). Fix the "
        "changelog before releasing, and merge with a non-conventional subject — GitHub's default "
        "`Merge pull request #N from <branch>` is what `pr-checks.yml` uses for exactly this reason:\n  - "
        + "\n  - ".join(duplicates))


def test_the_rule_notices_a_duplicate(tmp_path):
    """Guard the guard: the 2.32.0 release PR is the fixture this rule was written against."""
    section = """## [2.0.0](https://example/compare/v1.0.0...v2.0.0) (2026-01-01)


### Features

* **lesson:** a change ([#1](https://x/1)) ([aaaaaaa](https://x/a))
* **lesson:** a change ([#1](https://x/1)) ([bbbbbbb](https://x/b))
* **site:** another change ([ccccccc](https://x/c))
"""
    assert duplicate_entries(section) == ["* **lesson:** a change"], duplicate_entries(section)

    # ...and it must not fire on the same wording in two different releases.
    two_releases = """## [2.0.0](x) (2026-01-01)

* **lesson:** a change ([aaaaaaa](x))

## [1.0.0](x) (2025-12-01)

* **lesson:** a change ([zzzzzzz](x))
"""
    assert duplicate_entries(newest_section(two_releases)) == []


def test_the_helper_reads_a_real_section():
    """A rule that returns an empty string for the real file would pass forever."""
    section = newest_section(CHANGELOG.read_text(encoding="utf-8"))
    assert section.startswith("## "), "no release section found in CHANGELOG.md"
    assert any(line.strip().startswith("* ") for line in section.splitlines()), (
        "the newest release section has no entries at all, so the duplicate rule has nothing to read")
    assert len(section) > 200
