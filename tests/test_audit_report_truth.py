#!/usr/bin/env python3
"""The audit report said "tests failed" about a suite that never ran (#1959, #1960, #1961).

`Run Test Suite` carries `if: steps.scope.outputs.scope == 'full'`. A step condition that contains no
status function inherits an implicit `success()`, so the moment an earlier gate in the job goes red —
DCO, most often, because "6 commit(s) without sign-off" is easy to produce and easy to fix — every
later step is skipped. `steps.pytest.outcome` is then the string `skipped`, and the verdict treated
*skipped* and *failed* as the same thing:

    OUTCOME="skipped"   DCO_RESULT="false"
    ❌ **FAIL** — tests have failures
    ❌ Test suite failed.

A contributor reading that goes looking for test failures that do not exist, in a PR whose tests never
started. `skipped` must still keep the verdict red — a gate nobody ran is not a gate that passed — but
it has to be named correctly, because the report is the only thing the contributor sees.

These tests execute the real `Post Audit Report` step with the `steps.*` values substituted, rather
than pattern-matching its text, so that "the report tells the truth" is checked on the output a person
would read.
"""
from __future__ import annotations

import os
import re
import subprocess

import pytest
from pathlib import Path

from posix_shell import require_posix_shell

yaml = pytest.importorskip("yaml", reason="PyYAML parses the workflow")

REPO = Path(__file__).resolve().parent.parent
PR_CHECKS = REPO / ".github" / "workflows" / "pr-checks.yml"

# Expressions the step interpolates. Each one is a `steps.*` output or a PR field, i.e. exactly the
# values the job computes; the test supplies them instead of running the whole job.
_EXPRESSIONS = {
    "${{ steps.scope.outputs.scope }}": "SCOPE",
    "${{ steps.pytest.outcome }}": "OUTCOME",
    "${{ steps.coverage.outputs.rate }}": "COVERAGE",
    "${{ steps.prsize.outputs.suspicious }}": "SUSPICIOUS",
    "${{ steps.prsize.outputs.notes }}": "SIZE_NOTES",
    "${{ steps.score.outputs.score }}": "SCORE",
    "${{ steps.score.outputs.reasons }}": "REASONS",
    "${{ steps.dco.outputs.dco-passed }}": "DCO_RESULT",
    "${{ steps.dco.outputs.failed-count }}": "DCO_FAILED",
    "${{ steps.schema.outputs.schema_result }}": "SCHEMA",
    "${{ steps.secrets.outputs.secrets_result }}": "SECRETS",
    "${{ steps.depaudit.outputs.depaudit_result }}": "DEPAUDIT",
    "${{ github.event.inputs.pr_number || github.event.pull_request.number }}": "PR_NUM",
    "${{ github.event.pull_request.head.sha || 'manual' }}": "SHA",
    # Not part of the verdict, but they are inside the same script and bash cannot evaluate them.
    "${{ github.event.pull_request.changed_files }}": "CHANGED_FILES",
    "${{ github.event.pull_request.additions }}": "ADDITIONS",
    "${{ github.run_id }}": "RUN_ID",
}


