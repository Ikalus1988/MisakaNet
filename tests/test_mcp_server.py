#!/usr/bin/env python3
"""Smoke test for MisakaNet MCP Server.

Tests the JSON-RPC handlers directly (no subprocess needed).

Usage:
    python3 tests/test_mcp_server.py
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.mcp_server import TOOLS, handle_request

PASS = 0
FAIL = 0


def rpc(method: str, params: dict = None, req_id: int = 1) -> dict:
    """Send a JSON-RPC request to the handler."""
    return handle_request({
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {},
    })


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}{': ' + detail if detail else ''}")


def test_initialize():
    print("\n-- initialize --")
    resp = rpc("initialize")
    result = resp.get("result", {})
    check("has protocolVersion", "protocolVersion" in result)
    check("has serverInfo.name", result.get("serverInfo", {}).get("name") == "misakanet")
    expected_version = re.search(
        r'^version\s*=\s*["\']([^"\']+)["\']',
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8", errors="replace"),
        re.MULTILINE,
    ).group(1)
    check(
        "has current serverInfo.version",
        result.get("serverInfo", {}).get("version") == expected_version,
    )
    check("has capabilities.tools", "tools" in result.get("capabilities", {}))


def test_tools_list():
    print("\n-- tools/list --")
    resp = rpc("tools/list")
    tools = resp.get("result", {}).get("tools", [])
    tool_names = {t["name"] for t in tools}
    check("has misakanet_search", "misakanet_search" in tool_names)
    check("has misakanet_get_lesson", "misakanet_get_lesson" in tool_names)
    check("has misakanet_submit_usage", "misakanet_submit_usage" in tool_names)
    check("search requires query", "query" in tools[0]["inputSchema"]["required"])


def test_tool_descriptions_are_agent_friendly():
    print("\n-- tool descriptions --")
    required_terms = [
        "Input semantics",
        "Output schema",
        "Error cases",
        "Side effects",
        "Auth",
        "Rate limits",
    ]
    for tool in TOOLS:
        desc = tool.get("description", "")
        missing = [term for term in required_terms if term not in desc]
        check(f"{tool['name']} describes operating contract", not missing, f"missing: {missing}")


def test_search():
    print("\n-- tools/call: misakanet_search --")
    resp = rpc("tools/call", {
        "name": "misakanet_search",
        "arguments": {"query": "CI pipeline", "top": 3},
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)

    if "error" in result:
        print(f"  WARN Search unavailable: {result['error']}")
        print("     (Run: python3 scripts/build_sag_index.py)")
        return

    results = result.get("results", [])
    check("returns results list", isinstance(results, list))
    if results:
        first = results[0]
        check("result has path", "path" in first, f"keys: {list(first.keys())}")
        check("result has status", "status" in first)
        check("result has score/rank", "score" in first or "rank" in first)
        check("no draft results", first.get("status") != "draft")
    else:
        print("  WARN No results returned (index may be empty)")


def test_get_lesson():
    print("\n-- tools/call: misakanet_get_lesson --")
    # Find a real lesson file
    lessons_dir = REPO_ROOT / "lessons"
    sample = None
    for subdir in ["core", "contrib"]:
        candidates = list((lessons_dir / subdir).glob("*.md")) if (lessons_dir / subdir).exists() else []
        if candidates:
            sample = candidates[0]
            break

    if not sample:
        print("  WARN No lesson files found, skipping")
        return

    lesson_id = sample.stem
    resp = rpc("tools/call", {
        "name": "misakanet_get_lesson",
        "arguments": {"id": lesson_id},
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)

    check("returns path", "path" in result, f"keys: {list(result.keys())}")
    check("returns content", "content" in result)
    check("content is non-empty", len(result.get("content", "")) > 10)


def test_submit_usage():
    print("\n-- tools/call: misakanet_submit_usage --")
    resp = rpc("tools/call", {
        "name": "misakanet_submit_usage",
        "arguments": {"lesson_id": "test-lesson", "tool": "smoke-test", "outcome": "solved"},
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns status", "status" in result)
    check("status is logged", result.get("status") == "logged")


def test_unknown_tool():
    print("\n-- error handling --")
    resp = rpc("tools/call", {
        "name": "nonexistent_tool",
        "arguments": {},
    })
    check("returns error for unknown tool", "error" in resp)
    check("error code is -32601", resp.get("error", {}).get("code") == -32601)


def test_no_drafts_in_search():
    print("\n-- search scope: no drafts --")
    resp = rpc("tools/call", {
        "name": "misakanet_search",
        "arguments": {"query": "draft test lesson", "top": 10},
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)

    if "error" in result:
        print("  WARN Search unavailable, skipping draft check")
        return

    results = result.get("results", [])
    draft_count = sum(1 for r in results if r.get("status") == "draft")
    check("no drafts in results", draft_count == 0, f"found {draft_count} drafts")


def test_usage_status():
    print("\n-- tools/call: misakanet_usage_status --")
    resp = rpc("tools/call", {
        "name": "misakanet_usage_status",
        "arguments": {"user": "anon:test-mcp"},
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns user", "user" in result)
    check("returns free_reads_used", "free_reads_used" in result)
    check("returns free_reads_limit", "free_reads_limit" in result)
    check("returns free_reads_remaining", "free_reads_remaining" in result)
    check("returns credits", "credits" in result)
    check("returns is_registered", "is_registered" in result)


if __name__ == "__main__":
    print("MisakaNet MCP Server smoke test")
    test_initialize()
    test_tools_list()
    test_tool_descriptions_are_agent_friendly()
    test_search()
    test_get_lesson()
    test_submit_usage()
    test_unknown_tool()
    test_no_drafts_in_search()
    test_usage_status()

    print(f"\n{'=' * 40}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
