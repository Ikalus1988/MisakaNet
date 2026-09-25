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
    # pytest's own exit code (1 = failing tests, 2 = interrupted during collection, 4 = usage error,
    # 5 = nothing collected). Carried out of the test step so the verdict can say *which* it was.
    "${{ steps.pytest.outputs.exit }}": "PYTEST_EXIT",
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


def run_report_streams(tmp_path, tag: str = "report", **values) -> tuple[str, str]:
    """Execute the real step; return (the report it writes, everything it printed).

    Both halves matter and they are read by different people: the report is the comment a contributor
    sees, and stdout is the run log — which for a *failed* audit is where the reason has to appear,
    because the report says what failed while the log has to say why.
    """
    script = _report_step_script()
    for expression, key in _EXPRESSIONS.items():
        script = script.replace(expression, _escape(values.get(key, "")))
    leftover = re.findall(r"\$\{\{[^}]*\}\}", script)
    assert not leftover, f"these expressions are not substituted and bash cannot evaluate them: {leftover}"

    body = tmp_path / f"{tag}.sh"
    body.write_text(script, encoding="utf-8")
    summary = tmp_path / f"{tag}-summary.md"
    env = dict(os.environ)
    env.update({
        "GITHUB_STEP_SUMMARY": str(summary),
        "GH_TOKEN": "",           # PR_NUM is empty for the default run, so no gh call happens
        "PR_NUM": "",
    })
    proc = subprocess.run([require_posix_shell(), "-e", str(body)], capture_output=True, text=True, env=env, cwd=tmp_path)
    assert proc.returncode in (0, 1), f"unexpected exit {proc.returncode}:\n{proc.stdout}\n{proc.stderr}"
    return summary.read_text(encoding="utf-8"), proc.stdout


def run_report(tmp_path, **values) -> str:
    """Execute the real step with the given step outputs; return the report it writes.

    A red verdict makes the step `exit 1` on purpose — the report is still written to the summary
    before that, which is the part a contributor reads.
    """
    return run_report_streams(tmp_path, **values)[0]


# A PR whose every gate passed — the control that proves the wording below comes from `OUTCOME` and
# not from a report that always says the same thing. PYTEST_EXIT is inert here (the message branch is
# only reached when OUTCOME is not success); the tests that care set it themselves.
_GREEN = {
    "SCOPE": "full", "OUTCOME": "success", "COVERAGE": "63", "SCORE": "100", "PYTEST_EXIT": "0",
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


# ── the reason, not just the fact (2026-09-25) ───────────────────────────────────────
# The wording above was already truthful about *what* happened. What it could not say is *why*: for
# days the audit printed "test suite has issues" for a suite that never ran, because the job pinned
# Python 3.10 while two test files import `tomllib` — pytest aborted during **collection** (exit 2)
# and the reader had to go several thousand log lines up to find out. Three of the eleven open PRs on
# 2026-09-25 were red for exactly that. So: the exit code is now carried out of the test step, and the
# failure message names it.
def _pytest_step_run() -> str:
    workflow = yaml.safe_load(PR_CHECKS.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if step.get("id") == "pytest":
                return step["run"]
    raise AssertionError("the `Run Test Suite` step (id: pytest) disappeared")


def test_the_test_step_publishes_its_exit_code():
    """The harness below substitutes `${{ … }}` into the script, so it *cannot* notice if the step
    stops writing the output — every message test would still pass on a value that never arrives."""
    run = _pytest_step_run()
    assert re.search(r"PYTEST_EXIT=\$\{PIPESTATUS\[0\]\}", run), run[-400:]
    assert re.search(r'echo "exit=\$PYTEST_EXIT" >> "\$GITHUB_OUTPUT"', run), (
        "pytest's exit code never reaches $GITHUB_OUTPUT, so the verdict cannot branch on it"
    )


def test_a_suite_that_never_ran_says_so_instead_of_blaming_the_contribution(tmp_path):
    _, stdout = run_report_streams(tmp_path, tag="collect", **{**_GREEN, "OUTCOME": "failure", "PYTEST_EXIT": "2"})
    assert "could not COLLECT" in stdout, stdout[-600:]
    assert "no test ran" in stdout, stdout[-600:]
    assert "python-version" in stdout or "runner" in stdout, (
        "a collection error is normally the runner rather than the PR, and the message should point "
        "there — that is the sentence that would have saved three PRs"
    )


def test_a_real_test_failure_is_still_called_a_test_failure(tmp_path):
    """The positive control: naming collection errors must not relabel a genuinely failing suite."""
    _, stdout = run_report_streams(tmp_path, tag="fail", **{**_GREEN, "OUTCOME": "failure", "PYTEST_EXIT": "1"})
    assert "failing tests" in stdout, stdout[-600:]
    assert "could not COLLECT" not in stdout, stdout[-600:]


@pytest.mark.parametrize("code,expected", [("4", "usage error"), ("5", "collected no tests")])
def test_the_other_pytest_exit_codes_are_named_too(code, expected, tmp_path):
    """4 and 5 are also "the suite did not really run"; the catch-all must not swallow them."""
    _, stdout = run_report_streams(tmp_path, tag=f"exit{code}", **{**_GREEN, "OUTCOME": "failure", "PYTEST_EXIT": code})
    assert expected in stdout, stdout[-600:]


def test_an_unknown_exit_code_falls_back_without_crashing(tmp_path):
    """The step must still produce a verdict when the output is empty (a skipped test step)."""
    _, stdout = run_report_streams(tmp_path, tag="unknown", **{**_GREEN, "OUTCOME": "failure", "PYTEST_EXIT": ""})
    assert "test suite has issues" in stdout, stdout[-600:]
