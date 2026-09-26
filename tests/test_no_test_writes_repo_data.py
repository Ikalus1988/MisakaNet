#!/usr/bin/env python3
"""A test that writes into the checkout's own data files is a defect, not a habit.

Why this file exists. Two of this repository's data files are *logs about the repository*:

* `data/search_gaps.jsonl` — the queries that returned nothing. It is the local input for "which lessons
  are missing" (`scripts/demand_board.py`), so its value depends entirely on being real user traffic.
  It had reached 278 rows whose largest entries were test queries: `quantum computing error correction`
  ×105 and `draft test lesson` ×49.
* `data/contribution_queue.jsonl` — contributions awaiting a decision. It had reached 522 rows, **520 of
  them fixtures** (`source: contract-test` 381, `mcp-agent` 134), and every one still `pending` — so
  anything reading it to ask "what is waiting for a decision" was reading test data.

Both are gitignored, which is why nobody noticed: nothing in CI, no diff, no review. The writer was
`tests/test_mcp_server.py` — a directly-runnable smoke script that drives the real submit and search
handlers, so it could not rely on a conftest fixture for isolation even if one had existed.

The fix is deliberately not "patch the constant in the offending tests": the failure was never that a
test forgot, it was that **nothing made writing into the checkout impossible**. `tests/conftest.py`
redirects both paths for the whole session, the smoke script redirects them for itself when run directly,
and the assertions below are what keeps that true.

The behavioural tests matter more than the constant checks: a fixture that redirects a *copy* of the path
while the handler keeps using the original would pass an equality check on the constant and still write
into the repository.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

GAP_LOG = REPO / "data" / "search_gaps.jsonl"
QUEUE = REPO / "data" / "contribution_queue.jsonl"
ENV_VARS = ("MISAKANET_GAP_LOG", "MISAKANET_CONTRIBUTION_QUEUE")


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _resolve_in_subprocess(import_stmt: str, env_overrides: dict[str, str]) -> str:
    """Resolve a module-level path constant in a **fresh interpreter** and return it.

    A subprocess rather than `importlib` plus `sys.modules` surgery: the first version of this file
    popped and restored cached modules to re-import with a different environment, which left the cache
    in a state where a later test imported a handler holding the *previous* test's path. The bug was in
    the test, and it presented as a failure in an unrelated assertion — so the isolated interpreter is
    worth the ~0.3s it costs.
    """
    env = {k: v for k, v in os.environ.items() if k not in ENV_VARS}
    env.update(env_overrides)
    code = (
        "import sys; sys.path.insert(0, %r)\n%s\nprint(path)\n" % (str(REPO), import_stmt)
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=REPO, env=env,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, f"resolving the path failed:\n{result.stderr[-500:]}"
    return result.stdout.strip().splitlines()[-1]


# ── the override is real ────────────────────────────────────────────────────

def test_the_gap_log_honours_its_override(tmp_path):
    target = tmp_path / "gaps.jsonl"
    got = _resolve_in_subprocess(
        "from misakanet.server.handlers.search import _GAPS_FILE as path",
        {"MISAKANET_GAP_LOG": str(target)})
    assert got == str(target), "the gap log ignores MISAKANET_GAP_LOG"


def test_the_contribution_queue_honours_its_override(tmp_path):
    target = tmp_path / "queue.jsonl"
    got = _resolve_in_subprocess(
        "from scripts.contribution_queue import QUEUE_FILE as path",
        {"MISAKANET_CONTRIBUTION_QUEUE": str(target)})
    assert got == str(target), "the queue ignores MISAKANET_CONTRIBUTION_QUEUE"


def test_without_an_override_the_paths_stay_in_the_repository():
    """Production must not need an environment variable to find its own files."""
    assert _resolve_in_subprocess(
        "from misakanet.server.handlers.search import _GAPS_FILE as path", {}) == str(GAP_LOG)
    assert _resolve_in_subprocess(
        "from scripts.contribution_queue import QUEUE_FILE as path", {}) == str(QUEUE)


# ── the session is redirected, and a real write does not reach the repository ──

def test_this_test_session_redirected_both_paths():
    """`tests/conftest.py` must have set these before the handlers were imported."""
    from misakanet.server.handlers import search
    from scripts import contribution_queue

    for name, path in (("gap log", search._GAPS_FILE), ("queue", contribution_queue.QUEUE_FILE)):
        assert REPO not in path.parents, (
            f"the {name} still points inside the checkout ({path}) — tests/conftest.py's redirection is "
            "not in effect, so this very session is writing into the repository's data files"
        )
    assert search._GAPS_FILE.name.endswith(".jsonl")
    assert contribution_queue.QUEUE_FILE.name.endswith(".jsonl")


def test_a_no_result_search_does_not_append_to_the_repository():
    """Drive the real handler and check the repository's copy, not the redirected one."""
    from misakanet.server.handlers.search import handle_search

    before = digest(GAP_LOG)
    # A query the corpus cannot answer, so the gap branch is actually taken. Letters and a space only:
    # the local FTS path raises on punctuation (`sqlite3.OperationalError: no such column: preflight`
    # for a hyphenated query — the defect PR #1999 fixes), which would skip the branch under test.
    handle_search({"query": "qxzv wumblefrotz sentinel", "top": 1})
    assert digest(GAP_LOG) == before, (
        "a search from the test suite appended to data/search_gaps.jsonl — the gap log is the input for "
        "'which lessons are missing', and test traffic is what made its top entries noise"
    )


