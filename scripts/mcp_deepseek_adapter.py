#!/usr/bin/env python3
"""MisakaNet MCP Adapter for DeepSeekHarness.

Bridges MisakaNet's failure-memory tools to DeepSeekHarness's recovery contract.
This is a thin naming layer — all logic delegates to the existing MCP server.

Usage:
    # As MCP server (stdio transport)
    python3 scripts/mcp_deepseek_adapter.py

    # In DeepSeekHarness config:
    {
      "mcpServers": {
        "misakanet-recovery": {
          "command": "python3",
          "args": ["scripts/mcp_deepseek_adapter.py"]
        }
      }
    }

Tool mapping:
    misakanet.search          -> deepseek.recovery.search
    misakanet.get_lesson      -> deepseek.recovery.get_lesson
    misakanet.submit_usage    -> deepseek.recovery.submit_feedback
    misakanet.usage_status    -> deepseek.recovery.status
    (new)                     -> deepseek.recovery.doctor
    (new)                     -> deepseek.recovery.smoke
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ADAPTER_VERSION = "1.0.0"

# ── Import existing MCP handlers ──────────────────────────────────
sys.path.insert(0, str(REPO_ROOT))
from scripts.mcp_server import (
    handle_search,
    handle_get_lesson,
    handle_submit_usage,
    handle_usage_status,
    get_server_version,
)


# ── DeepSeekHarness-compatible tool definitions ───────────────────

TOOLS = [
    {
        "name": "deepseek.recovery.search",
        "description": (
            "Search MisakaNet's failure-lesson index for recovery guidance. "
            "Use when an error, exception, or failure occurs and you need "
            "a documented fix from real engineering sessions. "
            "Input: query (required), domain (optional), top (optional). "
            "Output: ranked lesson summaries with path, title, score."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Error message, keyword, or topic to search for",
                },
                "domain": {
                    "type": "string",
                    "description": "Optional domain filter (devops, python, rag, mcp, etc.)",
                },
                "top": {
                    "type": "integer",
                    "description": "Max results to return (default 5)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "deepseek.recovery.get_lesson",
        "description": (
            "Fetch a specific failure-recovery lesson by ID or path. "
            "Use after deepseek.recovery.search returns a match. "
            "Input: id or path (one required). "
            "Output: lesson content in markdown, truncated to 5000 chars."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Lesson ID (filename without .md)",
                },
                "path": {
                    "type": "string",
                    "description": "Lesson path relative to repo root",
                },
            },
        },
    },
    {
        "name": "deepseek.recovery.submit_feedback",
        "description": (
            "Record that a lesson helped with a failure. "
            "Use after applying a fix from a lesson. "
            "Input: lesson_id (required), outcome (solved/partial/not-helpful). "
            "Output: confirmation with lesson_id and status."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "lesson_id": {
                    "type": "string",
                    "description": "ID of the lesson that helped",
                },
                "outcome": {
                    "type": "string",
                    "enum": ["solved", "partial", "not-helpful"],
                    "description": "Outcome of applying the lesson",
                },
                "tool": {
                    "type": "string",
                    "description": "Calling tool name (default: deepseek-harness)",
                },
            },
            "required": ["lesson_id"],
        },
    },
    {
        "name": "deepseek.recovery.status",
        "description": (
            "Check MisakaNet recovery plugin status. "
            "Shows available lessons, search engine health, and usage quota. "
            "Input: none required. "
            "Output: status with lesson count, engine type, and quota."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "deepseek.recovery.doctor",
        "description": (
            "Health check for the MisakaNet recovery plugin. "
            "Verifies: data files exist, search engine is built, "
            "MCP server is reachable. "
            "Input: none required. "
            "Output: health status with checks and recommendations."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "deepseek.recovery.smoke",
        "description": (
            "Minimal smoke test: runs a search and lesson fetch. "
            "Use to verify the plugin works end-to-end. "
            "Input: none required. "
            "Output: pass/fail with timing and result counts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


# ── Handler implementations ───────────────────────────────────────

def handle_deepseek_search(args: dict) -> dict:
    """Delegate to misakanet.search with DeepSeekHarness naming."""
    try:
        result = handle_search(args)
    except Exception as e:
        # SAG-Lite FTS may fail on SQLite keywords (e.g. "off", "and")
        # Fall back to empty result with error info
        result = {
            "results": [],
            "source": "error",
            "error": str(e),
            "hint": "Search engine error — try a different query or rebuild index",
        }
    # Remap voice field for harness compatibility
    if "voice" in result:
        result["harness_voice"] = result.pop("voice")
    return result


def handle_deepseek_get_lesson(args: dict) -> dict:
    """Delegate to misakanet.get_lesson."""
    # Map id/path to misakanet format
    misakanet_args = {}
    if "id" in args:
        misakanet_args["id"] = args["id"]
    if "path" in args:
        misakanet_args["path"] = args["path"]
    return handle_get_lesson(misakanet_args)


def handle_deepseek_submit_feedback(args: dict) -> dict:
    """Delegate to misakanet.submit_usage with harness naming."""
    misakanet_args = {
        "lesson_id": args.get("lesson_id", ""),
        "tool": args.get("tool", "deepseek-harness"),
        "outcome": args.get("outcome", "unknown"),
    }
    return handle_submit_usage(misakanet_args)


def handle_deepseek_status(args: dict) -> dict:
    """Combined status: usage + search engine health."""
    usage = handle_usage_status({})

    # Check search engine
    engines = []
    try:
        from scripts.build_sag_index import search as sag_search
        sag_db = REPO_ROOT / "data" / "sag.db"
        if sag_db.exists():
            engines.append("sag-lite")
    except ImportError:
        pass

    try:
        from misakanet.search.engine import LESSONS
        engines.append("bm25")
    except ImportError:
        pass

    # Fallback always available
    lessons_json = REPO_ROOT / "data" / "lessons.json"
    if lessons_json.exists():
        engines.append("fallback")

    return {
        "plugin_version": ADAPTER_VERSION,
        "mcp_server_version": get_server_version(),
        "search_engines": engines,
        "active_engine": engines[0] if engines else "none",
        "usage": usage,
    }


def handle_deepseek_doctor(args: dict) -> dict:
    """Health check for the recovery plugin."""
    checks = []

    # Check data files
    lessons_json = REPO_ROOT / "data" / "lessons.json"
    checks.append({
        "name": "lessons.json",
        "status": "ok" if lessons_json.exists() else "missing",
        "path": str(lessons_json.relative_to(REPO_ROOT)),
    })

    sag_db = REPO_ROOT / "data" / "sag.db"
    checks.append({
        "name": "sag.db",
        "status": "ok" if sag_db.exists() else "missing",
        "path": str(sag_db.relative_to(REPO_ROOT)),
    })

    # Check lessons directory
    lessons_dir = REPO_ROOT / "lessons"
    lesson_count = 0
    if lessons_dir.exists():
        lesson_count = len(list(lessons_dir.rglob("*.md")))
    checks.append({
        "name": "lessons/",
        "status": "ok" if lesson_count > 0 else "empty",
        "lesson_count": lesson_count,
    })

    # Check search engine
    engine_status = "none"
    try:
        from scripts.build_sag_index import search as sag_search
        if sag_db.exists():
            engine_status = "sag-lite"
    except ImportError:
        pass
    try:
        from misakanet.search.engine import LESSONS
        engine_status = "bm25"
    except ImportError:
        pass
    checks.append({
        "name": "search_engine",
        "status": engine_status,
    })

    # Overall status
    failed = [c for c in checks if c["status"] in ("missing", "empty", "none")]
    overall = "healthy" if not failed else "degraded"

    return {
        "overall": overall,
        "checks": checks,
        "recommendation": (
            "Run: python3 scripts/build_sag_index.py" if engine_status == "none" else None
        ),
    }


def handle_deepseek_smoke(args: dict) -> dict:
    """Minimal smoke test: search + lesson fetch."""
    results = {}
    start = time.time()
    smoke_query = "DCO"

    # Test 1: Search
    try:
        search_result = handle_deepseek_search({"query": smoke_query, "top": 1, "detail": "full"})
        result_count = len(search_result.get("results", []))
        results["search"] = {
            "status": "ok" if result_count > 0 else "fail",
            "result_count": result_count,
            "source": search_result.get("source"),
        }
        if "error" in search_result:
            results["search"]["error"] = search_result["error"]
    except Exception as e:
        results["search"] = {"status": "fail", "error": str(e)}

    # Test 2: Get lesson (if search found one)
    if results["search"]["status"] == "ok" and results["search"]["result_count"] > 0:
        try:
            first_result = search_result["results"][0]
            lesson_path = first_result.get("path", "")
            if lesson_path:
                lesson_result = handle_deepseek_get_lesson({"path": lesson_path})
                results["get_lesson"] = {
                    "status": "ok" if "content" in lesson_result else "fail",
                    "content_length": len(lesson_result.get("content", "")),
                }
            else:
                results["get_lesson"] = {"status": "skip", "reason": "no path in search result"}
        except Exception as e:
            results["get_lesson"] = {"status": "fail", "error": str(e)}
    else:
        results["get_lesson"] = {"status": "skip", "reason": "search failed or no results"}

    elapsed = time.time() - start
    all_ok = all(r.get("status") in ("ok", "skip") for r in results.values())

    return {
        "overall": "pass" if all_ok else "fail",
        "elapsed_ms": round(elapsed * 1000),
        "tests": results,
    }


# ── MCP Server ────────────────────────────────────────────────────

def handle_request(request: dict) -> dict | None:
    """Handle a JSON-RPC request."""
    method = request.get("method", "")
    params = request.get("params", {})
    req_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "misakanet-deepseek-adapter",
                    "version": ADAPTER_VERSION,
                },
            },
        }

    elif method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        handlers = {
            "deepseek.recovery.search": handle_deepseek_search,
            "deepseek.recovery.get_lesson": handle_deepseek_get_lesson,
            "deepseek.recovery.submit_feedback": handle_deepseek_submit_feedback,
            "deepseek.recovery.status": handle_deepseek_status,
            "deepseek.recovery.doctor": handle_deepseek_doctor,
            "deepseek.recovery.smoke": handle_deepseek_smoke,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }

        result = handler(tool_args)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
            },
        }

    elif method == "notifications/initialized":
        return None

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    }


def main():
    """MCP stdio server loop."""
    sys.stderr.write(f"MisakaNet DeepSeekHarness Adapter v{ADAPTER_VERSION}\n")
    sys.stderr.write(f"MCP Server: v{get_server_version()}\n")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        response = handle_request(request)
        if response:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
