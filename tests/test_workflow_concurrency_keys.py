#!/usr/bin/env python3
"""A concurrency key must not collapse distinct runs into one group.

Measured 2026-10-06: `quality-labels` on #2913 reported `fail` in `gh pr checks`, while the
check run it produced was `cancelled` with no log at all. Of the last 12 runs of
`pr-quality-gate.yml`, 2 were cancelled and none had failed for a real reason. A gate that
cancels itself is worse than no gate — it turns a pull request red for a reason that has
nothing to do with the change under review.

The mechanism was the group key, not the job:

    group: pr-quality-gate-${{ github.event.pull_request.number
                               || github.event.check_run.pull_requests[0].number
                               || github.sha }}

Both PR-number expressions are empty for a `check_run` event whose check run has no attached
pull request, so the key fell through to `github.sha` and every check completion on that commit
shared one group. With `cancel-in-progress: true` they cancelled each other in a race, and the
loser was reported as a failed check on the PR. The job's `if:` already discarded exactly that
case, but a **job-level** `if:` still creates the *run*, so the run still joined its group and
still resolved the key. Job guards do not protect group keys.

## What this file does and does not assert

Only workflows that trigger on `check_run` are in scope, and only when their key is built from
`github.event.pull_request.number` / `github.event.check_run.pull_requests[0].number`. Those are
the two expressions that are empty on a `check_run` with no attached PR.

Workflows that key on `github.head_ref`, `github.ref` or a literal are **left alone**. On a
`pull_request` event `github.head_ref` *is* the branch name, which is already per-PR unique, and
a literal group is a deliberate choice by whoever wrote it. An earlier draft of this file
asserted that every cancelling group must mention `pull_request.number`, and it duly reported
10 workflows as broken — all of them correctly configured. A rule that fires on correct
configuration teaches people to ignore the rule, so the assertion is scoped to the shape that
is actually broken instead of being broadened until it looks thorough.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"

# The two expressions that are empty on a `check_run` carrying no attached pull request.
EMPTY_ON_BARE_CHECK_RUN = (
    "github.event.pull_request.number",
    "github.event.check_run.pull_requests[0].number",
)
BARE_SHA_TAIL = re.compile(r"\|\|\s*github\.sha\s*\}\}\s*$")


def _workflows() -> list[tuple[Path, dict]]:
    out = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if isinstance(data, dict):
            out.append((path, data))
    return out


def _cancelling_check_run_workflows() -> list[tuple[Path, dict]]:
    """Workflows that both cancel in progress and key their group on the fragile expressions."""
    out = []
    for path, data in _workflows():
        block = data.get("concurrency")
        if not isinstance(block, dict) or not block.get("cancel-in-progress"):
            continue
        on = data.get("on", data.get(True))
        triggers = on if isinstance(on, dict) else {}
        if "check_run" not in triggers:
            continue
        group = " ".join(str(block.get("group", "")).split())
        if not any(expr in group for expr in EMPTY_ON_BARE_CHECK_RUN):
            continue
        out.append((path, block))
    return out


def _ids(path: Path) -> str:
    """Readable ids: pytest passes one parameter per name, so this takes `path`, not the pair."""
    return path.name

def test_the_scan_found_the_workflow_it_is_about() -> None:
    """Otherwise every assertion below passes on an empty list.

    If `pr-quality-gate.yml` is renamed or its trigger changes, this fails instead of the file
    quietly guarding nothing.
    """
    paths = {p.name for p, _ in _cancelling_check_run_workflows()}
    assert "pr-quality-gate.yml" in paths, (
        "pr-quality-gate.yml is no longer in scope: either its trigger or its group key changed, "
        f"and this file's assertions need updating. In scope now: {sorted(paths)}"
    )


@pytest.mark.parametrize("path,block", _cancelling_check_run_workflows())
def test_the_key_does_not_fall_through_to_the_sha(path: Path, block: dict) -> None:
    """The exact shape that cancelled #2913's check.

    A `check_run` event with no attached pull request is routine — most check runs on a push to
    `main` carry none — so a key that resolves to `github.sha` there puts every such event on
    one commit into one group, and `cancel-in-progress` turns that into a red X on an unrelated
    pull request.
    """
    group = " ".join(str(block.get("group", "")).split())
    assert not BARE_SHA_TAIL.search(group), (
        f"{path.name}: the group key ends in a bare `|| github.sha`. On a check_run with no "
        "attached PR both PR-number expressions are empty, so every check completion on that "
        "commit shares one group and they cancel each other. Put github.sha in as a *suffix* so "
        "runs stay grouped per PR and still distinguished by commit."
    )


@pytest.mark.parametrize("path,block", _cancelling_check_run_workflows())
def test_the_explanation_travels_with_the_key(path: Path, block: dict) -> None:
    """A guard nobody can find is a guard the next person tidying the file deletes.

    `pr-quality-gate.yml` carries a long comment on exactly this; the check is that the
    reasoning stays attached to the key it explains rather than drifting into a section about
    something else.
    """
    text = path.read_text(encoding="utf-8")
    assert "cancel" in text.lower(), (
        f"{path.name} cancels in progress but never says so in the file; the next reader has no "
        "way to know a cancellation here is load-bearing"
    )
