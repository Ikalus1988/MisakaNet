#!/usr/bin/env python3
"""MisakaNet MCP Server — exposes lesson search as an MCP tool.

Works with Cursor, Claude Desktop, Continue.dev, and any MCP-compatible client.

Usage:
    python3 integrations/mcp-server/server.py

MCP Config (cursor_mcp.json or claude_desktop_config.json):
    {
      "mcpServers": {
        "misakanet": {
          "command": "python3",
          "args": ["/path/to/MisakaNet/integrations/mcp-server/server.py"]
        }
      }
    }
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SEARCH_SCRIPT = REPO_ROOT / "search_knowledge.py"


def search_lessons(query: str, top_k: int = 5, domain: str = "") -> list[dict]:
    """Search MisakaNet knowledge base."""
    cmd = [sys.executable, str(SEARCH_SCRIPT), query, "--json", "--top", str(top_k)]
    if domain:
        cmd.extend(["--domain", domain])
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15, cwd=str(REPO_ROOT)
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return []


def get_lesson_content(path: str) -> str:
    """Read full lesson content by relative path."""
    full = REPO_ROOT / path
    if full.exists() and full.suffix == ".md":
        return full.read_text(encoding="utf-8")[:5000]
    return f"Lesson not found: {path}"


def list_domains() -> list[str]:
    """List available knowledge domains."""
    lessons_dir = REPO_ROOT / "lessons"
    if not lessons_dir.exists():
        return []
    domains = set()
    for f in lessons_dir.rglob("*.md"):
        rel = f.relative_to(lessons_dir)
        if len(rel.parts) > 1:
            domains.add(rel.parts[0])
    return sorted(domains)


# ── MCP Protocol (stdio JSON-RPC) ──

TOOLS = [
    {
        "name": "misakanet_search",
        "description": "Search MisakaNet knowledge base for debugging lessons, fixes, and technical references. Returns ranked results with title, score, domain, and preview.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (error message, topic, tool name)"},
                "top_k": {"type": "integer", "description": "Number of results (default 5)", "default": 5},
                "domain": {"type": "string", "description": "Filter by domain (optional)", "default": ""},
            },
            "required": ["query"],
        },
    },
    {
        "name": "misakanet_read_lesson",
        "description": "Read the full content of a MisakaNet lesson by its path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to lesson file (from search results)"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "misakanet_list_domains",
        "description": "List all available knowledge domains in MisakaNet.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def handle_request(request: dict) -> dict:
    """Handle a single JSON-RPC request."""
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "misakanet", "version": "0.1.0"},
            },
        }

    if method == "notifications/initialized":
        return None  # No response for notifications

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})

        if tool_name == "misakanet_search":
            results = search_lessons(
                args.get("query", ""),
                args.get("top_k", 5),
                args.get("domain", ""),
            )
            content = json.dumps(results, ensure_ascii=False, indent=2) if results else "No results found."
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": content}]},
            }

        if tool_name == "misakanet_read_lesson":
            text = get_lesson_content(args.get("path", ""))
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": text}]},
            }

        if tool_name == "misakanet_list_domains":
            domains = list_domains()
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(domains)}]},
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
        }

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}


def main():
    """MCP stdio transport: read JSON-RPC from stdin, write to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        response = handle_request(request)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
