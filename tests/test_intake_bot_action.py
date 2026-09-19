#!/usr/bin/env python3
"""The intake bot's failure mode: it ran 21,732 times and posted nothing (#1825).

`intake-bot-demo.yml` exists to answer "your CI failed — someone has hit this before, here is how
they fixed it". It never posted a single comment. Two independent defects, both of which turn a real
result into silence:

1. `ARGS="--json --source $X …"` was expanded **unquoted** into `python3 $SCRIPT $ARGS`. `--error`
   carries a multi-line excerpt of the failing job's log, so word splitting handed argparse
   `--error` plus a pile of unrecognised positionals → exit 2 → and `2>/dev/null ||` replaced the
   reason with `{"decision":"error","reason":"script failed"}`. The comment step skips unknown
   decisions, the step exited 0, and the run went **green**.
2. When `workflow_run.pull_requests` was empty (a run GitHub does not associate with a PR), the
   comment step logged at `info` and returned — nothing posted, nothing wrong-looking.

These are structural assertions about the action's shell and script, because the defects are exactly
structural: the value is passed either as one argv element or as many, and a failure is either
reported or swallowed. A behavioural test of the YAML would mean running Actions.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML parses the composite action")

REPO = Path(__file__).resolve().parent.parent
ACTION = REPO / ".github" / "actions" / "misaka-intake-bot" / "action.yml"
WORKFLOW = REPO / ".github" / "workflows" / "intake-bot-demo.yml"


def _action() -> dict:
    return yaml.safe_load(ACTION.read_text(encoding="utf-8"))


def _step(step_id: str) -> dict:
    for step in _action()["runs"]["steps"]:
        if step.get("id") == step_id:
            return step
    raise AssertionError(f"no step with id={step_id!r} in {ACTION.name}")


def _code(script: str) -> str:
    """The executable lines only.

    The comments in this action deliberately *name* the constructs that caused #1825 (`$ARGS`,
    `2>/dev/null`), so the negative assertions have to look at code, not at prose — the first
    version of this test failed on its own documentation.
    """
    return "\n".join(line for line in script.splitlines() if not line.strip().startswith("#"))


def test_error_text_is_passed_as_one_argument_not_many():
    script = _step("intake")["run"]
    assert 'python3 "$SCRIPT" "${ARGS[@]}"' in script, (
        "the bot must be invoked with the array form; `python3 $SCRIPT $ARGS` word-splits the "
        "multi-line --error excerpt into dozens of argv entries and argparse exits 2"
    )
    # The specific shape of the old bug, so a re-introduction is named rather than inferred.
    assert "$SCRIPT $ARGS" not in _code(script)
    assert 'ARGS="' not in _code(script), "ARGS must be a bash array, not a string"
    # Every value that can contain whitespace is quoted at the point it enters the array.
    for value in ('"$INPUT_SOURCE"', '"$INPUT_SIM"', '"$INPUT_WHAT_TRIED"', '"$INPUT_ERROR"',
                  '"$INPUT_LOG_FILE"'):
        assert value in script, f"{value} must be quoted"


def test_a_failed_bot_reports_why_and_does_not_look_like_a_clean_run():
    script = _step("intake")["run"]
    code = _code(script)
    assert "2>/dev/null" not in code, "discarding stderr is what hid this failure for a month"
    assert "RC=$?" in code, "the exit code must be captured, not replaced by a generic object"
    assert "intake bot exited" in code, "the reason must name the exit code"
    # And the step itself goes red: `decision=error` used to exit 0 with a green run.
    assert 'if [ "$DECISION" = "error" ]' in code
    assert "exit 1" in code


def test_the_comment_path_is_reachable_and_says_when_it_is_not():
    script = next(
        step for step in _action()["runs"]["steps"] if step.get("name") == "Comment on PR"
    )["with"]["script"]
    assert "skip unknown decisions" not in script, (
        "an unmatched decision must warn; returning silently is indistinguishable from "
        "'the bot had nothing to say'"
    )
    assert "core.warning" in script
    # Empty `pull_requests` is a real case, not a reason to give up: resolve the PR by head branch.
    assert "head_branch" in script and "pulls.list" in script
    # An explicit PR number makes the path testable by hand (a dispatch has no associated run).
    assert "INPUT_PR_NUMBER" in script


def test_pr_number_is_declared_and_wired_through_the_demo_workflow():
    action = _action()
    assert "pr-number" in action["inputs"], "the input must be declared to be settable"
    step = _step("intake")
    assert step["env"]["INPUT_PR_NUMBER"] == "${{ inputs.pr-number }}", (
        "the env mapping is what reaches the shell; a declared-but-unmapped input is the same "
        "class of bug as `source-ref` (which the shell could never read as INPUT_SOURCE_REF)"
    )
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # `on` is parsed as the boolean True key by YAML 1.1 — read it either way.
    triggers = workflow.get("on") or workflow.get(True) or {}
    dispatch_inputs = triggers["workflow_dispatch"]["inputs"]
    assert "pr-number" in dispatch_inputs, "a manual test needs a way to name the PR"
    called = workflow["jobs"]["intake-demo"]["steps"][-1]["with"]
    assert called["pr-number"] == "${{ inputs.pr-number || '' }}"
