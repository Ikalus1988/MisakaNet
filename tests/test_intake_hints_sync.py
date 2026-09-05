"""CI guard: verify workers/lib/utils.js is in sync with data/intake-kind-hints.json."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_utils_js_in_sync():
    """utils.js QUESTION_HINTS/FAILURE_HINTS must match intake-kind-hints.json."""
    result = subprocess.run(
        [sys.executable, "scripts/sync_intake_hints.py", "--check"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"utils.js is out of sync with intake-kind-hints.json.\n"
        f"Run: python3 scripts/sync_intake_hints.py\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_json_loadable():
    """The JSON file must be valid and contain both hint arrays."""
    path = ROOT / "data" / "intake-kind-hints.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data.get("question_hints"), list)
    assert isinstance(data.get("failure_hints"), list)
    assert len(data["question_hints"]) >= 20
    assert len(data["failure_hints"]) >= 3


def test_python_intake_kind_uses_json():
    """scripts/intake_kind.py must load hints from the JSON file."""
    src = (ROOT / "scripts" / "intake_kind.py").read_text(encoding="utf-8")
    assert "intake-kind-hints.json" in src, "intake_kind.py should load from JSON"
    # Should not have hardcoded QUESTION_HINTS lists
    assert "QUESTION_HINTS = [" not in src, "QUESTION_HINTS should be loaded from JSON, not hardcoded"
