#!/usr/bin/env python3
"""MisakaNet MCP Server — thin adapter for Claude Code, Cursor, Continue, etc.

Exposes 3 tools:
  misakanet.search(query, domain?, top?)
  misakanet.get_lesson(path_or_id)
  misakanet.submit_usage(lesson_id, tool, outcome)

Usage:
    # As MCP server (stdio transport)
    python3 scripts/mcp_server.py

    # In Claude Code settings.json:
    {
      "mcpServers": {
        "misakanet": {
          "command": "python3",
          "args": ["C:/Users/hp/MisakaNet/scripts/mcp_server.py"]
        }
      }
    }
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Import SAG-Lite search
try:
    from scripts.build_sag_index import search as sag_search
    SAG_DB = REPO_ROOT / "data" / "sag.db"
    HAS_SAG = SAG_DB.exists()
except ImportError:
    HAS_SAG = False

# Import BM25 search fallback
try:
    from misakanet.search.engine import MisakaNetSearchEngine
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False


def handle_search(args: dict) -> dict:
    """Search MisakaNet lessons."""
    query = args.get("query", "")
    domain = args.get("domain")
    top = args.get("top", 5)

    if not query:
        return {"error": "query is required"}

    if HAS_SAG:
        results = sag_search(SAG_DB, query, domain=domain, top=top)
        return {"results": results, "source": "sag-lite"}
    elif HAS_BM25:
        engine = MisakaNetSearchEngine()
        results = engine.search(query, top=top)
        return {"results": results, "source": "bm25"}
    else:
        return {"error": "No search engine available. Run: python3 scripts/build_sag_index.py"}


def handle_get_lesson(args: dict) -> dict:
    """Get a lesson by path or ID."""
    path_or_id = args.get("path", args.get("id", ""))
    if not path_or_id:
        return {"error": "path or id is required"}

    # Try direct path
    lesson_path = REPO_ROOT / path_or_id
    if not lesson_path.exists():
        # Try searching by ID in lessons/
        for subdir in ["core", "contrib"]:
            candidate = REPO_ROOT / "lessons" / subdir / f"{path_or_id}.md"
            if candidate.exists():
                lesson_path = candidate
                break

    if not lesson_path.exists():
        return {"error": f"Lesson not found: {path_or_id}"}

    content = lesson_path.read_text(encoding="utf-8", errors="replace")
    return {
        "path": str(lesson_path.relative_to(REPO_ROOT)),
        "content": content[:5000],  # Truncate for MCP context window
    }


def handle_submit_usage(args: dict) -> dict:
    """Submit a usage report (placeholder — creates GitHub Issue via API)."""
    lesson_id = args.get("lesson_id", "")
    tool = args.get("tool", "unknown")
    outcome = args.get("outcome", "unknown")

    if not lesson_id:
        return {"error": "lesson_id is required"}

    # For now, just log locally
    report = {
        "lesson_id": lesson_id,
        "tool": tool,
        "outcome": outcome,
        "status": "logged",
    }

    # TODO: POST to /api/usage or create GitHub Issue
    return report


# MCP Protocol handler
TOOLS = [
    {
        "name": "misakanet_search",
        "description": "Search MisakaNet lessons for solutions to errors, bugs, and technical problems.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (error message, keyword, or topic)"},
                "domain": {"type": "string", "description": "Filter by domain (devops, python, network, feishu, rag, etc.)"},
                "top": {"type": "integer", "description": "Number of results (default 5)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "misakanet_get_lesson",
        "description": "Get the full content of a specific lesson by path or ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Lesson path (e.g., lessons/core/auto-merge-ci-pipeline.md)"},
                "id": {"type": "string", "description": "Lesson ID (filename without .md)"},
            },
        },
    },
    {
        "name": "misakanet_submit_usage",
        "description": "Report that a lesson was used to solve a problem. Helps the network learn which lessons are valuable.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "string", "description": "ID of the lesson that helped"},
                "tool": {"type": "string", "description": "Your tool name (e.g., claude-code, cursor, aider)"},
                "outcome": {"type": "string", "description": "Outcome: solved, partial, not-helpful"},
            },
            "required": ["lesson_id"],
        },
    },
]


def handle_request(request: dict) -> dict:
    """Handle a JSON-RPC request."""
    method = request.get("method", "")
    params = request.get("params", {})
    req_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "misakanet",
                    "version": "2.9.2",
                },
            },
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS},
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        handlers = {
            "misakanet_search": handle_search,
            "misakanet_get_lesson": handle_get_lesson,
            "misakanet_submit_usage": handle_submit_usage,
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
        # Client notification, no response needed
        return None

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"},
        }


def main():
    """MCP stdio server loop."""
    # Write to stderr for debug (stdout is for MCP protocol)
    sys.stderr.write("MisakaNet MCP Server started\n")
    sys.stderr.write(f"SAG-Lite: {'available' if HAS_SAG else 'not available (run build_sag_index.py)'}\n")
    sys.stderr.write(f"BM25: {'available' if HAS_BM25 else 'not available'}\n")

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
