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

**A third round, measured 2026-09-25, showed that "do not give a merge commit a conventional subject" is not
enough advice** — because the conventional text is not only in the subject. `pr-checks.yml` had been changed
to drop `--subject`, on the reasoning that GitHub's default merge subject is not conventional. It is not:

```
Merge pull request #2047 from Ikalus1988/feat/done-but-open-detector      <- subject, not conventional
                                                                          <- blank
feat(intake): detect intakes whose work is already merged but whose ...   <- the PR *title*, in the body
```

release-please reads the whole message, so that merge commit (`a6923ea`) and the branch commit it merged
(`fd1bbca`, same files) each produced an entry — and the 2.35.0 release PR arrived with **113 entries, 103 of
them duplicates**. GitHub fills the body with the PR title by default; nothing has to be "given" to it.

The durable fix is therefore the merge *method*, not the message: **squash**, which produces one commit per
PR and no merge commit at all. `auto-merge-docs`, `auto-merge-lessons` and `scripts/ci/land_change.py`
already squashed; `pr-checks.yml` was the last path that did not, and
`test_every_merge_path_squashes` below now pins that.

This test exists because the practice is easy to get wrong silently, and because the failure is only visible
in a file nobody reads until release day: it fails when the newest release section lists the same entry twice.

Duplicates *within* one release are the signal. The same wording appearing in *different* releases is normal
(a bug fixed again after a regression is a new change).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

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


# ── the cause, pinned where it can be seen before release day ─────────────────────────────────────

# Every way a pull request reaches `main`. A merge commit is the shape that duplicates changelog entries,
# so each of these has to squash. The list is explicit rather than discovered: a *new* merge path is
# something a person should add here with a reason, not something a glob should silently include.
MERGE_PATHS = {
    ".github/workflows/pr-checks.yml": "the Auto-Merge Gate",
    ".github/workflows/auto-merge-docs.yml": "external docs PRs",
    ".github/workflows/auto-merge-lessons.yml": "lesson PRs",
}

SQUASH_OK = ("--squash", "'merge_method': 'squash'", '"merge_method": "squash"')
MERGE_COMMIT_FORMS = ("--merge ", "--merge\n", "'merge_method': 'merge'", '"merge_method": "merge"')


# An *invocation* of `gh pr merge`, not a mention of one: the workflows discuss the command in comments
# and in `echo` text ("it cannot call `gh pr merge --auto`"), and a substring search reports those as
# commands — which is how the first version of this gate failed on a file that was already correct.
MERGE_INVOCATION = re.compile(r"(?:^|[;&|]\s*|\bif\s+|\bthen\s+|\bdo\s+)gh\s+pr\s+merge\b")


def merge_commands(text: str) -> list[str]:
    """Every command in a workflow that merges a pull request, continuations joined.

    Joined because the shell form is often spread over lines, with the `--squash` on the second: a
    line-based reader concludes the flag is missing and reports a correct file as broken.
    """
    commands, pending = [], ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            continue
        pending += (" " if pending else "") + line.rstrip("\\").strip()
        if line.endswith("\\"):
            continue
        for candidate in re.split(r"[;&|]{1,2}", pending):
            candidate = candidate.strip()
            if MERGE_INVOCATION.match(candidate):
                commands.append(candidate)
        pending = ""
    return commands


@pytest.mark.parametrize("name", sorted(MERGE_PATHS))
def test_every_merge_path_squashes(name: str) -> None:
    """A merge commit puts the PR title in its body, and release-please reads it.

    This is the rule the 2.35.0 release PR paid for: 113 entries, 103 duplicates, and a required check
    (`test (ubuntu-latest, 3.11)`) that stayed red for three days on a release nobody could merge.
    """
    text = (REPO / name).read_text(encoding="utf-8")
    commands = merge_commands(text)
    assert commands, f"{name} ({MERGE_PATHS[name]}) no longer merges anything — update MERGE_PATHS"
    for command in commands:
        assert any(form in command for form in SQUASH_OK), (
            f"{name} merges without `--squash`: {command!r}. A merge commit carries the PR title in its "
            f"body, so release-please counts it *and* the branch commit it merged — that is the duplicate "
            f"this module exists to catch, and it is cheaper to prevent than to fix on release day"
        )
        for form in MERGE_COMMIT_FORMS:
            assert form not in command, f"{name} still asks for a merge commit: {command!r}"


def test_the_merge_path_rule_can_go_red() -> None:
    """Guard the guard: the exact line that caused the 2.35.0 duplicates."""
    bad = 'gh pr merge "$PR_NUM" --repo Ikalus1988/MisakaNet --merge --auto'
    assert not any(form in bad for form in SQUASH_OK)
    good = 'gh pr merge "$PR" --repo "$REPO" --squash'
    assert any(form in good for form in SQUASH_OK)


def test_the_documented_reason_is_still_the_measured_one() -> None:
    """The module docstring quotes the merge commit that doubled 103 entries.

    If someone rewrites it to the earlier, incomplete reasoning ("the default merge subject is not
    conventional"), this fails — that reasoning was already disproven once, at the cost of a stalled
    release.
    """
    # The *module docstring*, not the file text: the first version read the whole file, and the phrases
    # it looked for are in the assertions below — so it searched a string that contained itself and
    # could never fail (found by mutation, 2026-09-25).
    import ast

    source = (REPO / "tests" / "test_changelog_shape.py").read_text(encoding="utf-8")
    doc = ast.get_docstring(ast.parse(source)) or ""
    assert doc, "the module lost its docstring"
    assert "the PR *title*, in the body" in doc, "the measured mechanism left the docstring"
    assert "Merge request #2047" .replace("request", "pull request") in doc, (
        "the evidence (the merge commit whose body carried the title) left the docstring"
    )
    assert "113 entries, 103 of" in doc, "the measured cost left the docstring"


def test_the_command_reader_ignores_mentions_of_the_command() -> None:
    """Both shapes that made the first version of this gate fail on correct files."""
    comment = "          # so the `gh pr merge` at the end of this step answers"
    echo = "              echo 'secrets), so it cannot call `gh pr merge --auto`. Auto-merge is a'"
    invocation = 'gh pr merge "$PR_NUM" --repo Ikalus1988/MisakaNet --squash --auto'
    assert merge_commands(comment) == []
    assert merge_commands(echo) == []
    assert merge_commands(invocation) == [invocation]


def test_the_command_reader_joins_continuations() -> None:
    joined = merge_commands("          if gh pr merge \"$PR_NUM\" \\\n"
                            "            --repo \"$REPO\" \\\n"
                            "            --squash \\\n"
                            "            --auto; then")
    assert len(joined) == 1, joined
    assert "--squash" in joined[0] and "--auto" in joined[0]
