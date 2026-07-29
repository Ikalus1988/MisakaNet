#!/usr/bin/env python3
"""Validation test for OKF required fields (issue #274 acceptance criteria)."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_FIELDS = {"type", "title", "description", "tags", "timestamp"}


def test_okf_export_has_required_fields():
    """Every exported OKF record must have all required fields."""
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "export_okf.py"), "--output", tmp, "--validate"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"Export failed: {result.stderr}"

        okf_file = Path(tmp) / "lessons.jsonl"
        assert okf_file.exists(), "lessons.jsonl not created"

        count = 0
        with open(okf_file, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                for field in REQUIRED_FIELDS:
                    assert field in record, f"Missing field '{field}' in record: {record.get('id', '?')}"
                    assert record[field], f"Empty field '{field}' in record: {record.get('id', '?')}"
                assert isinstance(record["tags"], list), f"tags must be list in: {record.get('id')}"
                count += 1

        assert count > 0, "No lessons exported"
        print(f"OK: {count} records validated")


def test_sag_index_builds():
    """SAG-Lite index builds successfully from OKF bundle."""
    with tempfile.TemporaryDirectory() as tmp:
        # Export first
        subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "export_okf.py"), "--output", tmp],
            capture_output=True, text=True, cwd=str(REPO_ROOT), check=True,
        )
        # Build index
        db_path = Path(tmp) / "test.db"
        okf_file = Path(tmp) / "lessons.jsonl"
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "build_sag_index.py"), "--db", str(db_path), "--okf", str(okf_file)],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"Index build failed: {result.stderr}"
        assert db_path.exists(), "Database not created"
        print(f"OK: index built at {db_path}")


if __name__ == "__main__":
    test_okf_export_has_required_fields()
    test_sag_index_builds()
    print("\nAll validation tests passed!")
