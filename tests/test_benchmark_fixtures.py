#!/usr/bin/env python3
"""Tests for canonical benchmark fixtures and the Phase-B loader."""
import json
import subprocess
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
    )
    reports = json.loads(result.stdout)
    assert {report["fixture"] for report in reports} == EXPECTED_NAMES
    assert all(report["status"] == "PASS" for report in reports), reports
