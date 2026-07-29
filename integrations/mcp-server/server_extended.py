#!/usr/bin/env python3
"""MisakaNet MCP Server (Extended) — tools + resources for lesson metadata.

Extends the base MCP server with:
- MCP Resources: misakanet://lessons/{id}, misakanet://domains
- Enhanced search tool with tags support
- Full MCP protocol compliance (resources/list, resources/read)

Compatible with: Cursor, Claude Code, Claude Desktop, Continue.dev

Usage:
    python3 integrations/mcp-server/server_extended.py

MCP Config:
    {
      "mcpServers": {
        "misakanet": {
          "command": "python3",
          "args": ["/path/to/MisakaNet/integrations/mcp-server/server_extended.py"]
        }
      }
    }
"""
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SEARCH_SCRIPT = REPO_ROOT / "search_knowledge.py"
LESSONS_DIR = REPO_ROOT / "lessons"


# ── Core Functions ──

def search_lessons(query: str, top_k: int = 5, domain: str = "", tags: str = "") -> list[dict]:
    """Search MisakaNet knowledge base with optional domain and tag filters."""
    cmd = [sys.executable, str(SEARCH_SCRIPT), query, "--json", "--top", str(top_k)]
    if domain:
        cmd.extend(["--domain", domain])
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15, cwd=str(REPO_ROOT)
        )
        if result.returncode == 0 and result.stdout.strip():
            results = json.loads(result.stdout)
            # Client-side tag filtering if tags specified
            if tags:
                tag_list = [t.strip().lower() for t in tags.split(",")]
                results = [
                    r for r in results
                    if any(t in json.dumps(r).lower() for t in tag_list)
                ] or results  # Fallback to unfiltered if no tag matches
            return results
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return []


def get_lesson_by_id(lesson_id: str) -> dict:
    """Get a lesson by ID (filename without extension or relative path)."""
    # Try direct path
    candidates = [
        LESSONS_DIR / f"{lesson_id}.md",
        LESSONS_DIR / lesson_id,
        REPO_ROOT / lesson_id,
    ]
    # Try glob for partial match
    if not any(c.exists() for c in candidates):
        matches = list(LESSONS_DIR.rglob(f"*{lesson_id}*"))
        if matches:
            candidates = matches[:1]

    for path in candidates:
        if path.exists() and path.suffix == ".md":
            content = path.read_text(encoding="utf-8")
            rel_path = str(path.relative_to(REPO_ROOT))
            # Extract metadata from frontmatter or first lines
            metadata = _extract_metadata(content, rel_path)
            return metadata
    return {"error": f"Lesson not found: {lesson_id}", "id": lesson_id}


def _extract_metadata(content: str, path: str) -> dict:
    """Extract lesson metadata from markdown content."""
    lines = content.split("\n")
    title = ""
    tags = []
    domain = ""

    # Parse YAML frontmatter if present
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                break
            if line.startswith("title:"):
                title = line.split(":", 1)[1].strip().strip("\"\'")
            elif line.startswith("tags:"):
                tags = [t.strip() for t in line.split(":", 1)[1].split(",")]
            elif line.startswith("domain:"):
                domain = line.split(":", 1)[1].strip()

    # Fallback: use first heading as title
    if not title:
        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip()
                break

    # Infer domain from path
    if not domain:
        parts = Path(path).parts
        if len(parts) > 1 and parts[0] == "lessons":
            domain = parts[1] if len(parts) > 2 else ""

    return {
        "id": Path(path).stem,
        "path": path,
        "title": title or Path(path).stem,
        "domain": domain,
        "tags": tags,
        "content": content[:8000],
        "word_count": len(content.split()),
    }


def list_domains() -> list[dict]:
    """List all knowledge domains with lesson counts."""
    if not LESSONS_DIR.exists():
        return []
    domains = {}
    for f in LESSONS_DIR.rglob("*.md"):
        rel = f.relative_to(LESSONS_DIR)
        domain = rel.parts[0] if len(rel.parts) > 1 else "general"
        domains[domain] = domains.get(domain, 0) + 1
    return [{"name": k, "lesson_count": v} for k, v in sorted(domains.items())]


