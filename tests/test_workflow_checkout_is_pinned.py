#!/usr/bin/env python3
"""A workflow that runs on another workflow's failure must not check out that run's code.

The alert (plugin-scanner `GITHUB_ACTIONS_UNTRUSTED_CHECKOUT`, #397/#398)
------------------------------------------------------------------------
`workflow_run` and `pull_request_target` fire with the **base repository's** token and secrets, while
the run they react to may be a fork's. Checking out "whatever the triggering run used" in that
position is the classic pwn-request shape, and the scanner reports it as soon as it sees a checkout
in such a workflow — which is why `deploy-freshness.yml` was still reported after #325/#326 pinned
its ref: the heuristic does not evaluate the `ref:` expression.

Two things are true and both are needed:

1. The **code** has to be safe — an explicit ref naming the default branch, never a head ref, never
   an expression that could resolve to one.
2. The **invariant** has to be checkable here, so the safety does not rest on a scanner we cannot
   configure: this file.

The honest way to keep the alerts closed is therefore (1) plus (2), with the alert dismissed and the
reason pointing at this test — not a dismissal on its own.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"

#: Triggers that run with the base repository's privileges.
PRIVILEGED_TRIGGERS = ("workflow_run:", "pull_request_target:")

#: `ref:` expressions that name something other than the default branch. A head ref here is the
#: defect the alert is about; the two below are the ways it gets written.
UNTRUSTED_REF = re.compile(
    r"github\.(event\.pull_request|head_ref|event\.workflow_run\.head_sha|event\.workflow_run\.head_branch)")


def _workflows() -> list[tuple[str, str]]:
    return [(path.name, path.read_text(encoding="utf-8")) for path in sorted(WORKFLOWS.glob("*.yml"))]


def _privileged() -> list[tuple[str, str]]:
    out = []
    for name, text in _workflows():
        head = text.split("jobs:", 1)[0]
        if any(trigger in head for trigger in PRIVILEGED_TRIGGERS):
            out.append((name, text))
    return out


def test_every_privileged_workflow_pins_its_checkout_to_the_default_branch() -> None:
    problems = []
    for name, text in _privileged():
        for block in re.findall(r"actions/checkout@[0-9a-f]{40}[^\n]*\n(?:.*\n)*?(?=\n\s*- name:|\n\s*- uses:|\Z)",
                                text):
            ref_line = next((line for line in block.splitlines() if "ref:" in line), "")
            # No `ref:` at all is the *base* branch under both triggers — safe, and several long-lived
            # workflows rely on it. The defect is naming a ref that belongs to the run being reacted
            # to, because that is the run a fork controls.
            if ref_line and UNTRUSTED_REF.search(ref_line):
                problems.append(f"{name}: checkout ref names a run's head — {ref_line.strip()}")
    assert not problems, (
        "a privileged workflow checks out code it did not choose: " + "; ".join(problems)
        + ". Pin `ref:` to `github.event.repository.default_branch || 'main'`.")


def test_the_two_known_pinned_workflows_are_the_only_privileged_ones() -> None:
    """If a third appears, the rule above starts applying to it before anyone remembers to look."""
    names = {name for name, _ in _privileged()}
    assert names == {
        "approval-watch.yml", "auto-merge-docs.yml", "ci-lesson-search.yml", "dco-check.yml",
        "deploy-freshness.yml", "intake-bot-demo.yml", "pr-merged-thank.yml", "pr-shape-guard.yml",
        "pr-thank-you.yml", "pr-welcome.yml", "update-badges.yml",
    }, (
        f"the set of privileged workflows changed: {sorted(names)} — check each new one against the "
        "rule above, then update this list so the next reader sees the decision was made")


def test_no_tracked_file_quotes_the_dynamic_execution_api_by_name() -> None:
    """The API's name as *text* is what the scanner matches — a comment that names it recreates the
    alert.

    Both test harnesses that used to call it were rewritten (#399/#400); their explanatory comments
    still contained the name, and the alert stayed open because of the prose rather than the code.
    The rule is the one `test_scanner_secret_patterns.py` already applies to token-shaped strings:
    describe the pattern, do not quote it.
    """
    # Assembled from fragments on purpose: this file is scanned too, and a literal here would make
    # the gate report itself (the same reason `test_scanner_secret_patterns.py` splits its tokens).
    interpreter = "ev" + "al"
    patterns = (interpreter + "(", "new " + "Function(")
    offenders = []
    for path in list(REPO.glob("tests/**/*.py")) + list(REPO.glob("workers/**/*.mjs")) + list(
            REPO.glob("scripts/**/*.py")):
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            if pattern in text:
                offenders.append(f"{path.relative_to(REPO)}: {pattern!r}")
    assert not offenders, (
        "files quote the dynamic-execution API literally, which an external scanner reports as a "
        "finding regardless of how it is used: " + ", ".join(offenders))
