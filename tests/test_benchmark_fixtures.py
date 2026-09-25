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


def test_orchestrator_lists_all_fixtures():
    result = subprocess.run(
        [sys.executable, str(ORCHESTRATOR), "--list", "--json"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
cwd=REPO,
        timeout=300,   # a hang must fail this test, not hold the leg
)
    listed = {item["name"] for item in json.loads(result.stdout)}
    assert listed == EXPECTED_NAMES


def test_each_fixture_verifies():
    result = subprocess.run(
        [sys.executable, str(ORCHESTRATOR), "--json"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
cwd=REPO,
        timeout=300,   # a hang must fail this test, not hold the leg
)
    reports = json.loads(result.stdout)
    assert {report["fixture"] for report in reports} == EXPECTED_NAMES
    assert all(report["status"] == "PASS" for report in reports), reports


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