def _report_step_script() -> str:
    workflow = yaml.safe_load(PR_CHECKS.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if step.get("name") == "Post Audit Report":
                return step["run"]
    raise AssertionError("the Post Audit Report step disappeared — the audit comment is how a "
                         "contributor learns why their PR is red")


def _escape(value: str) -> str:
    """Values reach the shell inside double quotes, so a stray `"` would end the string early."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")


def run_report(tmp_path, **values) -> str:
    """Execute the real step with the given step outputs; return the report it writes.

    A red verdict makes the step `exit 1` on purpose — the report is still written to the summary
    before that, which is the part a contributor reads.
    """
    script = _report_step_script()
    for expression, key in _EXPRESSIONS.items():
        script = script.replace(expression, _escape(values.get(key, "")))
    leftover = re.findall(r"\$\{\{[^}]*\}\}", script)
    assert not leftover, f"these expressions are not substituted and bash cannot evaluate them: {leftover}"

    body = tmp_path / "report.sh"
    body.write_text(script, encoding="utf-8")
    summary = tmp_path / "summary.md"
    env = dict(os.environ)
    env.update({
        "GITHUB_STEP_SUMMARY": str(summary),
        "GH_TOKEN": "",           # PR_NUM is empty for the default run, so no gh call happens
        "PR_NUM": "",
    })
    proc = subprocess.run([require_posix_shell(), "-e", str(body)], capture_output=True, text=True, env=env, cwd=tmp_path)
    assert proc.returncode in (0, 1), f"unexpected exit {proc.returncode}:\n{proc.stdout}\n{proc.stderr}"
    return summary.read_text(encoding="utf-8")


# A PR whose every gate passed — the control that proves the wording below comes from `OUTCOME` and
# not from a report that always says the same thing.
_GREEN = {
    "SCOPE": "full", "OUTCOME": "success", "COVERAGE": "63", "SCORE": "100",
    "DCO_RESULT": "true", "SCHEMA": "pass", "SECRETS": "pass", "DEPAUDIT": "pass",
    "SHA": "abcdef1234567",
}


def test_a_skipped_suite_is_not_reported_as_a_failed_one(tmp_path):
    """The #1959 shape: DCO red, tests never ran (`OUTCOME="skipped"`)."""
    report = run_report(tmp_path, **{**_GREEN, "OUTCOME": "skipped", "DCO_RESULT": "false", "DCO_FAILED": "6"})
    assert "did not run" in report, (
        "a suite that never started must say so — this is the sentence #1959/#1960/#1961 read")
    assert "tests have failures" not in report, (
        "claiming test failures for a suite that was skipped is the defect: contributors then hunt "
        "for failures that do not exist")
    assert "Test suite failed" not in report
    # DCO is what actually failed, and it must still be the named blocker.
    assert "6 commit(s)" in report and "DCO audit failed" in report


def test_a_genuinely_failing_suite_is_still_reported_as_failed(tmp_path):
    """The positive control: the skip wording must not swallow a real failure."""
    report = run_report(tmp_path, **{**_GREEN, "OUTCOME": "failure", "COVERAGE": "41"})
    assert "FAIL" in report and "tests have failures" in report
    assert "Test suite failed" in report, "a red suite must still be called a red suite"
    assert "did not run" not in report


def test_a_green_run_still_reads_green(tmp_path):
    report = run_report(tmp_path, **_GREEN)
    assert "All gates passed" in report, report[-400:]
    assert "did not run" not in report and "FAIL" not in report


def test_a_skipped_suite_keeps_the_verdict_red(tmp_path):
    """Unverified is not verified: the wording changed, the verdict must not have."""
    report = run_report(tmp_path, **{**_GREEN, "OUTCOME": "skipped", "DCO_RESULT": "true"})
    verdict = report.split("Verdict")[-1]
    assert "did not run" in verdict, "the verdict must name the skipped suite as skipped"
    assert "all gates passed" not in report.lower(), (
        "with the suite skipped and no other gate failing, the verdict must still be red — otherwise "
        "`skipped` becomes a way to pass without running anything")


def test_stripping_the_skip_branch_reproduces_the_old_report(tmp_path):
    """Mutation: fold `skipped` back into `failure` and the wrong sentence comes back."""
    # Drop the whole `elif [ "$OUTCOME" = "skipped" ]` arm, whatever its comment says — a literal copy
    # of the block here would rot the moment the comment is edited, and a mutation that silently fails
    # to mutate asserts nothing (this repository has shipped that mistake before).
    script = re.sub(
        r'\n *elif \[ "\$OUTCOME" = "skipped" \]; then\n(?: *#.*\n)* *REPORT\+="[^\n]*"\n',
        "\n",
        _report_step_script(),
    )
    assert "Did not run" not in script, "the branch body survived the mutation"

    for expression, key in _EXPRESSIONS.items():
        script = script.replace(expression, _escape({**_GREEN, "OUTCOME": "skipped"}.get(key, "")))
    body = tmp_path / "mutated.sh"
    body.write_text(script, encoding="utf-8")
    summary = tmp_path / "mutated.md"
    env = dict(os.environ)
    env.update({"GITHUB_STEP_SUMMARY": str(summary), "GH_TOKEN": "", "PR_NUM": ""})
    proc = subprocess.run([require_posix_shell(), "-e", str(body)], capture_output=True, text=True, env=env, cwd=tmp_path)
    assert proc.returncode in (0, 1), f"{proc.stdout}\n{proc.stderr}"
    assert "tests have failures" in summary.read_text(encoding="utf-8"), (
        "without the branch, the old 'a skipped suite is a failed suite' wording must return")
