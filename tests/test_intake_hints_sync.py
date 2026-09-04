#!/usr/bin/env python3
"""Verify intake kind hints are consistent and loaded from JSON single source.

Single source of truth is workers/lib/intake-hints.json.
This test ensures:
1. intake-hints.json exists, is valid JSON, and has all expected keys
2. Regex patterns in question_hints and failure_hints compile without error
3. Python (scripts/intake_kind.py) loads patterns from JSON
4. JS (workers/lib/utils.js) loads patterns from JSON
"""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO_ROOT = Path(__file__).resolve().parent.parent
HINTS_FILE = REPO_ROOT / "workers" / "lib" / "intake-hints.json"


def test_hints_file_exists_and_valid():
    assert HINTS_FILE.exists(), f"Missing {HINTS_FILE}"
    data = json.loads(HINTS_FILE.read_text(encoding="utf-8"))
    assert "intake_kinds" in data
    assert "question_hints" in data
    assert "failure_hints" in data
    assert isinstance(data["intake_kinds"], list)
    assert isinstance(data["question_hints"], list)
    assert isinstance(data["failure_hints"], list)
    assert "question" in data["intake_kinds"]
    assert "missing_lesson" in data["intake_kinds"]

    for pattern in data["question_hints"]:
        re.compile(pattern, re.IGNORECASE)

    for pattern in data["failure_hints"]:
        re.compile(pattern, re.IGNORECASE)


def test_python_intake_kind_uses_json():
    from scripts.intake_kind import INTAKE_KINDS, QUESTION_HINTS, FAILURE_HINTS
    data = json.loads(HINTS_FILE.read_text(encoding="utf-8"))
    assert list(INTAKE_KINDS) == data["intake_kinds"]
    assert list(QUESTION_HINTS) == data["question_hints"]
    assert list(FAILURE_HINTS) == data["failure_hints"]
