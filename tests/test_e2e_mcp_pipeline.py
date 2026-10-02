#!/usr/bin/env python3
"""E2E tests for MisakaNet MCP pipeline (Issues #1359, #1360, #1361).

Tests the complete workflow:
1. Lesson write pipeline: submit -> issue -> lesson -> search (Issue #1359)
2. No-match feedback loop: search -> suggestion -> intake -> lesson (Issue #1360)
3. CLI --remote mode: clone-less search via D1 (Issue #1361)

This file used to be called ``tests/e2e_mcp_pipeline.py``. That name does not
match pytest's default ``test_*.py`` collection pattern, so **none of its five
tests had ever run in any gate** -- it read as E2E coverage without being one.
Renaming it into the collected set exposed three further defects, all fixed here:

* the functions ``return``\\ ed a dict/bool instead of asserting, and pytest
  discards a test function's return value -- so even once collected they would
  have reported PASS while failing (measured: a ``def test_x(): return False``
  is reported as ``1 passed``);
* the local path submitted a real record into ``data/contribution_queue.jsonl``
  (repo state) instead of an isolated queue;
* the remote path hit the deployed endpoint without ``Origin`` /
  ``MCP-Protocol-Version``, which the live server rejects with 403.

The tests that need the deployed service are opt-in, matching the existing
convention of ``tests/test_issue_1361_remote_search.py``::

    MISAKANET_REMOTE_TEST=1 pytest -q tests/test_e2e_mcp_pipeline.py

The default run needs no network: it drives the same pipeline through the
in-process handlers and redirects the contribution queue to a temp file.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# The deployed endpoint rejects requests without these headers (403). Measured
# 2026-10-02: `Origin` and `MCP-Protocol-Version` are both required, *and* the
# edge answers 403 to a request whose User-Agent is Python-urllib's or Java's
# default (curl/Mozilla/absent are fine), so send an explicit one.
MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "MCP-Protocol-Version": "2025-06-18",
    "Origin": "https://misakanet.org",
    "User-Agent": "misakanet-e2e/1.0",
}

REMOTE = os.getenv("MISAKANET_REMOTE_TEST") == "1"
REMOTE_URL = os.getenv("MISAKANET_MCP_URL", "https://misakanet.org/mcp")

needs_remote = pytest.mark.skipif(
    not REMOTE,
    reason="set MISAKANET_REMOTE_TEST=1 to run the live-endpoint variant",
)


def _mcp_call(name: str, arguments: dict) -> dict:
    """Call a tool on the deployed endpoint and return the *tool payload*.

    Unwraps JSON-RPC: raises on a transport-level ``error``, and returns the
    object carried in the ``result.content[0].text`` envelope.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    req = urllib.request.Request(
        REMOTE_URL, data=json.dumps(payload).encode(), headers=MCP_HEADERS
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    assert "error" not in body, f"{name} failed at the JSON-RPC layer: {body['error']}"
    result = body.get("result", {})
    assert result, f"{name} returned no result: {body}"
    if "content" in result:
        return json.loads(result["content"][0]["text"])
    return result


def test_submit_intake(monkeypatch, tmp_path):
    """Issue #1359 Step 1: Submit lesson via MCP intake.

    Hermetic: the queue is redirected into ``tmp_path`` so the test never writes
    repo state, and no network is involved.

    The redirect patches the module's constant rather than setting
    ``MISAKANET_CONTRIBUTION_QUEUE``: that variable is read **once, at import**
    (``scripts/contribution_queue.py``), so setting it only takes effect while
    nothing has imported the module yet. Run alone, this test was green; inside the
    full suite ``tests/conftest.py`` had already imported it, the write landed in
    the session queue, and the assertion below failed on all six CI legs while
    passing locally (reproduced by running ``tests/test_intake_backfill.py`` first).
    ``patch(...QUEUE_FILE...)`` is what the other queue tests already do, and it is
    independent of collection order.
    """
    monkeypatch.syspath_prepend(str(REPO_ROOT))
    import scripts.contribution_queue as contribution_queue
    monkeypatch.setattr(contribution_queue, "QUEUE_FILE", tmp_path / "queue.jsonl")

    from misakanet.server.handlers.submit import handle_submit_intake

    result = handle_submit_intake(
        {
            "kind": "new_lesson_candidate",
            "problem": "Agent failed to parse YAML frontmatter with nested quotes",
            "error": "YAMLException: bad indentation of a mapping at line 3",
            "what_tried": "Tried PyYAML, ruamel.yaml, js-yaml",
            "source": "e2e-test",
        }
    )
    assert result.get("submitted") is True, f"intake was not accepted: {result}"
    assert result.get("intake_id"), f"no intake_id in the receipt: {result}"
    assert (tmp_path / "queue.jsonl").exists(), "the intake was not persisted to the queue"


@needs_remote
def test_submit_intake_remote():
    """Issue #1359 Step 1, live endpoint variant: the deployed intake tool."""
    result = _mcp_call(
        "misakanet_submit_intake",
        {
            "kind": "new_lesson_candidate",
            "problem": "Agent failed to parse YAML frontmatter with nested quotes",
            "error": "YAMLException: bad indentation of a mapping at line 3",
            "what_tried": "Tried PyYAML, ruamel.yaml, js-yaml",
            "source": "e2e-test",
        },
    )
    # Anonymous intakes are deduplicated server-side, so a repeat submission is a
    # legitimate answer; what must not happen is an unexplained rejection.
    assert result.get("submitted") is True or result.get("error") == "duplicate", (
        f"intake was neither accepted nor deduplicated: {result}"
    )


@needs_remote
def test_no_match_search():
    """Issue #1360 Step 1: a nonsense query is answered as a miss, not a hit.

    Live-only on purpose. The relevance floor that turns "no token matches
    anything" into ``no_match`` lives in the deployed worker; the in-process
    handler deliberately has no such floor (it scores lexical overlap and returns
    whatever is > 0), so asserting this locally would be testing a contract the
    local backend does not implement. Measured 2026-10-02: the live endpoint
    answers this query with ``no_match: True`` and 0 results; the local handler
    returns 5 weakly-matching lessons and no ``no_match`` key.
    """
    result = _mcp_call(
        "misakanet_search",
        {"query": "quantum computing error correction xyz123"},
    )
    hits = result.get("results") or []
    assert result.get("no_match") and not hits, (
        "a nonsense query must not look like a match: "
        f"no_match={result.get('no_match')!r} results={len(hits)}"
    )
    assert result.get("intake"), "a miss must carry the intake path (gap -> issue loop)"


@needs_remote
def test_remote_search_cli():
    """Issue #1361: the clone-less ``--remote --json`` CLI returns a JSON array."""
    search_script = REPO_ROOT / "search_knowledge.py"
    assert search_script.exists(), f"search_knowledge.py not found at {search_script}"

    result = subprocess.run(
        [sys.executable, str(search_script), "pip install timeout", "--remote", "--json"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, f"CLI returned {result.returncode}: {result.stderr[:400]}"
    data = json.loads(result.stdout)
    assert isinstance(data, list), f"expected a JSON array, got {type(data)}: {result.stdout[:200]}"


@needs_remote
def test_search_returns_results():
    """Basic search should return results for known topics (live endpoint)."""
    result = _mcp_call("misakanet_search", {"query": "git push"})
    results = result.get("results") or []
    assert results, f"no results for 'git push': {result}"


def test_search_returns_results_locally(monkeypatch):
    """Basic search should return results for known topics (in-process handler)."""
    monkeypatch.syspath_prepend(str(REPO_ROOT))

    from misakanet.server.handlers.search import handle_search

    result = handle_search({"query": "git push"})
    results = result.get("results") or []
    assert results, f"no results for 'git push': {result}"
    first = results[0]
    assert first.get("id"), f"the top hit has no id: {first}"
    assert "score" in first, f"the top hit is not ranked (no score): {first}"


def main():
    parser = argparse.ArgumentParser(description="E2E MCP pipeline tests")
    parser.add_argument("--remote", help="MCP endpoint URL for remote testing")
    parser.add_argument("--local", action="store_true", help="Test against local server")
    args = parser.parse_args()

    os.environ["MISAKANET_REMOTE_TEST"] = "1"
    if args.remote:
        os.environ["MISAKANET_MCP_URL"] = args.remote
    elif args.local:
        os.environ["MISAKANET_MCP_URL"] = "http://127.0.0.1:8787/mcp"

    # Kept for the `python tests/test_e2e_mcp_pipeline.py` entry point; pytest is
    # the supported runner (and the name pytest actually collects).
    return pytest.main(["-q", str(Path(__file__))])


if __name__ == "__main__":
    sys.exit(main())
