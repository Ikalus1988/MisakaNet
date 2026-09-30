#!/usr/bin/env python3
"""Tests for scripts/check_doc_freshness.py (#2082).

Verifies the freshness gate catches stale numbers and passes clean docs.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_script_runs_without_error():
    """The script should exit 0 on the current repo state."""
    result = subprocess.run(
        [sys.executable, "scripts/check_doc_freshness.py", "--check"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"Script failed: {result.stdout}\n{result.stderr}"


def test_json_output_has_expected_keys():
    """JSON output should include ssot values and pass status."""
    result = subprocess.run(
        [sys.executable, "scripts/check_doc_freshness.py", "--json"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "ssot_lessons" in data
    assert "ssot_domains" in data
    assert "errors" in data
    assert "warnings" in data
    assert "pass" in data
    assert data["ssot_lessons"] > 0
    assert data["ssot_domains"] > 0


def test_reverse_test_detects_bad_number():
    """The reverse-test should detect an injected bad number."""
    result = subprocess.run(
        [sys.executable, "scripts/check_doc_freshness.py", "--reverse-test"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"Reverse test failed: {result.stdout}"
    assert "Reverse test passed" in result.stdout


def test_no_errors_in_current_sections():
    """No error-severity issues should exist in current doc sections."""
    result = subprocess.run(
        [sys.executable, "scripts/check_doc_freshness.py", "--json"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    data = json.loads(result.stdout)
    assert data["pass"] is True, f"Found errors: {data['errors']}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
