#!/usr/bin/env python3
"""The cross-platform matrix reported ✅ while running zero tests (#2006).

Measured on PR #2002's own job log (`test (macos-latest, 3.12)`, job `106261547580`):

    pytest tests/ -v --tb=short
      ERROR tests/test_add_provenance.py
      ModuleNotFoundError: No module named 'scripts'
      Interrupted: 1 error during collection
      → 1 skipped, 1 error in 5.12s
    Verify test outcome: ✅ Tests passed        ← the check grepped for "==+ .* failed"

Three separate defects produced that one green line, and each is pinned here:

1. **Nothing installed the repository.** `tests/` imports `scripts.…` from the repository root, and
   the workflow installed `requirements.txt` only — with even that behind `|| echo "::warning::"`.
   So every leg died in *collection*, which is not a test failure and therefore never matched the
   text the verdict looked for.
2. **The verdict was a text match.** `grep -qE "==+ .* failed"` cannot match `Interrupted: 1 error
   during collection` or `1 error in 5.12s`. pytest's exit code can: 0 pass, 1 failures,
   2 interrupted, **5 no tests ran**.
3. **The report contradicted the job.** `Report Results` read `steps.test.outcome`, but the test step
   had no `id:` — the value was empty, the comparison always false, so every leg printed
   "❌ …: FAIL" even when it passed.

This is the repository's own recurring defect class (#1825, #1826, #1984): a check that looks like it
is working and cannot fail. What is different here is the blast radius — this is the *only* place
tests run on another operating system, so `macOS`-shaped defects (like the missing `timeout` fixed in
PR #2002) had no way to be seen.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "ci-cross-platform.yml"


def code_of(text: str) -> str:
    """Executable lines of a `run:` block, comments removed.

    The fix for this very defect carries comments naming `steps.test.outcome` and
    `grep -qE "==+ .* failed"` to explain what went wrong, so a rule reading raw text is satisfied (or
    tripped) by the prose describing the bug — this repository has hit that five times already.
    """
    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))


def _steps() -> list[dict]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["test"]["steps"]


def _step(name: str) -> dict:
    for step in _steps():
        if step.get("name") == name:
            return step
    raise AssertionError(f"no step named {name!r} — steps are {[s.get('name') for s in _steps()]}")


def _steps_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_the_suite_is_run_from_the_repository_root_on_every_leg():
    """`scripts.…` has to be importable, and only PYTHONPATH/`-e .` makes it so (see pr-checks.yml)."""
    text = _steps_text()
    assert "PYTHONPATH: $" in text, (
        "tests/ imports `scripts.…` from the repository root; without PYTHONPATH (or an editable "
        "install that adds it) every leg dies in collection — which is exactly how this workflow ran "
        "zero tests on eight legs (#2006)")
    install = _step("Install Dependencies")
    code = install["run"]
    assert "pip install" in code and "requirements.txt" in code
    assert "exit 1" in code, (
        "a failed dependency install must fail loudly: it used to be `|| echo \"::warning::…\"`, so a "
        "broken install left the leg to die in collection and report success")


def test_the_verdict_uses_the_exit_code_not_a_text_match():
    text = _steps_text()
    code = text.split("- name: Verify test outcome", 1)[1]
    assert 'steps.test.outputs.pytest_exit' in code, (
        "the verdict must read pytest's exit code; a text match cannot see a collection error")
    assert 'grep -qE "==+ .* failed"' not in code, (
        "that grep is the defect: it cannot match `Interrupted: 1 error during collection`")
    for code_value, what in (("2", "collection error"), ("5", "no tests ran")):
        assert f"{code_value})" in code, f"exit code {code_value} ({what}) must be handled explicitly"


def test_the_test_step_has_an_id_and_the_report_reads_it():
    """`Report Results` read `steps.test.outcome` while the step had no `id:` — always "FAIL"."""
    test_step = _step("Run Tests")
    assert test_step.get("id") == "test", "the report references steps.test.*, so the step needs the id"
    report = code_of(_step("Report Results")["run"])
    assert "steps.test.outputs.pytest_exit" in report, (
        "the report must use the same signal as the verdict, or the two disagree again")
    assert "steps.test.outcome" not in report, (
        "`outcome` is the pre-continue-on-error result; it is not the verdict")
    # The id is written by the test step itself, from PIPESTATUS — `tee` eats the exit code otherwise.
    assert "PIPESTATUS" in test_step["run"] and "pytest_exit=" in test_step["run"]


def test_the_test_step_runs_under_bash_on_every_platform():
    """`PIPESTATUS` and `$GITHUB_OUTPUT` redirects are bash; Windows defaults to pwsh."""
    assert _step("Run Tests").get("shell") == "bash", (
        "the exit-code capture only works in bash, and windows-latest defaults to pwsh")


def test_an_empty_collection_cannot_read_as_green():
    """Belt and braces beyond the exit code: a suite that collected nothing is not a suite."""
    code = _steps_text().split("- name: Verify test outcome", 1)[1]
    assert "no tests ran" in code
    assert "collected" in code, "the verify step should assert that a collection summary exists"


def test_the_workflow_still_runs_the_four_legs_it_claims_to():
    """The matrix is the whole point of this workflow; a narrowed matrix would hide the same class."""
    matrix = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["test"]["strategy"]["matrix"]
    assert "macos-latest" in matrix["os"], "macOS is where the environment-only defects live"
    assert "windows-latest" in matrix["os"]
    assert set(matrix["python-version"]) >= {"3.11", "3.12", "3.13"}


# ── guard the guard: replay the defect this file exists for ──────────────────────────────────────

def test_the_defect_that_shipped_is_caught(tmp_path):
    """Take the fixed workflow and put each of the three defects back, one at a time."""
    text = WORKFLOW.read_text(encoding="utf-8")

    # (3) the report reading an `outcome` whose step has no id
    mutated = text.replace("steps.test.outputs.pytest_exit", "steps.test.outcome")
    report = code_of(mutated.split("- name: Report Results", 1)[1])
    assert "steps.test.outcome" in report, "mutation did not take"
    assert "steps.test.outputs.pytest_exit" not in report

    # (2) the text-match verdict
    mutated2 = text.replace("EXIT_CODE=\"${{ steps.test.outputs.pytest_exit }}\"",
                            'grep -qE "==+ .* failed" test_output.txt', 1)
    assert 'grep -qE "==+ .* failed"' in mutated2
    assert 'steps.test.outputs.pytest_exit' not in mutated2.split("- name: Verify test outcome", 1)[1].split("- name: Report Results")[0], (
        "the verdict no longer reads the exit code — which is the defect")

    # (1) dropping PYTHONPATH — the *env line*, not the word (the comment explains it)
    mutated3 = text.replace("PYTHONPATH: ${{ github.workspace }}", "")
    assert "PYTHONPATH: $" not in mutated3, "mutation did not take"
    assert "PYTHONPATH" in mutated3, "the comment mentioning it stays; only the setting is removable"


def test_the_exit_code_can_actually_be_captured():
    """`shell: bash` runs with `-e`, so the capture lines must be protected from the failure they
    exist to record.

    Measured on this fix's own first CI run: the macOS legs went red with "The test step produced no
    exit code — it did not run", because `-e` aborted the step at the failing `pytest | tee`
    pipeline. Right conclusion, wrong reason, and neither of the two real macOS failures was named.
    """
    run = _step("Run Tests")["run"]
    assert "set +e" in run, "without `set +e` the step aborts before PYTEST_EXIT is read"
    assert run.index("set +e") < run.index("PYTEST_EXIT="), "the guard must come before the capture"
    assert "PIPESTATUS[0]" in run, "`tee` swallows the exit code otherwise"
    assert '"$GITHUB_OUTPUT"' in run, "the code has to reach the verdict step"
