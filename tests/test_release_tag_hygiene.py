#!/usr/bin/env python3
"""A tag that is not a release must not be readable as one.

Publishing the intake bot to GitHub Marketplace requires tagging a release, and the conventional
name for an action's first version is `v1` — which, in a repository whose Python package releases are
tagged `v2.32.1`, is a tag that every unanchored pattern reads as a release tag:

* `release-pypi.yml` triggered on `push: tags: ["v*"]`, so pushing `v1` would fire a full build plus
  an approval request on the `pypi` environment, which can only end in "this file already exists".
* `git describe --tags --abbrev=0` returns the nearest *reachable* tag, so once `v1` exists on main
  it becomes "the previous release": `gen_changelog.get_last_tag()` returned `v1`, and
  `release-pypi.yml`'s `sed 's/v//'` turned that into `--since 1` — a silently empty range.

Both were reproduced before being fixed (the tests below reproduce the mechanism, then assert the
fix). The rule they encode: a pattern that means "a release tag" must require the full `vX.Y.Z`
shape. `v[0-9]*` is *not* enough — it matches `v1` too, which is asserted here so the next person
does not "simplify" the pattern.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML reads the workflow's tag filter")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import gen_changelog  # noqa: E402  (the module under test)

RELEASE_TAGS = ["v2.32.1", "v2.33.0", "v10.0.1"]
NON_RELEASE_TAGS = ["v1", "v1.0", "action-v1"]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def tagged_repo(tmp_path: Path) -> Path:
    """Five commits; the last release `v2.32.1` is at c3 and the action tag `v1` sits at c4.

    That order is the real one: an action tag is created *after* the release it follows, so it is
    both reachable from the next release commit and nearer to it than the previous release tag.
    """
    repo = tmp_path / "tagged"
    repo.mkdir()
    _git(repo, "init", "-q", ".")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    for i in range(1, 6):
        (repo / "f.txt").write_text(f"{i}\n", encoding="utf-8")
        _git(repo, "add", "f.txt")
        _git(repo, "commit", "-qm", f"c{i}")
    _git(repo, "tag", "v2.32.1", "HEAD~2")
    _git(repo, "tag", "v1", "HEAD~1")
    return repo


def test_an_action_tag_is_not_mistaken_for_the_previous_release(tagged_repo: Path):
    # Fixture check first: if the unanchored describe did not pick the action tag, the assertion
    # below could pass for a reason that has nothing to do with the fix.
    assert _git(tagged_repo, "describe", "--tags", "--abbrev=0") == "v1"
    assert gen_changelog.get_last_tag(str(tagged_repo)) == "v2.32.1", (
        "get_last_tag must return the previous *release* tag; `v1` makes the changelog range "
        "`--since 1`, which silently yields nothing"
    )


def test_the_obvious_shorter_pattern_would_still_be_wrong(tagged_repo: Path):
    loose = _git(tagged_repo, "describe", "--tags", "--abbrev=0", "--match", "v[0-9]*")
    assert loose == "v1", (
        "`v[0-9]*` looks like a release filter and is not one — it matches `v1`. The pattern must "
        "require two dots."
    )


def test_the_pypi_workflow_ignores_tags_that_are_not_releases():
    workflow = yaml.safe_load(
        (REPO / ".github" / "workflows" / "release-pypi.yml").read_text(encoding="utf-8")
    )
    triggers = workflow.get("on") or workflow.get(True) or {}
    patterns = triggers["push"]["tags"]
    assert patterns, "the tag trigger must exist for this test to mean anything"
    for pattern in patterns:
        for tag in NON_RELEASE_TAGS:
            assert not _github_tag_matches(pattern, tag), (
                f"tag pattern {pattern!r} matches {tag!r}: pushing the action's tag would fire a "
                f"PyPI build and an approval request that cannot succeed"
            )
        for tag in RELEASE_TAGS:
            assert _github_tag_matches(pattern, tag), (
                f"tag pattern {pattern!r} must still match the release tag {tag!r}"
            )


def test_the_changelog_range_is_anchored_in_the_workflow_too():
    text = (REPO / ".github" / "workflows" / "release-pypi.yml").read_text(encoding="utf-8")
    assert re.search(r"git describe --tags --abbrev=0 --match 'v\[0-9\]\*\.", text), (
        "release-pypi.yml computes PREV_TAG with its own git describe; it needs the same "
        "release-tag pattern as gen_changelog, or `sed 's/v//'` feeds the script a non-version"
    )


def _github_tag_matches(pattern: str, tag: str) -> bool:
    """GitHub's ref-filter grammar, to the extent our patterns use it.

    `*` matches any run of characters (dots included — it is not a regex quantifier), `.` is a
    literal character, and `[...]` is a character class. Interpreting these patterns with `fnmatch`
    would be wrong in the direction that matters here: fnmatch has no `+` (GitHub does: "one or more
    of the preceding character"), so a pattern that works on GitHub could silently match a different
    set of tags in the test than in the runner.
    """
    out = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            out.append(".*")
        elif ch == "?":
            out.append(".")
        elif ch == "+":
            out.append("+")
        elif ch == "[":
            end = pattern.index("]", i)
            out.append(pattern[i:end + 1])
            i = end
        else:
            out.append(re.escape(ch))
        i += 1
    return re.fullmatch("".join(out), tag) is not None


def test_the_action_alias_follows_each_release():
    """`uses: Ikalus1988/MisakaNet@v1` must get the newest release, not the tag it was born at.

    The action IS this repository, so its `v1` alias has to move with the releases — decided
    2026-09-23: the tag has to show that the version changed. `v1` was created once at the
    intake-bot migration and would otherwise freeze the Marketplace listing at whatever `main`
    looked like that afternoon, while `@v2.34.0` (the versioned tag the same step creates) is
    what pins an exact version, for anyone who needs that.
    """
    text = (REPO / ".github" / "workflows" / "release-please.yml").read_text(encoding="utf-8")
    assert re.search(r"git tag -f v1\b", text), (
        "release-please.yml tags the release but never moves `v1`, so the action alias is "
        "frozen at the first commit it was pointed at")
    # The push is spelled `git -c http.extraheader="$AUTH_HEADER" push -f origin v1` since 2026-09-25:
    # the checkout no longer persists credentials (a PAT push alongside them is attributed to the bot and
    # the new head's runs are held), so each push names its own. The property is the same one — the alias
    # is pushed — so the rule reads the property, not the spelling.
    assert re.search(r"push\s+(-f|--force)\s+origin\s+v1\b", text), (
        "the alias is moved locally but never pushed, so consumers never see it")
    # Ordering matters in one direction only: the versioned tag has to exist before it is used
    # as the thing `v1` points at, and the release notes are generated from it.
    assert text.index('git tag "$TAG"') < text.index("git tag -f v1"), (
        "`v1` must be moved after the versioned tag for the same release exists")
