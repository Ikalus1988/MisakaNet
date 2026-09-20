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
# The action moved to the repository root so GitHub Marketplace can publish it (`@v1` references
# only ever resolve a root action.yml). The assertions below are about behaviour, not location, but
# the location is part of the public contract now: see test_action_is_publishable_at_the_repo_root.
ACTION = REPO / "action.yml"
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


# ── the Marketplace contract ───────────────────────────────────────────────────────────────────
# An `owner/repo@ref` reference publishes and runs exactly one file: the action.yml at the
# repository root. The bot lived in .github/actions/misaka-intake-bot/ from 2026-09-06, which means
# every "reuse this action in your repo" instruction in this repository named a path that only
# works with a MisakaNet checkout — the one thing an external caller does not have. These tests hold
# the entry point still, because the failure mode is a *successful* CI run in a repository that
# believed it had installed the bot.


def test_action_is_publishable_at_the_repo_root():
    action = _action()
    assert (REPO / "action.yml").exists(), (
        "the action must be at the repository root: `Ikalus1988/MisakaNet@v1` cannot reach "
        ".github/actions/<name>, so a subdirectory action is unreachable for external callers"
    )
    assert not (REPO / ".github" / "actions" / "misaka-intake-bot").exists(), (
        "the old path must be gone, not shadowed: a stale copy would keep the demo green while "
        "external callers ran something else"
    )
    # What GitHub validates before it will publish an action to Marketplace.
    assert action["name"] and len(action["name"]) <= 100
    assert action["description"], "Marketplace shows the description; it is required"
    assert len(action["description"]) <= 125, (
        "Marketplace rejects a longer description — and the failure is at release time, in the UI, "
        "long after CI went green"
    )
    assert action["branding"]["icon"] and action["branding"]["color"], (
        "branding drives the Marketplace card and the icon shown next to the action in a workflow"
    )
    assert action["runs"]["using"] == "composite"
    assert action["inputs"] and action["outputs"], (
        "inputs/outputs are what the Marketplace listing documents; an action with neither is "
        "usually a `runs.using: docker` stub"
    )


def test_the_dogfood_workflow_calls_the_entry_point_external_users_get():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    uses = [s["uses"] for s in workflow["jobs"]["intake-demo"]["steps"] if "uses" in s]
    assert "./" in uses, (
        "the demo must call the root action (`uses: ./`) — the same file an external caller gets as "
        "@v1. Exercising a second path is how a broken public entry point stays green here"
    )
    assert not [u for u in uses if "misaka-intake-bot" in u], (
        "no workflow may still reference the removed subdirectory path"
    )


def test_every_local_uses_reference_resolves_to_an_action_that_exists():
    """`uses: ./x` is only checked at run time by the runner, not by any linter here."""
    problems = []
    for path in sorted((REPO / ".github" / "workflows").glob("*.y*ml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        text = path.read_text(encoding="utf-8")
        for job in (workflow.get("jobs") or {}).values():
            if not isinstance(job, dict):
                continue
            for step in job.get("steps") or []:
                uses = (step or {}).get("uses") if isinstance(step, dict) else None
                if not isinstance(uses, str) or not uses.startswith("./"):
                    continue
                target = REPO / uses[2:]
                if not (target / "action.yml").exists() and not (target / "action.yaml").exists() \
                        and not (target.is_file() and target.name.startswith("action.")):
                    problems.append(f"{path.name}: uses: {uses} → no action.yml")
        # A YAML-only check misses nothing here, but `text` keeps the intent explicit: the reference
        # must be a literal, because composite `uses:` does not expand expressions.
        assert "${{" not in " ".join(
            l for l in text.splitlines() if l.strip().startswith("- uses: ./")
        ), "local `uses:` paths cannot be expressions"
    assert not problems, "; ".join(problems)


def test_the_script_is_found_without_reaching_the_network():
    code = _code(_step("intake")["run"])
    action_path_candidate = '${GITHUB_ACTION_PATH:+$GITHUB_ACTION_PATH/scripts/intake_bot.py}'
    assert action_path_candidate in code, (
        "the action now ships scripts/ with itself (root action = whole repo on the runner), so it "
        "must look there: an external caller gets the pinned ref's script with no fetch and no "
        "version skew between the action and the script it runs"
    )
    assert code.index("GITHUB_ACTION_PATH") < code.index("curl "), (
        "the network fetch is a fallback and must come after the local candidates"
    )
    assert (REPO / "scripts" / "intake_bot.py").exists()
    assert (REPO / "scripts" / "sample_report.py").exists(), (
        "sample_report.py moved next to it; ${GITHUB_ACTION_PATH}/scripts/sample_report.py is how "
        "the action invokes it"
    )
    assert "${GITHUB_ACTION_PATH:-.}/scripts/sample_report.py" in code


def test_the_how_to_doc_names_the_reference_external_users_can_actually_use():
    doc = (REPO / "docs" / "agents" / "external-usage.md").read_text(encoding="utf-8")
    assert "Ikalus1988/MisakaNet@v1" in doc, "the copy-paste workflow must use the pinnable ref"
    assert ".github/actions/misaka-intake-bot" not in doc, (
        "this doc is the instruction external maintainers follow; it must not name the path that "
        "no longer exists"
    )
