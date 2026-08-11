#!/usr/bin/env python3
"""MisakaNet MCP HTTP Server — wraps mcp_server.py with SSE/Streamable HTTP transport.

Usage:
    # Start HTTP server on default port 8080
    python3 scripts/mcp_http_server.py

    # Custom port
    python3 scripts/mcp_http_server.py --port 9090

    # In Claude Code settings.json:
    {
      "mcpServers": {
        "misakanet-http": {
          "url": "http://localhost:8080/mcp"
        }
      }
    }
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from mcp.server.fastmcp import FastMCP

# ── Import search engines ──
try:
    from scripts.build_sag_index import search as sag_search
    SAG_DB = REPO_ROOT / "data" / "sag.db"
    HAS_SAG = SAG_DB.exists()
except ImportError:
    HAS_SAG = False

try:
    from misakanet.search.engine import MisakaNetSearchEngine
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False

# ── Create FastMCP server ──
mcp = FastMCP("misakanet")


@mcp.tool()
def misakanet_search(query: str, domain: str = "", top: int = 5) -> dict:
    """Search MisakaNet's public failure-lesson index by error text, keyword, or topic."""
    if not query:
        return {"error": "query is required", "voice": "failure-warning"}

    domain_val = domain if domain else None

    if HAS_SAG:
        results = sag_search(SAG_DB, query, domain=domain_val, top=top)
        voice = "lesson-found" if results else "failure-warning"
        return {"results": results, "source": "sag-lite", "voice": voice}
    elif HAS_BM25:
        engine = MisakaNetSearchEngine()
        results = engine.search(query, top=top)
        voice = "lesson-found" if results else "failure-warning"
        return {"results": results, "source": "bm25", "voice": voice}
    else:
        return {"error": "No search engine available. Run: python3 scripts/build_sag_index.py", "voice": "failure-warning"}


@mcp.tool()
def misakanet_get_lesson(path: str = "", id: str = "") -> dict:
    """Fetch one public MisakaNet lesson by repository path or lesson ID."""
    path_or_id = path or id
    if not path_or_id:
        return {"error": "path or id is required", "voice": "failure-warning"}

    lesson_path = (REPO_ROOT / path_or_id).resolve()
    if not lesson_path.is_relative_to(REPO_ROOT.resolve()):
        return {"error": "Invalid path: path traversal detected", "voice": "failure-warning"}
    # Restrict to lessons/ directory and .md files only
    lessons_dir = (REPO_ROOT / "lessons").resolve()
    if not lesson_path.is_relative_to(lessons_dir) or not lesson_path.suffix == ".md":
        return {"error": "Access denied: only lessons/*.md files are accessible", "voice": "failure-warning"}
    if not lesson_path.exists():
        for subdir in ["core", "contrib"]:
            candidate = REPO_ROOT / "lessons" / subdir / f"{path_or_id}.md"
            if candidate.exists():
                lesson_path = candidate
                break

    if not lesson_path.exists():
        return {"error": f"Lesson not found: {path_or_id}", "voice": "failure-warning"}

    content = lesson_path.read_text(encoding="utf-8", errors="replace")
    return {
        "path": str(lesson_path.relative_to(REPO_ROOT)),
        "content": content[:5000],
        "voice": "connect-success",
    }


@mcp.tool()
def misakanet_submit_usage(lesson_id: str, tool: str = "unknown", outcome: str = "unknown") -> dict:
    """Record that a public lesson helped with a problem."""
    if not lesson_id:
        return {"error": "lesson_id is required", "voice": "failure-warning"}
    return {
        "lesson_id": lesson_id,
        "tool": tool,
        "outcome": outcome,
        "status": "logged",
        "voice": "pair-success",
    }


@mcp.tool()
def misakanet_usage_status(user: str = "anon:mcp-default") -> dict:
    """Check current usage status and remaining quota."""
    try:
        from scripts.usage_meter import get_status
        status = get_status(user)
        return {
            "user": status["user"],
            "free_reads_used": status["free_reads_used"],
            "free_reads_limit": status["free_reads_limit"],
            "free_reads_remaining": status["free_reads_remaining"],
            "credits": status["credits"],
            "is_registered": status["is_registered"],
        }
    except Exception as e:
        return {"error": str(e), "user": "unknown", "free_reads_remaining": -1}


# ── Resources ──
@mcp.resource("misaka://lessons/index")
def lessons_index() -> str:
    """Browse all published lessons with metadata."""
    lessons = []
    for subdir in ["core", "contrib"]:
        d = REPO_ROOT / "lessons" / subdir
        if d.exists():
            for f in sorted(d.glob("*.md")):
                lessons.append({
                    "id": f.stem,
                    "path": str(f.relative_to(REPO_ROOT)),
                    "category": subdir,
                })
    return json.dumps({"lessons": lessons, "count": len(lessons)}, ensure_ascii=False)


@mcp.resource("misaka://protocol/overview")
def protocol_overview() -> str:
    """Swarm Knowledge Protocol configuration."""
    p = REPO_ROOT / "misaka-protocol.json"
    if p.exists():
        return p.read_text(encoding="utf-8")
    return json.dumps({"error": "not found"})


@mcp.resource("misaka://docs/readme")
def readme_resource() -> str:
    """Project overview."""
    p = REPO_ROOT / "README.md"
    if p.exists():
        return p.read_text(encoding="utf-8", errors="replace")[:8000]
    return "README.md not found"


# ── Prompts ──
@mcp.prompt()
def search_lesson(query: str, domain: str = "") -> str:
    """Search for lessons matching an error or topic."""
    domain_hint = f" in the '{domain}' domain" if domain else ""
    return (
        f"Search MisakaNet lessons for solutions to: \"{query}\"{domain_hint}.\n\n"
        f"Use misakanet_search with query=\"{query}\""
        + (f" and domain=\"{domain}\"" if domain else "")
        + ".\n\nReport the top 3 matches with relevance score and actionable summary."
    )


@mcp.prompt()
def triage_failure(error: str, context: str = "unknown context") -> str:
    """Structured failure triage."""
    return (
        f"I encountered this error while {context}:\n\n"
        f"```\n{error}\n```\n\n"
        "Please:\n"
        "1. Search MisakaNet for matching lessons\n"
        "2. If a rescue card exists, apply its fix\n"
        "3. If no match, suggest root cause and next steps"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MisakaNet MCP HTTP Server")
    parser.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    args = parser.parse_args()

    print(f"Starting MisakaNet MCP HTTP server on {args.host}:{args.port}")
    print(f"SAG-Lite: {'available' if HAS_SAG else 'not available'}")
    print(f"BM25: {'available' if HAS_BM25 else 'not available'}")
    print(f"Endpoint: http://{args.host}:{args.port}/mcp")

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport="streamable-http")