def list_lessons(domain: str = "") -> list[dict]:
    """List lessons, optionally filtered by domain."""
    if not LESSONS_DIR.exists():
        return []
    pattern = f"{domain}/**/*.md" if domain else "**/*.md"
    lessons = []
    for f in LESSONS_DIR.glob(pattern):
        rel = str(f.relative_to(REPO_ROOT))
        lessons.append({
            "id": f.stem,
            "path": rel,
            "title": f.stem.replace("-", " ").replace("_", " ").title(),
            "domain": domain or (str(f.relative_to(LESSONS_DIR)).split("/")[0] if len(f.relative_to(LESSONS_DIR).parts) > 1 else "general"),
        })
    return lessons[:50]  # Limit to 50


# ── MCP Protocol ──

TOOLS = [
    {
        "name": "search_lessons",
        "description": "Search MisakaNet knowledge base. Returns ranked lessons with title, score, domain, tags, and preview. Use for debugging, finding solutions, or exploring knowledge.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (error message, topic, tool name)"},
                "domain": {"type": "string", "description": "Filter by domain (e.g., python, docker, git)", "default": ""},
                "tags": {"type": "string", "description": "Comma-separated tags to filter (e.g., 'timeout,proxy')", "default": ""},
                "top_k": {"type": "integer", "description": "Number of results (default 5)", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_lesson",
        "description": "Get full lesson content and metadata by ID or path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Lesson ID (filename stem) or relative path"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "list_domains",
        "description": "List all knowledge domains with lesson counts.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_lessons",
        "description": "List available lessons, optionally filtered by domain.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Filter by domain name", "default": ""},
            },
        },
    },
]

RESOURCES = [
    {
        "uri": "misakanet://domains",
        "name": "Knowledge Domains",
        "description": "List all available knowledge domains with lesson counts",
        "mimeType": "application/json",
    },
]

RESOURCE_TEMPLATES = [
    {
        "uriTemplate": "misakanet://lessons/{id}",
        "name": "Lesson by ID",
        "description": "Get full lesson content and metadata by ID",
        "mimeType": "application/json",
    },
]


def handle_request(request: dict) -> dict | None:
    """Handle a JSON-RPC request."""
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    # ── Lifecycle ──
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                },
                "serverInfo": {"name": "misakanet", "version": "0.2.0"},
            },
        }

    if method == "notifications/initialized":
        return None

    # ── Tools ──
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})

        if tool_name == "search_lessons":
            results = search_lessons(
                args.get("query", ""),
                args.get("top_k", 5),
                args.get("domain", ""),
                args.get("tags", ""),
            )
            text = json.dumps(results, ensure_ascii=False, indent=2) if results else "No results found."
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": text}]}}

        if tool_name == "get_lesson":
            lesson = get_lesson_by_id(args.get("id", ""))
            text = json.dumps(lesson, ensure_ascii=False, indent=2)
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": text}]}}

        if tool_name == "list_domains":
            domains = list_domains()
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(domains, indent=2)}]}}

        if tool_name == "list_lessons":
            lessons = list_lessons(args.get("domain", ""))
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(lessons, ensure_ascii=False, indent=2)}]}}

        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}}

    # ── Resources ──
    if method == "resources/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": RESOURCES, "resourceTemplates": RESOURCE_TEMPLATES}}

    if method == "resources/read":
        uri = params.get("uri", "")

        if uri == "misakanet://domains":
            domains = list_domains()
            return {"jsonrpc": "2.0", "id": req_id, "result": {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(domains, indent=2)}]}}

        if uri.startswith("misakanet://lessons/"):
            lesson_id = unquote(uri.replace("misakanet://lessons/", ""))
            lesson = get_lesson_by_id(lesson_id)
            return {"jsonrpc": "2.0", "id": req_id, "result": {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(lesson, ensure_ascii=False, indent=2)}]}}

        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": f"Unknown resource: {uri}"}}

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}


def main():
    """MCP stdio transport."""
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
