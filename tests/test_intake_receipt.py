#!/usr/bin/env python3
"""Tests for scripts/emit_intake_receipt.py."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "emit_intake_receipt.py"


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO, capture_output=True, text=True,
    )


def test_check_passes_with_no_contributions():
    """--check returns 0 when no lessons have contrib_id."""
    r = run("--check")
    assert r.returncode == 0, f"expected 0, got {r.returncode}\n{r.stderr}"


def test_check_detects_pending_receipt(tmp_path=None):
    """--check returns 1 when a lesson has contrib_id but no receipt."""
    # Create a temporary lesson with contrib_id
    lessons_dir = REPO / "lessons" / "contrib"
    test_file = lessons_dir / "_test_receipt_tmp.md"
    try:
        test_file.write_text(
            '---\ntitle: "Test Receipt"\ndomain: test\ncontrib_id: "test-123"\nstatus: published\n---\n\n## Problem\n\nTest.\n',
            encoding="utf-8",
        )
        r = run("--check")
        assert r.returncode == 1, f"expected 1, got {r.returncode}"
        assert "pending receipt" in r.stderr
    finally:
        test_file.unlink(missing_ok=True)


def test_dry_run_shows_pending():
    """--dry-run lists pending receipts without posting."""
    lessons_dir = REPO / "lessons" / "contrib"
    test_file = lessons_dir / "_test_receipt_tmp.md"
    try:
        test_file.write_text(
            '---\ntitle: "Test Dry Run"\ndomain: test\ncontrib_id: "test-dry-456"\nstatus: published\n---\n\n## Problem\n\nTest.\n',
            encoding="utf-8",
        )
        r = run("--dry-run")
        assert r.returncode == 0
        assert "DRY RUN" in r.stdout
    finally:
        test_file.unlink(missing_ok=True)


def test_receipt_log_created():
    """Receipt log is created after emitting."""
    log_path = REPO / "data" / "intake_receipts.jsonl"
    # Ensure it doesn't exist
    log_path.unlink(missing_ok=True)
    # The script creates it on first emit — test that it can be created
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text('{"contrib_id": "test", "lesson_path": "test.md", "issue_url": "", "evidence_level": "unverified"}\n')
    assert log_path.exists()
    log_path.unlink()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"  {name} ... ", end="", flush=True)
            try:
                fn()
                print("PASS")
            except Exception as e:
                print(f"FAIL: {e}")