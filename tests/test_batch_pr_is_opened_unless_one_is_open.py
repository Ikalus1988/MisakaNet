#!/usr/bin/env python3
"""The batch may not mistake a merged pull request for an open one.

`gh pr view <branch>` answers for **any** pull request from that branch, merged or not. The batch
workflow used it as "is one already open?" — measured 2026-11-21: the 00:46 batch merged, a 01:31
re-dispatch rebuilt the branch with **12 new lessons**, force-pushed, read the merged PR back as
"already open", and exited **0**. Green run; lessons on a branch nobody would merge; intakes left open.

The fix is one flag (`--state open`), and this file keeps it there: the failure is invisible in every
signal except "the queue did not shrink", which is the signal nobody watches.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "intake-batch-convert.yml"


def _step_script(name_fragment: str) -> str:
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in document["jobs"].values():
        for step in job.get("steps") or []:
            if name_fragment in (step.get("name") or ""):
                return step.get("run") or ""
    raise AssertionError(f"no step whose name contains {name_fragment!r}")


def _code(name_fragment: str) -> str:
    """The step's shell with its comments removed: a comment may *name* the call it explains."""
    return chr(10).join(line.split("#", 1)[0]
                        for line in _step_script(name_fragment).splitlines())


def test_the_open_question_is_asked_about_open_pull_requests_only():
    script = _code("Open the batch pull request")
    assert "gh pr list --head \"$BRANCH\" --state open" in script, (
        "the batch must ask for an *open* pull request; `gh pr view $BRANCH` also answers for a merged one"
    )
    assert "gh pr view \"$BRANCH\"" not in script


def test_a_merged_branch_can_still_open_a_new_pull_request():
    """The branch is force-pushed with new commits, so "no open PR" must fall through to `gh pr create`."""
    script = _code("Open the batch pull request")
    assert 'if [ -n "$open_pr" ]' in script
    assert "gh pr create --base main --head \"$BRANCH\"" in script