def test_a_contribution_does_not_append_to_the_repository():
    from scripts.contribution_queue import submit_contribution

    before = digest(QUEUE)
    submit_contribution(
        "lesson",
        user="test:preflight",
        title="preflight sentinel — this submission must not reach the repository",
        problem="p", root_cause="r", fix="f",
        source="preflight-sentinel",
    )
    assert digest(QUEUE) == before, (
        "a submission from the test suite appended to data/contribution_queue.jsonl — 99% of that file "
        "was fixtures, which made 'what is waiting for a decision' unreadable"
    )


def test_the_redirected_files_are_actually_written_to(tmp_path):
    """The other direction: the redirection must not be achieved by making the writers no-ops.

    Without this, deleting the write calls entirely would satisfy every assertion above — a gate that
    cannot tell "isolated" from "broken" is the shape this repository keeps finding in its own gates.
    """
    target = tmp_path / "gaps.jsonl"
    code = (
        "import os, sys\n"
        "os.environ['MISAKANET_GAP_LOG'] = %r\n"
        "sys.path.insert(0, %r)\n"
        "from misakanet.server.handlers.search import _log_search_gap\n"
        "_log_search_gap('sentinel-query-for-the-isolation-test', 'unit-test')\n" % (str(target), str(REPO))
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True,
                            text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-400:]
    assert target.exists(), "the gap log wrote nothing at all under an override"
    rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(r.get("query") == "sentinel-query-for-the-isolation-test" for r in rows)


def test_the_directly_runnable_smoke_script_isolates_itself():
    """`tests/conftest.py` does not apply to `python3 tests/test_mcp_server.py`, so it must do it itself.

    Run as a subprocess with the env vars *removed*, which is the state a contributor is in when they
    follow the script's own usage line.
    """
    env = {k: v for k, v in os.environ.items() if k not in ENV_VARS}
    before = (digest(GAP_LOG), digest(QUEUE))
    result = subprocess.run([sys.executable, str(REPO / "tests" / "test_mcp_server.py")],
                            cwd=REPO, env=env, capture_output=True, text=True, timeout=300)
    assert result.returncode in (0, 1), f"the smoke script crashed: {result.stderr[-400:]}"
    assert (digest(GAP_LOG), digest(QUEUE)) == before, (
        "running tests/test_mcp_server.py directly wrote into the repository's data files; that script "
        "drives the real handlers and must redirect them itself"
    )
