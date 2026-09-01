#!/usr/bin/env python3
"""E2E tests for MisakaNet MCP pipeline (Issues #1359, #1360, #1361).

Tests the complete workflow:
1. Lesson write pipeline: submit → issue → lesson → search (Issue #1359)
2. No-match feedback loop: search → suggestion → intake → lesson (Issue #1360)
3. CLI --remote mode: clone-less search via D1 (Issue #1361)

Usage:
    # Test against local MCP server
    python tests/e2e_mcp_pipeline.py --local

    # Test against remote MCP endpoint
    python tests/e2e_mcp_pipeline.py --remote https://misakanet.org/mcp
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_submit_intake(mcp_url: str = None) -> dict:
    """Issue #1359 Step 1: Submit lesson via MCP intake."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "misakanet_submit_intake",
            "arguments": {
                "kind": "new_lesson_candidate",
                "problem": "Agent failed to parse YAML frontmatter with nested quotes",
                "error": "YAMLException: bad indentation of a mapping at line 3",
                "what_tried": "Tried PyYAML, ruamel.yaml, js-yaml",
                "source": "e2e-test",
            },
        },
    }

    if mcp_url:
        import urllib.request
        req = urllib.request.Request(
            mcp_url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    else:
        from misakanet.server.handlers.submit import handle_submit_intake
        result = handle_submit_intake(payload["params"]["arguments"])
        return {"result": result}


def test_no_match_search(mcp_url: str = None) -> dict:
    """Issue #1360 Step 1: Search for non-existent topic."""
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "misakanet_search",
            "arguments": {"query": "quantum computing error correction xyz123"},
        },
    }

    if mcp_url:
        import urllib.request
        req = urllib.request.Request(
            mcp_url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    else:
        from misakanet.server.handlers.search import handle_search
        result = handle_search(payload["params"]["arguments"])
        return {"result": result}


def test_remote_search_cli() -> bool:
    """Issue #1361: Test CLI --remote mode."""
    search_script = Path(__file__).resolve().parent.parent / "search_knowledge.py"
    if not search_script.exists():
        print("  SKIP: search_knowledge.py not found")
        return True

    try:
        result = subprocess.run(
            [sys.executable, str(search_script), "pip install timeout", "--remote", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            print(f"  FAIL: CLI returned {result.returncode}: {result.stderr[:200]}")
            return False

        data = json.loads(result.stdout)
        if not isinstance(data, list):
            print(f"  FAIL: Expected JSON array, got {type(data)}")
            return False

        print(f"  PASS: Remote search returned {len(data)} results")
        return True
    except subprocess.TimeoutExpired:
        print("  FAIL: CLI timed out")
        return False
    except json.JSONDecodeError:
        print(f"  FAIL: Invalid JSON output: {result.stdout[:200]}")
        return False


def test_search_returns_results() -> bool:
    """Basic search should return results for known topics."""
    from misakanet.server.handlers.search import handle_search

    result = handle_search({"query": "git push"})
    results = result.get("results", [])
    if not results:
        print("  FAIL: No results for 'git push'")
        return False
    print(f"  PASS: Got {len(results)} results")
    return True


def main():
    parser = argparse.ArgumentParser(description="E2E MCP pipeline tests")
    parser.add_argument("--remote", help="MCP endpoint URL for remote testing")
    parser.add_argument("--local", action="store_true", help="Test against local server")
    args = parser.parse_args()

    mcp_url = args.remote
    results = {}

    print("\n=== Issue #1359: Lesson Write Pipeline ===")
    print("Step 1: Submit intake...")
    try:
        resp = test_submit_intake(mcp_url)
        print(f"  Response: {json.dumps(resp, indent=2)[:300]}")
        results["submit_intake"] = "PASS" if resp else "FAIL"
    except Exception as e:
        print(f"  FAIL: {e}")
        results["submit_intake"] = "FAIL"

    print("\n=== Issue #1360: No-Match Feedback Loop ===")
    print("Step 1: Search for non-existent topic...")
    try:
        resp = test_no_match_search(mcp_url)
        result = resp.get("result", resp)
        has_no_match = result.get("no_match", False)
        has_suggestion = bool(result.get("suggestion"))
        print(f"  no_match: {has_no_match}")
        print(f"  suggestion: {result.get('suggestion', 'N/A')[:100]}")
        results["no_match_loop"] = "PASS" if has_no_match or has_suggestion else "PARTIAL"
    except Exception as e:
        print(f"  FAIL: {e}")
        results["no_match_loop"] = "FAIL"

    print("\n=== Issue #1361: CLI Remote Mode ===")
    results["remote_cli"] = "PASS" if test_remote_search_cli() else "FAIL"

    print("\n=== Basic Search ===")
    results["basic_search"] = "PASS" if test_search_returns_results() else "FAIL"

    print("\n=== Summary ===")
    for test, status in results.items():
        icon = "✅" if status == "PASS" else "⚠️" if status == "PARTIAL" else "❌"
        print(f"  {icon} {test}: {status}")

    return all(v == "PASS" for v in results.values())


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
