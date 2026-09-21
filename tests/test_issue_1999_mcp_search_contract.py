#!/usr/bin/env python3
"""The MCP search surface broke four ways at once (found 2026-09-21).

An integration pass wired the local stdio server into every agent harness on the
machine, then ran the documented flow against it: search, then read the lesson
the search returned. Four separate defects surfaced, each invisible because
nothing tested the path end to end:

1. **Compact results carried no usable identifier.** The SAG-Lite backend returns
   ``path`` and no ``id`` (its ``id`` column is a SQLite rowid). The compact
   transform copied ``id`` — empty for SAG — and dropped ``path`` and ``status``.
   The documented next step, ``misakanet_get_lesson``, accepts only path or id,
   so the flow dead-ended on ``{"error": "path or id is required"}`` against the
   default backend while working against the hosted worker (which does set id).

2. **Drafts leaked into search results.** ``docs/mcp.md`` promises "Drafts are
   excluded to avoid surfacing unverified content" and the BM25 engine enforces
   it (``_search_cached`` filters ``is_draft``), but the SAG-Lite and fallback
   backends did not, so the same query surfaced drafts or not depending on which
   backend answered.

3. **Unescaped query text crashed the server.** FTS5 parses MATCH as an
   expression language, so ``, ``:``, ``-``, ``*``, quotes and the AND/OR/NOT
   operators are syntax. Nine of ten realistic error strings killed the process
   before it could answer — and because the request loop had no guard, the whole
   session died rather than the single call.

4. **``misakanet_memory_context`` described only its parameters**, not its
   operating contract, unlike the other eight tools.

These tests pin all four. They are behavioural where behaviour is the contract
(1-3) and structural only where the contract *is* the text (4).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402

# Imported after the sys.path insert above, which is what makes them resolvable.
from misakanet.server.handlers.get_lesson import handle_get_lesson  # noqa: E402
from misakanet.server.handlers.search import handle_search  # noqa: E402

# Real error strings, not synthetic ones: these are the shapes an agent actually
# pastes into a search box, and the ones that used to crash the server.
REAL_ERROR_STRINGS = [
    "ModuleNotFoundError: No module named misakanet_core",
    "sqlite3.OperationalError: database is locked",
    "docker multi-stage build OOM",
    "GH013: Secret scanning found",
    "[WinError 10061] connection refused",
    "error: cannot find module",
    "Permission denied (publickey)",
    "fatal: not a git repository",
    "npm ERR! code EACCES",
    "pip install ReadTimeoutError",
]


def test_compact_results_are_resolvable_by_get_lesson():
    """A compact result must carry an id or path that get_lesson accepts."""
    resp = handle_search({"query": "database is locked", "top": 3})
    results = resp.get("results", [])
    assert results, "search returned nothing; the corpus or index is missing"

    first = results[0]
    identifier = first.get("id") or first.get("path")
    assert identifier, (
        "compact result carries neither id nor path, so the documented "
        f"search -> get_lesson flow cannot continue: keys={list(first.keys())}"
    )

    fetched = handle_get_lesson({"id": first.get("id")} if first.get("id")
                                else {"path": first["path"]})
    assert "error" not in fetched, (
        f"get_lesson rejected the identifier a search just returned: {fetched}"
    )
    assert fetched.get("content")


def test_every_detail_level_keeps_the_result_actionable():
    """compact/summary/full must all expose an identifier and a status."""
    for detail in ("compact", "summary", "full"):
        resp = handle_search({"query": "pip install timeout", "top": 2, "detail": detail})
        results = resp.get("results", [])
        assert results, f"no results at detail={detail}"
        for r in results:
            assert r.get("id") or r.get("path"), (
                f"detail={detail} result has no id or path: keys={list(r.keys())}"
            )
            assert r.get("status"), (
                f"detail={detail} result has no status, so a caller cannot tell "
                f"a draft from a published lesson: keys={list(r.keys())}"
            )


def test_drafts_are_never_returned():
    """docs/mcp.md: drafts are excluded from search results."""
    # Queries aimed squarely at known draft titles.
    for query in (
        "Benchmark Honesty Distinguishing Simulated vs Real Results",
        "Search Quota Exhaustion Causes False Zero Results",
        "draft test lesson",
    ):
        resp = handle_search({"query": query, "top": 10, "detail": "full"})
        drafts = [r for r in resp.get("results", []) if r.get("status") == "draft"]
        assert not drafts, (
            f"draft lessons surfaced for {query!r}: "
            f"{[r.get('title') for r in drafts]}"
        )


def test_top_is_respected_after_draft_filtering():
    """Excluding drafts must not silently shrink the caller's result budget."""
    for top in (1, 2, 3):
        resp = handle_search({"query": "mcp server", "top": top})
        assert len(resp.get("results", [])) <= top, (
            f"top={top} returned more results than asked for"
        )


@pytest.mark.parametrize("query", REAL_ERROR_STRINGS)
def test_real_error_strings_do_not_crash_the_search_handler(query):
    """FTS5 syntax characters in real error text must not raise."""
    resp = handle_search({"query": query, "top": 3})
    assert "results" in resp or "error" in resp, resp


@pytest.mark.parametrize("query", REAL_ERROR_STRINGS)
def test_real_error_strings_do_not_kill_the_server_process(query):
    """The end-to-end contract: a bad query must not take the process down.

    This is the regression that mattered most — the failure mode was not a wrong
    answer but a dead session, which no handler-level test can catch.
    """
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "misakanet_search",
                    "arguments": {"query": query, "top": 3}}},
    ]
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "mcp_server.py")],
        input="\n".join(json.dumps(r) for r in requests) + "\n",
        capture_output=True, text=True, timeout=120,
    )
    assert "Traceback" not in proc.stderr, (
        f"server crashed on {query!r}:\n{proc.stderr[-800:]}"
    )
    answered = any(
        json.loads(line).get("id") == 2
        for line in proc.stdout.splitlines() if line.strip()
    )
    assert answered, f"server never answered the request for {query!r}"


def test_a_raising_handler_does_not_end_the_session():
    """A tool error must cost one call, not the whole stdio session."""
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        # Malformed argument types force the handler to raise.
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "misakanet_search",
                    "arguments": {"query": 12345, "top": "notanint"}}},
        # The next request must still be served by the same process.
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "misakanet_search",
                    "arguments": {"query": "database locked", "top": 2}}},
    ]
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "mcp_server.py")],
        input="\n".join(json.dumps(r) for r in requests) + "\n",
        capture_output=True, text=True, timeout=120,
    )
    ids = {}
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        ids[payload.get("id")] = "error" if "error" in payload else "result"
    assert ids.get(3) == "result", (
        f"the session did not survive the raising call: {ids}\n{proc.stderr[-500:]}"
    )


def test_memory_context_documents_its_operating_contract():
    """Every tool description states the same six contract sections."""
    from misakanet.server.tools import TOOLS

    required = [
        "Input semantics", "Output schema", "Error cases",
        "Side effects", "Auth", "Rate limits",
    ]
    tool = next(t for t in TOOLS if t["name"] == "misakanet_memory_context")
    missing = [term for term in required if term not in tool["description"]]
    assert not missing, f"misakanet_memory_context is missing: {missing}"
