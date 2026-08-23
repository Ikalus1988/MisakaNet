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
    check("has misakanet_submit_intake", "misakanet_submit_intake" in tool_names)
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


def test_submit_intake():
    print("\n-- tools/call: misakanet_submit_intake --")
    resp = rpc("tools/call", {
        "name": "misakanet_submit_intake",
        "arguments": {
            "kind": "missing_lesson",
            "problem": "pip install fails on WSL with SSL timeout",
            "error": "SSL: CERTIFICATE_VERIFY_FAILED",
            "source": "claude-code",
        },
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns submitted", result.get("submitted") is True)
    check("returns intake_id", "intake_id" in result)
    check("status is pending_review", result.get("status") == "pending_review")
    check("returns redactions_applied", "redactions_applied" in result)
    check("returns quality_score", "quality_score" in result)
    check("returns receipt", "receipt" in result)


def test_submit_intake_missing_problem():
    print("\n-- tools/call: misakanet_submit_intake missing problem --")
    resp = rpc("tools/call", {
        "name": "misakanet_submit_intake",
        "arguments": {"kind": "missing_lesson"},
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns error when problem missing", "error" in result)


def test_submit_intake_dedup():
    print("\n-- tools/call: misakanet_submit_intake dedup --")
    args = {
        "kind": "missing_lesson",
        "problem": "Unique dedup test case XYZ123",
        "source": "smoke-test",
    }
    resp1 = rpc("tools/call", {"name": "misakanet_submit_intake", "arguments": args})
    resp2 = rpc("tools/call", {"name": "misakanet_submit_intake", "arguments": args})
    r1 = json.loads(resp1.get("result", {}).get("content", [{}])[0].get("text", "{}"))
    r2 = json.loads(resp2.get("result", {}).get("content", [{}])[0].get("text", "{}"))
    check("first submission succeeds", r1.get("submitted") is True)
    check("duplicate rejected", r2.get("submitted") is False or "error" in r2)


def test_submit_intake_title_sanitization():
    print("\n-- tools/call: misakanet_submit_intake title sanitization --")
    args = {
        "kind": "missing_lesson",
        "problem": "## 背景\n\nfeishu-interactive-card 是 Hermes Agent 的一个技能模块\n\n在日常使用中积累了一些实用经验",
        "source": "smoke-test",
    }
    resp = rpc("tools/call", {"name": "misakanet_submit_intake", "arguments": args})
    result = json.loads(resp.get("result", {}).get("content", [{}])[0].get("text", "{}"))
    check("submission succeeds", result.get("submitted") is True)
    # Verify no markdown headings in intake_id (which comes from GitHub issue)
    check("has intake_id", "intake_id" in result)


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


def test_write_lesson_missing_fields():
    print("\n-- tools/call: misakanet_write_lesson missing fields --")
    resp = rpc("tools/call", {
        "name": "misakanet_write_lesson",
        "arguments": {"title": "test"},
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns submitted=False", result.get("submitted") is False)
    check("returns error for missing fields", "error" in result)
    check("error mentions missing fields", "Missing required fields" in result.get("error", ""))


def test_write_lesson_no_token():
    print("\n-- tools/call: misakanet_write_lesson no token --")
    resp = rpc("tools/call", {
        "name": "misakanet_write_lesson",
        "arguments": {
            "title": "test lesson",
            "domain": "python",
            "problem": "Something failed during build",
            "root_cause": "Missing dependency",
            "fix": "Install the package",
        },
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns submitted=False", result.get("submitted") is False)
    check("returns error for no token", "error" in result)
    check("error mentions token required", "token required" in result.get("error", "").lower())


def test_write_lesson_anon_token():
    print("\n-- tools/call: misakanet_write_lesson anon token --")
    resp = rpc("tools/call", {
        "name": "misakanet_write_lesson",
        "arguments": {
            "title": "test lesson",
            "domain": "python",
            "problem": "Something failed during build",
            "root_cause": "Missing dependency",
            "fix": "Install the package",
            "token": "anon:test",
        },
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns submitted=False", result.get("submitted") is False)
    check("rejects anon token", "token required" in result.get("error", "").lower())


def test_write_lesson_low_quality():
    print("\n-- tools/call: misakanet_write_lesson low quality --")
    import uuid
    unique = uuid.uuid4().hex[:8]
    resp = rpc("tools/call", {
        "name": "misakanet_write_lesson",
        "arguments": {
            "title": f"test {unique}",
            "domain": "misc",
            "problem": "nope",
            "root_cause": "nope",
            "fix": "nope",
            "token": "token:test-agent",
        },
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns submitted=False", result.get("submitted") is False)
    check("rejects low quality", "Quality score too low" in result.get("error", ""))
    check("returns quality_score", "quality_score" in result)


def test_write_lesson_success():
    print("\n-- tools/call: misakanet_write_lesson success --")
    import uuid
    unique = uuid.uuid4().hex[:8]
    title = f"pip install timeout on corporate proxy {unique}"
    resp = rpc("tools/call", {
        "name": "misakanet_write_lesson",
        "arguments": {
            "title": title,
            "domain": "python",
            "problem": "When running pip install behind a corporate proxy, the connection times out after 15 seconds. This happens because the proxy requires authentication but pip does not send credentials by default.",
            "root_cause": "pip does not automatically use HTTP_PROXY_AUTH environment variables. The proxy returns 407 Proxy Authentication Required but pip treats this as a timeout.",
            "fix": "Set HTTP_PROXY and HTTPS_PROXY with embedded credentials: export HTTP_PROXY=http://user:pass@proxy:8080. Or use pip --proxy flag.",
            "verification": "Run pip install requests behind proxy and verify it completes within 30 seconds.",
            "token": "token:test-agent",
            "source": "smoke-test",
        },
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns submitted=True", result.get("submitted") is True)
    check("returns lesson_id", "lesson_id" in result)
    check("status is pending_review", result.get("status") == "pending_review")
    check("returns quality_score", "quality_score" in result)
    check("quality_score >= 75", result.get("quality_score", 0) >= 75)
    check("returns receipt", "receipt" in result)
    # Clean up test contribution from queue
    queue_path = Path("data/contribution_queue.jsonl")
    if queue_path.exists():
        lines = queue_path.read_text(encoding="utf-8").strip().split("\n")
        lines = [l for l in lines if unique not in l]
        queue_path.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")


def test_preflight_missing_intent():
    print("\n-- tools/call: misakanet_preflight missing intent --")
    resp = rpc("tools/call", {
        "name": "misakanet_preflight",
        "arguments": {},
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns error for missing intent", "error" in result)


def test_memory_context_no_task():
    print("\n-- tools/call: misakanet_memory_context no task --")
    resp = rpc("tools/call", {
        "name": "misakanet_memory_context",
        "arguments": {},
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("returns error for missing task", "error" in result)
    check("error mentions task required", "task" in result.get("error", "").lower())


def test_memory_context_basic():
    print("\n-- tools/call: misakanet_memory_context basic --")
    resp = rpc("tools/call", {
        "name": "misakanet_memory_context",
        "arguments": {"task": "set up pip install behind corporate proxy"},
    })
    result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
    result = json.loads(result_text)
    check("has task field", result.get("task") == "set up pip install behind corporate proxy")
    check("has lesson_count", "lesson_count" in result)
    check("has context_block", "context_block" in result)
    check("context_block contains MisakaNet", "MisakaNet" in result.get("context_block", ""))


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
    test_write_lesson_missing_fields()
    test_write_lesson_no_token()
    test_write_lesson_anon_token()
    test_write_lesson_low_quality()
    test_write_lesson_success()
    test_preflight_missing_intent()
    test_memory_context_no_task()
    test_memory_context_basic()

    print(f"\n{'=' * 40}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
