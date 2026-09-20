#!/usr/bin/env python3
"""The Auto-Merge Gate compared two different API spellings and could never merge (#1826).

`gh api …/pulls/N --jq '.mergeable'` reads the **REST** field, a JSON boolean: `true`, `false`, or
`null` while GitHub is still computing it. The line then compared it to `"MERGEABLE"`, which is the
**GraphQL** enum spelling. The two are never equal, so the gate skipped every PR:

    Mergeable: true
    Not mergeable. Skipping.

"All green PRs auto-merge" was therefore a branch that could not be reached — the whole history
contains no `Auto-merge #N` commit. The same mistake had already been made and fixed once in
`scripts/lesson_pr_mergeable.py`, whose docstring is the canonical explanation and whose
`mergeable_is_clean()` is the helper Python callers use. This test pins both sides so the trap cannot
be re-set in either language.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML parses the workflow")

from scripts.lesson_pr_mergeable import mergeable_is_clean  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PR_CHECKS = REPO / ".github" / "workflows" / "pr-checks.yml"


def _code(script: str) -> str:
    """Executable lines only — the comments name the constructs these tests forbid."""
    return "\n".join(line for line in script.splitlines() if not line.strip().startswith("#"))


def _gate_script() -> str:
    workflow = yaml.safe_load(PR_CHECKS.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if step.get("name") == "Auto-Merge Gate":
                return step["run"]
    raise AssertionError("the Auto-Merge Gate step disappeared — #1826 tracked it as dead, not unwanted")


def test_the_gate_reads_the_rest_boolean_not_the_graphql_enum():
    script = _gate_script()
    assert "--jq '.mergeable'" in script, "the gate reads the REST pull request, so the value is a boolean"
    code = "\n".join(line for line in script.splitlines() if not line.strip().startswith("#"))
    assert '"MERGEABLE"' not in code and "'MERGEABLE'" not in code, (
        "comparing a REST boolean to the GraphQL enum is the bug in #1826: it is always unequal, "
        "so the gate can never merge anything"
    )
    # Exactly `true` counts. `null` means GitHub has not computed it yet, and treating that as
    # mergeable would merge a conflicted PR.
    assert re.search(r'\[ "\$MERGEABLE" = "true" \]', code), "only the boolean true is mergeable"


def test_the_gates_that_must_stay_between_mergeable_and_merging_stay():
    script = _gate_script()
    code = _code(script)
    # Lesson content is executed by agents: an auto-merged attacker-authored lesson is a poisoning
    # vector (2026-08-30 security gate).
    assert "lessons/" in script, "the lessons/ human-merge gate must not be dropped"
    # Unchecked acceptance criteria mean the PR does not claim to be finished. The pattern is
    # escaped inside the shell double quotes, so match the code that greps for it.
    assert "UNCHECKED" in script and r'\[ \]' in script
    assert "gh pr merge" in script and "--auto" in script, (
        "the gate must enable GitHub's auto-merge (which waits for required checks), not merge directly"
    )
    # A conventional-looking merge subject makes release-please list the merge commit *and* the
    # branch commit it merged: every auto-merged PR showed up twice in the next release notes.
    assert "--subject" not in code, (
        "let GitHub write the default merge subject ('Merge pull request #N from …'): it is not a "
        "conventional commit, so release-please skips it instead of duplicating the changelog entry"
    )


def test_both_spellings_are_understood_by_the_python_helper_but_only_one_is_clean():
    # The helper is deliberately lenient (it accepts the enum form so a GraphQL caller cannot
    # silently disable a channel), while `null` — GitHub still computing — is never clean.
    assert mergeable_is_clean(True) is True
    assert mergeable_is_clean("MERGEABLE") is True
    assert mergeable_is_clean(False) is False
    assert mergeable_is_clean(None) is False
    assert mergeable_is_clean("UNKNOWN") is False


def test_a_release_pull_request_is_not_auto_merged():
    """The one PR a person should read before it ships.

    On 2026-09-20 this gate merged the 2.32.0 release PR while the maintainer was still reviewing its
    changelog — which held 30 duplicated entries and shipped as-is. The duplication is caught separately
    (`tests/test_changelog_shape.py`); what this asserts is that somebody gets the chance to look: a release
    PR carries the version bump and the changelog that becomes the release notes, and it is prepared by a
    bot, so nothing human has read it yet.

    Both signals are asserted because they cover different windows: release-please applies
    `autorelease: pending` to the PR it opens, and the branch name is there even before that label lands.
    """
    script = _gate_script()
    assert "autorelease:" in script, (
        "the gate does not look at the `autorelease:` label, so a release PR can be merged by a bot")
    assert "release-please--" in script, (
        "the gate does not check the branch name, so a release PR opened without the label yet can be "
        "merged by a bot")
    assert re.search(r'case "\$PR_LABELS"', script) and re.search(r'case "\$PR_BRANCH"', script), (
        "the release checks are not wired to a skip path")


def _gate_script_of(path):
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if step.get("name") == "Auto-Merge Gate":
                return step["run"]
    raise AssertionError(f"no Auto-Merge Gate step in {path}")


def test_the_release_check_notices_a_stripped_guard(tmp_path):
    """A rule that cannot fail is not a rule: strip the branch check and the assertion must notice."""
    import shutil

    scratch = tmp_path / "repo"
    (scratch / ".github" / "workflows").mkdir(parents=True)
    victim = scratch / ".github" / "workflows" / "pr-checks.yml"
    shutil.copy(PR_CHECKS, victim)
    victim.write_text(victim.read_text(encoding="utf-8").replace("release-please--", "some-branch-"),
                      encoding="utf-8")
    mutated = _gate_script_of(victim)
    assert "release-please--" not in mutated, "the mutation did not take"
    assert "autorelease:" in mutated, "the label check survived, so only the branch check is under test"
