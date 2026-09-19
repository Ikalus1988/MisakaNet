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
    # Lesson content is executed by agents: an auto-merged attacker-authored lesson is a poisoning
    # vector (2026-08-30 security gate).
    assert "lessons/" in script, "the lessons/ human-merge gate must not be dropped"
    # Unchecked acceptance criteria mean the PR does not claim to be finished. The pattern is
    # escaped inside the shell double quotes, so match the code that greps for it.
    assert "UNCHECKED" in script and r'\[ \]' in script
    assert "gh pr merge" in script and "--auto" in script, (
        "the gate must enable GitHub's auto-merge (which waits for required checks), not merge directly"
    )


def test_both_spellings_are_understood_by_the_python_helper_but_only_one_is_clean():
    # The helper is deliberately lenient (it accepts the enum form so a GraphQL caller cannot
    # silently disable a channel), while `null` — GitHub still computing — is never clean.
    assert mergeable_is_clean(True) is True
    assert mergeable_is_clean("MERGEABLE") is True
    assert mergeable_is_clean(False) is False
    assert mergeable_is_clean(None) is False
    assert mergeable_is_clean("UNKNOWN") is False
