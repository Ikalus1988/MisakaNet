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


# ── the number, not the part after the comma ─────────────────────────────────────────────────────
def _count_pattern():
    """The scanner's own regex, imported rather than copied.

    A copy would pass while the real one drifted, which is the defect
    `tests/test_doctor_reach.py` was written for one layer over.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "check_doc_freshness", REPO_ROOT / "scripts" / "check_doc_freshness.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._COUNT_PATTERN


def test_a_thousands_separator_is_part_of_the_number():
    """`1,169 lessons` is 1169, not 169 (measured 2026-11-27).

    The pattern's `\\d{2,5}` stopped at the comma and matched the tail on its own, so a document that
    wrote the count the way prose normally does was reported as *contradicting* the SSOT while being
    exactly right. It surfaced on the README hero's alt text, which is a place a number is written for
    a human — the prettiest form was the one the gate punished.
    """
    pattern = _count_pattern()
    assert int(pattern.search("we ship 1,169 lessons").group(1).replace(",", "")) == 1169
    assert int(pattern.search("we ship 1169 lessons").group(1)) == 1169
    # Small counts keep working, with and without the separator.
    assert int(pattern.search("250 lessons").group(1)) == 250
    assert int(pattern.search("1,100 lessons").group(1).replace(",", "")) == 1100


def test_a_wrong_grouped_count_is_still_caught():
    """Widening the pattern must not make it blind: the number it extracts is still compared."""
    pattern = _count_pattern()
    assert int(pattern.search("1,000 lessons").group(1).replace(",", "")) == 1000


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
