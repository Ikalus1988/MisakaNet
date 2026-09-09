#!/usr/bin/env python3
"""Verify MisakaNet's Glama MCP listing shows the correct tools.

Checks:
1. Glama API returns non-empty tools list
2. Tool count matches local MCP_TOOLS definition
3. Key tools (search, get_lesson, submit_intake) are present

Usage:
  python3 scripts/verify-glama-listing.py [--json]

Exit codes:
  0 — listing is healthy
  1 — listing has issues (details in output)
  2 — could not reach Glama API

Issue #1063
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

GLAMA_API = "https://glama.ai/api/mcp/v1/servers/Ikalus1988/MisakaNet"
GLAMA_PAGE = "https://glama.ai/mcp/servers/Ikalus1988/MisakaNet"
WORKER = Path(__file__).resolve().parent.parent / "workers" / "register-proxy-sw.js"

EXPECTED_CORE_TOOLS = [
    "misakanet_search",
    "misakanet_get_lesson",
    "misakanet_submit_intake",
]


def get_local_tools() -> list[str]:
    """Extract tool names from register-proxy-sw.js MCP_TOOLS definition."""
    text = WORKER.read_text(encoding="utf-8")
    return re.findall(r'name:\s*"misakanet_(\w+)"', text)


def get_glama_tools() -> dict:
    """Fetch Glama API listing. Falls back to web page scrape on API failure.

    Returns {tools: [...], error?: str, source: "api"|"page"}.
    """
    # Try API first
    try:
        req = urllib.request.Request(GLAMA_API, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            tools = data.get("tools", [])
            if tools:
                return {"tools": tools, "raw": data, "source": "api"}
    except Exception:
        pass

    # Fallback: scrape web page for tool names
    try:
        req = urllib.request.Request(GLAMA_PAGE, headers={"Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            # Glama renders tool names in the page; extract misakanet_* patterns
            # Filter out double-underscore and empty matches
            tool_names = [t for t in re.findall(r'misakanet_([a-z]\w*)', html)]
            tools = [{"name": f"misakanet_{t}"} for t in sorted(set(tool_names))]
            if tools:
                return {"tools": tools, "source": "page"}
            return {"tools": [], "error": "no tools found in page", "source": "page"}
    except Exception as e:
        return {"tools": [], "error": str(e), "source": "failed"}


def main():
    as_json = "--json" in sys.argv

    local_tools = get_local_tools()
    glama = get_glama_tools()

    glama_names = [t.get("name", "") for t in glama.get("tools", [])]
    missing_core = [t for t in EXPECTED_CORE_TOOLS if t not in glama_names]

    local_set = {f"misakanet_{t}" for t in local_tools}
    glama_set = set(glama_names)
    stale_tools = sorted(glama_set - local_set - {""})
    new_tools = sorted(local_set - glama_set)

    result = {
        "local_tool_count": len(local_tools),
        "glama_tool_count": len(glama_names),
        "glama_tools": glama_names,
        "missing_core_tools": missing_core,
        "stale_on_glama": stale_tools,
        "missing_from_glama": new_tools,
        "glama_error": glama.get("error"),
        "glama_source": glama.get("source"),
        "healthy": len(glama_names) > 0 and len(missing_core) == 0
                   and len(stale_tools) == 0 and len(new_tools) == 0
                   and "error" not in glama,
    }

    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Local MCP tools: {len(local_tools)} ({', '.join(local_tools)})")
        print(f"Glama tools:     {len(glama_names)}")
        if glama_names:
            for name in glama_names:
                print(f"  - {name}")
        if glama.get("error"):
            print(f"Glama API error: {glama['error']}")
        if missing_core:
            print(f"Missing core tools: {missing_core}")
        if stale_tools:
            print(f"Stale on Glama (removed locally): {stale_tools}")
        if new_tools:
            print(f"Missing from Glama (added locally): {new_tools}")
        if result["healthy"]:
            print("✅ Glama listing is healthy")
        else:
            print("❌ Glama listing has issues")

    sys.exit(0 if result["healthy"] else (2 if glama.get("error") else 1))


if __name__ == "__main__":
    main()