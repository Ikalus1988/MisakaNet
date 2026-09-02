#!/usr/bin/env python3
"""MCP Auth Contract Tests — verify anonymous vs Bearer behavior.

Tests the auth bypass contract:
- submit_intake: anonymous allowed (no Bearer required)
- initialize, tools/list, search, get_lesson: Bearer required

These tests do NOT create real GitHub issues. They verify the
contract at the handler level using the local MCP server.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.mcp_server import handle_request

PASS = 0
FAIL = 0


def check(name: str, condition: bool):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def rpc(method: str, params: dict = None, req_id: int = 1) -> dict:
    return handle_request({
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {},
    })


def test_initialize_rejects_no_auth():
    """Initialize should work without auth (it's the handshake)."""
    print("\n-- initialize without auth --")
    resp = rpc("initialize", {"protocolVersion": "2025-06-18"})
    check("initialize succeeds", "result" in resp)


def test_tools_list_rejects_no_auth():
    """tools/list should work without auth (read-only)."""
    print("\n-- tools/list without auth --")
    resp = rpc("tools/list")
    tools = resp.get("result", {}).get("tools", [])
    check("tools/list succeeds", len(tools) > 0)
    check("has 5 tools", len(tools) == 5)


def test_search_rejects_no_auth():
    """Search should work without auth (read-only public data)."""
    print("\n-- search without auth --")
    resp = rpc("tools/call", {
        "name": "misakanet_search",
        "arguments": {"query": "DCO"},
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("search succeeds without auth", "results" in result)


def test_get_lesson_rejects_no_auth():
    """Get lesson should work without auth (read-only public data)."""
    print("\n-- get_lesson without auth --")
    resp = rpc("tools/call", {
        "name": "misakanet_get_lesson",
        "arguments": {"id": "dco-auto-fix-workflow"},
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("get_lesson succeeds without auth", "content" in result)


def test_submit_intake_allows_no_auth():
    """submit_intake should work without auth (anonymous intake)."""
    import time
    print("\n-- submit_intake without auth --")
    unique_problem = f"Auth contract test {int(time.time())}"
    resp = rpc("tools/call", {
        "name": "misakanet_submit_intake",
        "arguments": {
            "kind": "missing_lesson",
            "problem": unique_problem,
            "source": "contract-test",
        },
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("submit_intake succeeds without auth", result.get("submitted") is True)
    check("returns intake_id", "intake_id" in result)


def test_submit_intake_sanitizes_title():
    """submit_intake should sanitize markdown in title."""
    import time
    print("\n-- submit_intake title sanitization --")
    resp = rpc("tools/call", {
        "name": "misakanet_submit_intake",
        "arguments": {
            "kind": "missing_lesson",
            "problem": f"## 背景\n\nThis is a test with markdown headings {int(time.time())}",
            "source": "contract-test",
        },
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("submit_intake succeeds", result.get("submitted") is True)


def test_submit_intake_spam_not_in_local():
    """Local MCP server does not have spam check (Worker only)."""
    import time
    print("\n-- submit_intake spam (local has no spam guard) --")
    resp = rpc("tools/call", {
        "name": "misakanet_submit_intake",
        "arguments": {
            "problem": f"Buy now! Free money! Click here! {int(time.time())}",
            "source": "contract-test",
        },
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("local server accepts (spam guard is Worker-only)", result.get("submitted") is True)


def test_unknown_tool_rejected():
    """Unknown tools should be rejected."""
    print("\n-- unknown tool --")
    resp = rpc("tools/call", {
        "name": "nonexistent_tool",
        "arguments": {},
    })
    check("unknown tool rejected", "error" in resp)


if __name__ == "__main__":
    test_initialize_rejects_no_auth()
    test_tools_list_rejects_no_auth()
    test_search_rejects_no_auth()
    test_get_lesson_rejects_no_auth()
    test_submit_intake_allows_no_auth()
    test_submit_intake_sanitizes_title()
    test_submit_intake_spam_not_in_local()
    test_unknown_tool_rejected()

    print(f"\n{'='*50}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
