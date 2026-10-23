#!/usr/bin/env python3
"""Tests for canonical benchmark fixtures and the Phase-B loader."""
import json
import subprocess

import pytest
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ORCHESTRATOR = REPO / "bench" / "phase-b" / "orchestrator.py"
FIXTURES = REPO / "bench" / "fixtures"
EXPECTED_NAMES = {
    "dco-signoff",
    "python-import-error",
    "mcp-invalid-json",
    "git-merge-conflict",
    "timeout-hang",
}


def test_fixture_contracts_are_complete():
    names = {p.name for p in FIXTURES.iterdir() if p.is_dir()}
    assert names == EXPECTED_NAMES
    for name in names:
        path = FIXTURES / name
        assert (path / "setup.sh").is_file()
        assert (path / "teardown.sh").is_file()
        expected = json.loads((path / "expected.json").read_text(encoding="utf-8"))
        assert expected["scenario"] == name
        assert expected["expected_fix"]
        assert expected["expected_outcome"] in {"success", "success_with_human_input", "timeout"}
        assert expected["verifier"]["type"] in {"command_exit", "file_content", "process_timeout"}
        if expected["verifier"]["type"] == "file_content":
            assert "must_contain" in expected["verifier"] or "must_not_contain" in expected["verifier"]


def _describe_failure(stdout: str, stderr: str, returncode: int) -> str:
    """The evidence a red leg has to carry: which fixture failed, and why.

    The orchestrator prints its full report on stdout *before* returning a non-zero exit code
    (`main()` returns 1 when any fixture is not PASS, and it prints the JSON first). Calling it
    with `check=True` therefore throws away the only artifact that names the failure: the
    `CalledProcessError` carries an exit code and nothing else, so the log says "returned
    non-zero exit status 1" and does not say which fixture failed, or what it saw.

    That is not a hypothetical. On 2026-10-23 the `test (windows-latest, 3.11)` leg of PR #3761
    went red exactly that way: 4704 passed, 89 skipped, one failure, and the failure said
    nothing about the fixture. The re-run of the same commit passed, so the red was
    intermittent -- and the next one will be intermittent too. But as long as the evidence is
    discarded at the call, every occurrence costs the same blind search.

    So the exit code stays the verdict; this only makes sure the message that reports it is
    the one the orchestrator already wrote.
    """
    try:
        reports = json.loads(stdout)
    except (TypeError, ValueError):
        reports = []
    failed = [
        report.get("fixture")
        for report in reports
        if isinstance(report, dict) and report.get("status") != "PASS"
    ]
    return "\n".join(
        [
            f"the orchestrator did not pass every fixture (exit {returncode}).",
            f"failed fixtures: {failed or 'unknown - no machine-readable report on stdout'}",
            f"stdout:\n{stdout.strip()}",
            f"stderr:\n{stderr.strip()}",
        ]
    )


def test_orchestrator_lists_all_fixtures():
    result = subprocess.run(
        [sys.executable, str(ORCHESTRATOR), "--list", "--json"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
cwd=REPO,
        timeout=300,   # a hang must fail this test, not hold the leg
)
    assert result.returncode == 0, _describe_failure(
        result.stdout, result.stderr, result.returncode)
    listed = {item["name"] for item in json.loads(result.stdout)}
    assert listed == EXPECTED_NAMES


def test_each_fixture_verifies():
    result = subprocess.run(
        [sys.executable, str(ORCHESTRATOR), "--json"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
cwd=REPO,
        timeout=300,   # a hang must fail this test, not hold the leg
)
    assert result.returncode == 0, _describe_failure(
        result.stdout, result.stderr, result.returncode)
    reports = json.loads(result.stdout)
    assert {report["fixture"] for report in reports} == EXPECTED_NAMES
    assert all(report["status"] == "PASS" for report in reports), reports


def test_a_red_leg_must_name_the_fixture_that_failed():
    """The red leg has to carry the evidence that names the culprit.

    Before this, a failing fixture could only surface as `CalledProcessError`, which names
    nothing: the report the orchestrator wrote was on stdout, and the error threw it away.
    The property under test is that the failure message reaches the fixture's own report, so
    the next intermittent red costs a lookup instead of a blind search.
    """
    message = _describe_failure(
        json.dumps(
            [
                {"fixture": "dco-signoff", "status": "PASS", "detail": "ok"},
                {
                    "fixture": "timeout-hang",
                    "status": "FAIL",
                    "detail": "process exited with code 1 before timeout",
                },
            ]
        ),
        "",
        1,
    )
    assert "timeout-hang" in message
    assert "process exited with code 1 before timeout" in message
    # the fixtures that passed are named too, so the reader can see what did *not* break
    assert "dco-signoff" in message


def test_a_red_leg_survives_output_it_cannot_parse():
    """A crash before the report is written must still say what happened.

    `stdout` can be empty or truncated when the orchestrator dies before printing; the message
    then has to carry the raw output instead of a parsed list, so the reader is not left with
    "unknown" and nothing else.
    """
    message = _describe_failure("", "Traceback (most recent call last): ...", 1)
    assert "unknown" in message
    assert "Traceback" in message


def _orchestrator_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("phase_b_orchestrator_timeout", ORCHESTRATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_timing_out_fixture_raises_instead_of_returning(tmp_path):
    """A command that never finishes must produce `TimeoutExpired`, and soon.

    This is the property every caller in `orchestrator.py` relies on: the two fixtures whose whole
    point is not to finish (`timeout-hang`, and any `process_timeout` verifier) are judged by catching
    this exception. What it does **not** prove is the Windows-specific shape — see below.
    """
    import subprocess
    import time

    module = _orchestrator_module()
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        module._run("sh -c 'sleep 30'", tmp_path, 1)
    assert time.monotonic() - started < 15, "the timeout must be observed, not waited out"


# Not covered here, and deliberately stated rather than implied: on 2026-09-21 three windows legs sat
# for the full 30-minute job bound on `test_each_fixture_verifies`, whose last log line was the test
# before it. The mechanism that fits the evidence is that `subprocess.run(shell=True, timeout=...)`
# kills the *shell* on Windows while the process the shell spawned keeps the stdout/stderr pipes open,
# so the drain waits for an EOF that never comes. `orchestrator._kill_tree` + the bounded drain were
# added for that shape. It cannot be reproduced on this Linux box: with `sh -c 'sleep 30 & sleep 30'`
# and even a `setsid` grandchild, the previous one-liner still returned in ~1.2s, so a test asserting
# the fix would pass against the bug and be worse than no test. Windows CI is the verification.
