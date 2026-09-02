#!/usr/bin/env python3
"""Tests for bench/phase-b/orchestrator.py (fixtures verification model).

Rewritten 2026-08-28 to match the current API (fixture_names / load_fixture /
verify_fixture) — the old load_tasks()/run() contract no longer exists.
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bench" / "phase-b" / "orchestrator.py"

EXPECTED = {
    "dco-signoff",
    "git-merge-conflict",
    "mcp-invalid-json",
    "python-import-error",
    "timeout-hang",
}


def _module():
    spec = importlib.util.spec_from_file_location("phase_b_orchestrator", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_catalog_lists_known_fixtures():
    module = _module()
    assert set(module.fixture_names()) == EXPECTED


def test_load_fixture_returns_expected_contract():
    module = _module()
    f = module.load_fixture("dco-signoff")
    assert isinstance(f, dict)
    assert f["name"] == "dco-signoff"
    assert (ROOT / f["path"]).exists()
    expected = f["expected"]
    assert expected["scenario"] == "dco-signoff"
    assert expected["expected_fix"]
    assert expected["expected_outcome"] in {"success", "success_with_human_input", "timeout"}


def test_verify_fixture_reports_structured_result():
    module = _module()
    result = module.verify_fixture("dco-signoff")
    assert isinstance(result, dict)
    assert result.get("name") == "dco-signoff" or "ok" in result or "status" in result


def test_orchestrator_cli_lists_fixtures():
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--list", "--json"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    listed = {item["name"] for item in json.loads(result.stdout)}
    assert listed == EXPECTED
