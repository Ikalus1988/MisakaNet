#!/usr/bin/env python3
"""MisakaNet MCP Server — thin adapter for Claude Code, Cursor, Continue, etc.

Exposes 4 tools:
  misakanet.search(query, domain?, top?)
  misakanet.get_lesson(path_or_id)
  misakanet.submit_usage(lesson_id, tool, outcome)
  misakanet.usage_status(user?)

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
import re
import sys
from importlib import metadata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def get_server_version() -> str:
    """Return the installed or checkout package version for MCP metadata."""
    try:
        return metadata.version("misakanet")
    except metadata.PackageNotFoundError:
        pyproject = REPO_ROOT / "pyproject.toml"
        if pyproject.exists():
            match = re.search(
                r'^version\s*=\s*["\']([^"\']+)["\']',
                pyproject.read_text(encoding="utf-8", errors="replace"),
                re.MULTILINE,
            )
            if match:
                return match.group(1)
    return "0.0.0"

# Import SAG-Lite search
try:
    from scripts.build_sag_index import search as sag_search
    SAG_DB = REPO_ROOT / "data" / "sag.db"
    HAS_SAG = SAG_DB.exists()
except ImportError:
    HAS_SAG = False

# Import BM25 search fallback
try:
    from misakanet.search.engine import (
        LESSONS,
        _load_docs_cached,
        _search_cached,
    )
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False


def _fallback_search(query: str, domain: str = None, top: int = 5) -> list | None:
    """Lightweight keyword search from lessons.json — zero dependencies.

    Used when SAG-Lite and BM25 are both unavailable (e.g. Glama sandbox).
    Returns None if lessons.json is not found (caller should show error).
    Returns [] if lessons.json exists but no matches (caller should show empty results).
    """
    import json as _json

    # Try multiple locations for lessons.json
    candidates = [
        REPO_ROOT / "data" / "lessons.json",
        REPO_ROOT / "lessons.json",
    ]
    lessons = None
    for path in candidates:
        if path.exists():
            try:
                lessons = _json.loads(path.read_text(encoding="utf-8", errors="replace"))
                break
            except Exception:
                continue

    if not lessons or not isinstance(lessons, list):
        return None

    q = query.lower()
    q_words = [w for w in q.split() if len(w) > 2]
    scored = []

    for lesson in lessons:
        if not isinstance(lesson, dict):
            continue
        if domain and lesson.get("domain", "").lower() != domain.lower():
            continue

        title = (lesson.get("title") or "").lower()
        summary = (lesson.get("summary") or "").lower()
        lesson_domain = (lesson.get("domain") or "").lower()
        tags = " ".join(lesson.get("tags", [])).lower() if isinstance(lesson.get("tags"), list) else ""
        text = f"{title} {summary} {lesson_domain} {tags}"

        score = 0
        if q in text:
            score += 10
        for w in q_words:
            if w in text:
                score += 2
            if w in title:
                score += 1

        if score > 0:
            scored.append((score, lesson))

    scored.sort(key=lambda x: -x[0])
    return [
        {
            "title": l.get("title", ""),
            "path": l.get("url", l.get("path", "")),
            "score": round(s, 3),
            "domain": l.get("domain", ""),
            "status": l.get("status", ""),
        }
        for s, l in scored[:top]
    ]


def handle_search(args: dict) -> dict:
    """Search MisakaNet lessons."""
    query = args.get("query", "")
    domain = args.get("domain")
    tags = args.get("tags")
    top = args.get("top", 5)
    explain = bool(args.get("explain", False))

    if not query:
        return {
            "error": "query is required",
            "hint": "Try: {\"query\": \"python async\", \"domain\": \"core\"}",
            "examples": [
                "{\"query\": \"machine learning\"}",
                "{\"query\": \"REST API\", \"top\": 3}",
                "{\"query\": \"tutorial\", \"domain\": \"core\"}"
            ],
            "guidance": "Provide a search term (e.g. 'pip install timeout'). For broader results, try shorter keywords. See docs/integrations/mcp-remote.md for usage examples.",
            "voice": "failure-warning",
        }

    if HAS_SAG and not explain:
        results = sag_search(SAG_DB, query, domain=domain, top=top)
        voice = "lesson-found" if results else "failure-warning"
        return {"results": results, "source": "sag-lite", "voice": voice}
    elif HAS_BM25:
        docs = _load_docs_cached(LESSONS, is_lesson=True)
        scored = _search_cached(query, docs)
        results = []
        from misakanet.search.engine import _score_breakdown
        for score, doc in scored[:top]:
            result = {
                "title": doc.title,
                "path": str(doc.filepath),
                "score": round(score, 3),
                "domain": doc.domain,
                "status": doc.status,
            }
            if explain:
                result["score_breakdown"] = _score_breakdown(query, doc, docs=docs)
            results.append(result)
        voice = "lesson-found" if results else "failure-warning"
        return {"results": results, "source": "bm25", "voice": voice}
    else:
        # Fallback: lightweight keyword search from lessons.json
        results = _fallback_search(query, domain=domain, top=top)
        if results is not None:
            voice = "lesson-found" if results else "failure-warning"
            return {"results": results, "source": "fallback", "voice": voice}
        return {
            "error": "Search engine unavailable — index not built",
            "action": "Run: python3 scripts/build_sag_index.py to enable BM25/SAG search",
            "fallback": "Browse lessons via misaka://lessons/index resource instead",
            "guidance": "To obtain a token or search lessons, refer to docs/integrations/mcp-remote.md or contact maintainer.",
            "voice": "failure-warning",
        }


def handle_get_lesson(args: dict) -> dict:
    """Get a lesson by path or ID."""
    path_or_id = args.get("path", args.get("id", ""))
    if not path_or_id:
        return {
            "error": "path or id is required",
            "hint": "Try: {\"path\": \"lessons/core/welcome.md\"} or {\"id\": \"welcome\"}",
            "examples": [
                "{\"path\": \"lessons/core/async-python.md\"}",
                "{\"id\": \"async-python\"}"
            ],
            "guidance": "Provide a lesson path (e.g. 'lessons/core/auto-merge-ci-pipeline.md') or lesson ID. Use misakanet_search first to discover available lessons.",
            "voice": "failure-warning",
        }

    # Helper: check if path is within allowed lessons directory
    def _is_allowed_lesson_path(p):
        resolved = p.resolve()
        lessons_dir = (REPO_ROOT / "lessons").resolve()
        return resolved.is_relative_to(lessons_dir) and resolved.suffix == ".md"

    # Try direct path first (with traversal protection)
    lesson_path = (REPO_ROOT / path_or_id).resolve()
    if lesson_path.is_relative_to(REPO_ROOT.resolve()) and _is_allowed_lesson_path(lesson_path):
        if lesson_path.exists():
            content = lesson_path.read_text(encoding="utf-8", errors="replace")
            return {
                "path": str(lesson_path.relative_to(REPO_ROOT)),
                "content": content[:5000],
                "voice": "connect-success",
            }

    # Fallback: try searching by ID in lessons/core|contrib/
    for subdir in ["core", "contrib"]:
        candidate = REPO_ROOT / "lessons" / subdir / f"{path_or_id}.md"
        if candidate.exists() and _is_allowed_lesson_path(candidate):
            lesson_path = candidate
            break

    if not lesson_path.exists() or not _is_allowed_lesson_path(lesson_path):
        return {
            "error": f"Lesson not found: {path_or_id}",
            "hint": "Use misakanet_search to find available lessons by keyword",
            "suggestion": "Try searching with: {\"query\": \"" + path_or_id.replace("-", " ") + "\"}",
            "guidance": f"Use misakanet_search with a related keyword to discover available lessons, or check docs/integrations/mcp-remote.md for the lesson index.",
            "voice": "failure-warning",
        }

    content = lesson_path.read_text(encoding="utf-8", errors="replace")
    return {
        "path": str(lesson_path.relative_to(REPO_ROOT)),
        "content": content[:5000],  # Truncate for MCP context window
        "voice": "connect-success",
    }


def handle_submit_usage(args: dict) -> dict:
    """Submit a usage report (placeholder — creates GitHub Issue via API)."""
    lesson_id = args.get("lesson_id", "")
    tool = args.get("tool", "unknown")
    outcome = args.get("outcome", "unknown")

    if not lesson_id:
        return {
            "error": "lesson_id is required",
            "guidance": "Provide the lesson ID (e.g. 'auto-merge-ci-pipeline'). Use misakanet_search to discover lesson IDs by topic.",
            "voice": "failure-warning",
        }

    # For now, just log locally
    report = {
        "lesson_id": lesson_id,
        "tool": tool,
        "outcome": outcome,
        "status": "logged",
        "voice": "pair-success",
    }

    # TODO: POST to /api/usage or create GitHub Issue
    return report


def handle_preflight(args: dict) -> dict:
    """Handle misakanet_preflight tool call."""
    intent = args.get("intent", "")
    context = args.get("context")
    from scripts.mcp_preflight import evaluate_intent
    return evaluate_intent(intent, context)


def handle_usage_status(args: dict) -> dict:
    """Show current usage status and remaining quota."""
    try:
        from scripts.usage_meter import get_status, hash_ip
        user = args.get("user", "anon:mcp-default")
        status = get_status(user)
        return {
            "user": status["user"],
            "free_reads_used": status["free_reads_used"],
            "free_reads_limit": status["free_reads_limit"],
            "free_reads_remaining": status["free_reads_remaining"],
            "credits": status["credits"],
            "is_registered": status["is_registered"],
            "next": "Use misakanet_submit_intake or misakanet_contribute_lesson to request more credits."
        }
    except Exception as e:
        return {"error": str(e), "user": "unknown", "free_reads_remaining": -1}


# ── MCP Resources ──
RESOURCES = [
    {
        "uri": "misaka://lessons/index",
        "name": "Lessons Index",
        "description": "Browse all published lessons (core + contrib) with metadata",
        "mimeType": "application/json",
    },
    {
        "uri": "misaka://protocol/overview",
        "name": "Protocol Overview",
        "description": "Swarm Knowledge Protocol configuration (trust tiers, rings, scoring)",
        "mimeType": "application/json",
    },
    {
        "uri": "misaka://docs/readme",
        "name": "README",
        "description": "Project overview, quickstart, and integration guide",
        "mimeType": "text/markdown",
    },
    {
        "uri": "misaka://docs/faq",
        "name": "Troubleshooting FAQ",
        "description": "Common issues and solutions for MisakaNet users",
        "mimeType": "text/markdown",
    },
    {
        "uri": "misaka://docs/changelog",
        "name": "Changelog",
        "description": "Latest release notes and version history",
        "mimeType": "text/markdown",
    },
    {
        "uri": "misakanet://lessons/{id}",
        "name": "Lesson by ID",
        "description": "Full lesson content and metadata by lesson ID",
        "mimeType": "application/json",
    },
    {
        "uri": "misakanet://domains",
        "name": "Domain List",
        "description": "List all knowledge domains with lesson counts",
        "mimeType": "application/json",
    },
]


def handle_resources_list() -> list:
    """Return available resources."""
    return RESOURCES


def handle_resources_read(uri: str) -> dict:
    """Read a resource by URI."""
    if uri == "misaka://lessons/index":
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
        return {"lessons": lessons, "count": len(lessons)}

    elif uri == "misaka://protocol/overview":
        p = REPO_ROOT / "misaka-protocol.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return {"error": "misaka-protocol.json not found"}

    elif uri == "misaka://docs/readme":
        p = REPO_ROOT / "README.md"
        if p.exists():
            return {"content": p.read_text(encoding="utf-8", errors="replace")[:8000]}
        return {"error": "README.md not found"}

    elif uri == "misaka://docs/faq":
        p = REPO_ROOT / "docs" / "troubleshooting.md"
        if p.exists():
            return {"content": p.read_text(encoding="utf-8", errors="replace")[:8000]}
        return {"error": "troubleshooting.md not found"}

    elif uri == "misaka://docs/changelog":
        p = REPO_ROOT / "STATUS.md"
        if p.exists():
            return {"content": p.read_text(encoding="utf-8", errors="replace")[:4000]}
        return {"error": "STATUS.md not found"}

    elif uri.startswith("misakanet://lessons/"):
        lesson_id = uri.replace("misakanet://lessons/", "")
        for subdir in ["core", "contrib", "draft", "en"]:
            d = REPO_ROOT / "lessons" / subdir
            if d.exists():
                for f in d.glob("*.md"):
                    if f.stem == lesson_id:
                        content_text = f.read_text(encoding="utf-8", errors="replace")
                        return {
                            "id": f.stem,
                            "path": str(f.relative_to(REPO_ROOT)),
                            "title": content_text.split("\n")[0].replace("# ", "").strip(),
                            "domain": subdir,
                            "content": content_text[:8000],
                            "word_count": len(content_text.split()),
                        }
        return {"error": f"Lesson not found: {lesson_id}"}

    elif uri == "misakanet://domains":
        from collections import Counter
        domain_counts = Counter()
        for subdir in ["core", "contrib", "draft", "en"]:
            d = REPO_ROOT / "lessons" / subdir
            if d.exists():
                for f in d.glob("*.md"):
                    content_text = f.read_text(encoding="utf-8", errors="replace")
                    domain = subdir
                    if "domain:" in content_text[:500]:
                        for line in content_text[:500].split("\n"):
                            if line.strip().startswith("domain:"):
                                domain = line.split(":", 1)[1].strip()
                    domain_counts[domain] += 1
        return [{"name": d, "lesson_count": c} for d, c in sorted(domain_counts.items())]

    return {"error": f"Unknown resource: {uri}"}


# ── MCP Prompts ──
PROMPTS = [
    {
        "name": "search_lesson",
        "title": "Search Lessons",
        "description": "Search MisakaNet for lessons matching an error or topic",
        "arguments": [
            {"name": "query", "description": "Error message or topic to search for", "required": True},
            {"name": "domain", "description": "Optional domain filter (devops, python, rag, etc.)", "required": False},
        ],
    },
    {
        "name": "triage_failure",
        "title": "Triage Failure",
        "description": "Structured failure triage — find root cause and matching rescue cards",
        "arguments": [
            {"name": "error", "description": "The error message or stack trace", "required": True},
            {"name": "context", "description": "What were you doing when the error occurred", "required": False},
        ],
    },
    {
        "name": "release_audit",
        "title": "Release Audit",
        "description": "Check release readiness against MisakaNet quality gates",
        "arguments": [
            {"name": "version", "description": "Version to audit (e.g., v2.12.0)", "required": True},
        ],
    },
]


def handle_prompts_get(name: str, arguments: dict) -> dict:
    """Return a prompt with arguments filled in."""
    if name == "search_lesson":
        query = arguments.get("query", "")
        domain = arguments.get("domain", "")
        domain_hint = f" in the '{domain}' domain" if domain else ""
        return {
            "description": f"Search for lessons about: {query}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Search MisakaNet lessons for solutions to: \"{query}\"{domain_hint}.\n\n"
                            f"Use the misakanet_search tool with query=\"{query}\""
                            + (f" and domain=\"{domain}\"" if domain else "")
                            + ".\n\nReport the top 3 matches with their relevance score and actionable summary."
                        ),
                    },
                }
            ],
        }

    elif name == "triage_failure":
        error = arguments.get("error", "")
        context = arguments.get("context", "unknown context")
        return {
            "description": f"Triage failure: {error[:80]}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"I encountered this error while {context}:\n\n"
                            f"```\n{error}\n```\n\n"
                            "Please:\n"
                            "1. Search MisakaNet for matching lessons using misakanet_search\n"
                            "2. If a rescue card exists, apply its fix\n"
                            "3. If no match, suggest the root cause and next diagnostic steps"
                        ),
                    },
                }
            ],
        }

    elif name == "release_audit":
        version = arguments.get("version", "latest")
        return {
            "description": f"Audit release {version}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Audit MisakaNet release {version} for readiness.\n\n"
                            "Check:\n"
                            "1. Read misaka://docs/changelog for this version's changes\n"
                            "2. Verify all lessons in misaka://lessons/index have valid frontmatter\n"
                            "3. Check protocol version matches in misaka://protocol/overview\n"
                            "4. Report any gaps or blockers for release"
                        ),
                    },
                }
            ],
        }

    return {"error": f"Unknown prompt: {name}"}


# ── MCP Tools ──
TOOLS = [
    {
        "name": "misakanet_preflight",
        "description": (
            "Evaluate action intent and context before high-risk tasks (such as RAG build, GPU/WSL heavy operations, "
            "or bulk data import) to get proactive risk assessment, relevant lesson guidance, and safety guards. "
            "Input semantics: intent is required (description of the planned action); context is optional (environment "
            "details like OS, VRAM, data size). Output schema: JSON with risk ('low', 'medium', 'high', 'critical'), "
            "matched_lessons[], guards[], and recommendation. Side effects: none. Auth: none."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "intent": {"type": "string", "description": "Required action intent description (e.g. 'build RAG index from 218 PDFs')."},
                "context": {"type": "string", "description": "Optional environment context (e.g. 'WSL, GPU 8GB VRAM')."},
            },
            "required": ["intent"],
        },
    },
    {
        "name": "misakanet_search",
        "description": (
            "Search MisakaNet's public failure-lesson index by error text, keyword, or topic. "
            "Use when you need to discover relevant lessons and do not already know a lesson ID. "
            "Input semantics: query is required; domain optionally filters by lesson domain; top limits "
            "ranked results and defaults to 5. Set explain=true to return matched terms, TF-IDF, "
            "entity matches, vector similarity, and hybrid score components. Output schema: JSON "
            "with results[] and source; each "
            "result is a ranked lesson summary that may include path, title, domain/status, score/rank, "
            "and match details depending on the active index. Error cases: missing query, unavailable "
            "search index, or no matches (empty results). Side effects: none. Auth: none. Rate limits: "
            "local stdio process only; callers should keep result counts small. Do not use for private "
            "log collection; search only with redacted snippets. Use misakanet_get_lesson for full content."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Required redacted error message, keyword, or topic (for example: 'pip install timeout' or 'DCO sign-off failed')."},
                "domain": {"type": "string", "description": "Optional domain filter such as devops, python, network, feishu, rag, fanuc, or mcp."},
                "top": {"type": "integer", "description": "Maximum ranked results to return. Defaults to 5; keep small for MCP context and latency."},
                "explain": {"type": "boolean", "description": "Include score evidence for each result; vector similarity is null when the optional backend is unavailable."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "misakanet_get_lesson",
        "description": (
            "Fetch one public MisakaNet lesson by repository path or lesson ID. Use after "
            "misakanet_search returns a promising result, or when a lesson is explicitly referenced; "
            "do not use it for broad discovery. Input semantics: provide either path or id. Output "
            "schema: JSON with path and markdown content, truncated to 5000 characters for MCP context. "
            "Error cases: missing path/id or lesson not found. Side effects: none. Auth: none. Rate "
            "limits: local stdio process only; fetch one lesson per call when possible. Do not send "
            "private logs or prompts to this tool; it only reads repository lessons."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Lesson path relative to the repository, for example lessons/core/auto-merge-ci-pipeline.md."},
                "id": {"type": "string", "description": "Lesson ID, usually the filename without .md, for example auto-merge-ci-pipeline."},
            },
        },
    },
    {
        "name": "misakanet_submit_usage",
        "description": (
            "[Experimental] Record that a public lesson helped with a problem. Use only after the "
            "user or calling agent explicitly chooses to submit usage feedback for a specific lesson. "
            "Input semantics: lesson_id is required; tool names the calling client; outcome should be "
            "solved, partial, not-helpful, or another short status. Output schema: JSON with lesson_id, "
            "tool, outcome, and status. Error cases: missing lesson_id. Side effects: currently returns "
            "a local placeholder report only; it does not send data externally, open GitHub issues, or "
            "publish lessons. Auth: none. Rate limits: local stdio process only; submit at most once per "
            "resolved incident. Do not include raw logs, prompts, file contents, or secrets."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "string", "description": "Required ID of the lesson that helped, for example auto-merge-ci-pipeline."},
                "tool": {"type": "string", "description": "Calling tool or client name, for example claude-code, cursor, codex, or aider."},
                "outcome": {"type": "string", "description": "Short result label such as solved, partial, or not-helpful."},
            },
            "required": ["lesson_id"],
        },
    },
    {
        "name": "misakanet_usage_status",
        "description": (
            "Check current usage status and remaining quota. Use to see how many free lesson reads "
            "remain and how many credits are available. Input semantics: user is optional (defaults to "
            "anonymous). Output schema: JSON with user, free_reads_used, free_reads_limit, "
            "free_reads_remaining, credits, is_registered, and next steps. Error cases: none. Side "
            "effects: none. Auth: none. Rate limits: none."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "user": {"type": "string", "description": "Optional user identifier (e.g. 'anon:iphash' or 'token:xxx'). Defaults to 'anon:mcp-default'."},
            },
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
                "protocolVersion": "2025-06-18",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {},
                },
                "serverInfo": {
                    "name": "misakanet",
                    "version": get_server_version(),
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
            "misakanet_usage_status": handle_usage_status,
            "misakanet_preflight": handle_preflight,
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

    # ── Resources ──
    elif method == "resources/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"resources": handle_resources_list()},
        }

    elif method == "resources/read":
        uri = params.get("uri", "")
        content = handle_resources_read(uri)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "contents": [
                    {"uri": uri, "mimeType": "application/json", "text": json.dumps(content, ensure_ascii=False)}
                ]
            },
        }

    # ── Prompts ──
    elif method == "prompts/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"prompts": PROMPTS},
        }

    elif method == "prompts/get":
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        result = handle_prompts_get(name, arguments)
        if "error" in result:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": result["error"]},
            }
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

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
