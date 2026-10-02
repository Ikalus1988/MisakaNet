#!/usr/bin/env python3
"""MCP first-call user journey -- the deployed endpoint, as an agent sees it (closes #830).

This file used to be called ``tests/mcp_first_call_journey.py``. That name is not
collected by pytest (default pattern ``test_*.py``), so the journey had never run
in a gate. Renaming it exposed two defects that the old shape hid:

* it sent neither ``Origin`` nor ``MCP-Protocol-Version``, which the live server
  requires -- every step returned **HTTP 403 Forbidden**;
* it reported step outcomes through ``print()`` and ``return``\\ ed a bool, and
  pytest discards a test function's return value, so a 1/5-failing run was
  reported as PASS. Measured before the fix: ``RESULTS: 1/5 passed`` from the
  script, ``1 passed`` from pytest.

The journey tests the *deployed* service, so it is opt-in, following
``tests/test_issue_1361_remote_search.py``::

    MISAKANET_REMOTE_TEST=1 pytest -q tests/test_mcp_first_call_journey.py
    python tests/test_mcp_first_call_journey.py     # same journey, standalone
"""

import json
import os
import ssl
import urllib.request

import pytest

ENDPOINT = os.getenv("MISAKANET_MCP_URL", "https://misakanet.org/mcp")

# Required by the live server: a missing/invalid Origin is answered with 403, a
# missing protocol version breaks the MCP handshake, and the edge also 403s a
# request carrying Python-urllib's or Java's default User-Agent (measured
# 2026-10-02; curl/Mozilla/absent are answered normally), so send an explicit one.
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "MCP-Protocol-Version": "2025-06-18",
    "Origin": "https://misakanet.org",
    "User-Agent": "misakanet-e2e/1.0",
}

pytestmark = pytest.mark.skipif(
    os.getenv("MISAKANET_REMOTE_TEST") != "1",
    reason="set MISAKANET_REMOTE_TEST=1 to run the live first-call journey",
)


def rpc(method: str, params: dict | None = None, request_id: int = 1) -> dict:
    """POST one JSON-RPC message and return the decoded response body."""
    body = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        body["params"] = params
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode(),
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=15) as resp:
        return json.loads(resp.read())


def test_initialize_reports_server_info():
    """Step 1-2: the endpoint completes an MCP handshake."""
    resp = rpc(
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "journey-test", "version": "1.0.0"},
        },
    )
    assert "error" not in resp, f"initialize failed: {resp['error']}"
    server_info = resp.get("result", {}).get("serverInfo", {})
    assert server_info.get("name"), f"initialize returned no serverInfo.name: {resp}"


def test_tools_list_exposes_the_public_tools():
    """Step 3-4: an agent can discover the tools it is meant to call."""
    resp = rpc("tools/list", {}, request_id=2)
    assert "error" not in resp, f"tools/list failed: {resp['error']}"
    tools = [t["name"] for t in resp.get("result", {}).get("tools", [])]
    missing = {"misakanet_search", "misakanet_get_lesson", "misakanet_submit_intake"} - set(tools)
    assert not missing, f"tools/list is missing {sorted(missing)}; got {tools}"


def test_first_search_call_returns_lesson_payload():
    """Step 5-6: the first call an agent makes actually returns knowledge.

    The tool name is asserted, not assumed: this step used to call
    ``misaka_search`` (no such tool) and check only ``len(content) > 50``, which
    an error string satisfies -- a passing test for a broken call.
    """
    resp = rpc(
        "tools/call",
        {"name": "misakanet_search", "arguments": {"query": "git push", "detail": "compact"}},
        request_id=3,
    )
    assert "error" not in resp, f"tools/call failed: {resp['error']}"
    content = resp.get("result", {}).get("content", [])
    assert content, f"tools/call returned no content: {resp}"
    payload = json.loads(content[0]["text"])
    results = payload.get("results") or []
    assert results, f"the search tool returned no lessons for a known topic: {payload}"


def test_cors_preflight_allows_agent_origins():
    """Step 7: a browser-side agent can preflight the endpoint."""
    req = urllib.request.Request(ENDPOINT, method="OPTIONS")
    for key, value in HEADERS.items():
        req.add_header(key, value)
    req.add_header("Access-Control-Request-Method", "POST")
    with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=10) as resp:
        allowed_origin = resp.getheader("Access-Control-Allow-Origin", "")
        allowed_headers = resp.getheader("Access-Control-Allow-Headers", "")
    assert allowed_origin in ("*", "https://misakanet.org"), (
        f"preflight did not allow the canonical origin: {allowed_origin!r}"
    )
    assert "MCP-Protocol-Version" in allowed_headers, (
        f"preflight does not allow MCP-Protocol-Version: {allowed_headers!r}"
    )


def main() -> int:
    return pytest.main(["-q", os.path.abspath(__file__)])


if __name__ == "__main__":
    raise SystemExit(main())
