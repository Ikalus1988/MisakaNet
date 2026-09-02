"""Contract tests for the clone-less ``search_knowledge.py --remote`` CLI.

The tests are opt-in because they exercise the deployed D1-backed endpoint::

    MISAKANET_REMOTE_TEST=1 pytest -q tests/test_issue_1361_remote_search.py

They intentionally invoke the CLI as a subprocess, matching the issue's user-facing
commands and proving that the command works from a fresh environment without reading
local lesson files.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("MISAKANET_REMOTE_TEST") != "1",
    reason="set MISAKANET_REMOTE_TEST=1 to run live D1 contract tests",
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "search_knowledge.py"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=Path("/tmp"),
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )


def test_basic_remote_search_returns_ranked_results():
    result = run_cli("pip install timeout", "--remote")
    assert result.returncode == 0, result.stderr
    assert "pip-install-timeout-ssl" in result.stdout.lower()
    assert "score" in result.stdout.lower()


def test_remote_json_has_stable_result_schema():
    result = run_cli("docker compose", "--remote", "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert payload
    assert {"title", "domain", "tags", "score", "path", "preview"} <= payload[0].keys()


def test_remote_suggest_returns_titles_without_full_content():
    result = run_cli("kubernetes pod crash", "--remote", "--suggest")
    assert result.returncode == 0, result.stderr
    assert "## 根因" not in result.stdout
    assert "traceback" not in result.stdout.lower()
    assert "suggestions" in result.stdout.lower() or "no matches" in result.stdout.lower()


def test_remote_domain_filter_returns_only_python_lessons():
    result = run_cli("", "--remote", "--domain", "python")
    assert result.returncode == 0, result.stderr
    assert "filtering by domain: python" in result.stdout.lower()
    for line in result.stdout.splitlines():
        if line.strip().startswith("["):
            assert "[python]" in line.lower()


def test_remote_no_results_does_not_crash():
    result = run_cli("quantum computing error correction", "--remote")
    assert result.returncode == 0, result.stderr
    assert "traceback" not in result.stdout.lower()
