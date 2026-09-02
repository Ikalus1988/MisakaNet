"""MCP Tool definitions for MisakaNet server."""
from __future__ import annotations

import fnmatch
import os

TOOLS = [
    {
        "name": "misakanet_search",
        "description": (
            "Search MisakaNet's public failure-lesson index by error"
            " text, keyword, or topic. Use when you need to discover"
            " relevant lessons and do not already know a lesson ID."
            " Input semantics: query is required; domain optionally"
            " filters by lesson domain; top limits ranked results and"
            " defaults to 5. Set explain=true to return matched terms,"
            " TF-IDF, entity matches, vector similarity, and hybrid"
            " score components. detail controls progressive disclosure:"
            " compact (default, ~80 tok/lesson) for broad scans,"
            " summary (~200 tok) with domain/tags/fix, full for"
            " complete lesson markdown. Output schema: JSON with"
            " results[] and source; each result is a ranked lesson"
            " summary. Error cases: missing query, unavailable search"
            " index, or no matches (empty results). Side effects:"
            " none. Auth: none. Rate limits: local stdio process"
            " only; callers should keep result counts small. Do not"
            " use for private log collection; search only with"
            " redacted snippets. Use misakanet_get_lesson for full"
            " content."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Required redacted error message, keyword,"
                        " or topic (for example: 'pip install"
                        " timeout' or 'DCO sign-off failed')."
                    ),
                },
                "domain": {
                    "type": "string",
                    "description": (
                        "Optional domain filter such as devops,"
                        " python, network, feishu, rag, fanuc, or mcp."
                    ),
                },
                "top": {
                    "type": "integer",
                    "description": (
                        "Maximum ranked results to return."
                        " Defaults to 5; keep small for MCP"
                        " context and latency."
                    ),
                },
                "explain": {
                    "type": "boolean",
                    "description": (
                        "Include score evidence for each result;"
                        " vector similarity is null when the"
                        " optional backend is unavailable."
                    ),
                },
                "detail": {
                    "type": "string",
                    "enum": ["compact", "summary", "full"],
                    "description": (
                        "Progressive disclosure: compact (default,"
                        " ~80 tok/lesson) shows id/title/problem/"
                        "freshness; summary (~200 tok) adds domain/"
                        "tags/fix; full returns complete lesson"
                        " markdown. Use compact for broad scans,"
                        " full only after narrowing results."
                    ),
                },
                "bm25_weight": {
                    "type": "number",
                    "description": (
                        "Override BM25 keyword weight (0-1)."
                        " Higher values favor exact keyword matches."
                        " Default: 0.65. All weights must sum to 1.0."
                    ),
                },
                "metadata_weight": {
                    "type": "number",
                    "description": (
                        "Override metadata bonus weight (0-1)."
                        " Higher values favor lessons with matching"
                        " domain/tags. Default: 0.20."
                    ),
                },
                "baseline_weight": {
                    "type": "number",
                    "description": (
                        "Override baseline score weight (0-1)."
                        " Higher values favor proven/popular lessons."
                        " Default: 0.15."
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "misakanet_get_lesson",
        "description": (
            "Fetch one public MisakaNet lesson by repository path or"
            " lesson ID. Use after misakanet_search returns a"
            " promising result, or when a lesson is explicitly"
            " referenced; do not use it for broad discovery."
            " Input semantics: provide either path or id. Output"
            " schema: JSON with path and markdown content, truncated"
            " to 5000 characters for MCP context. Error cases:"
            " missing path/id or lesson not found. Side effects:"
            " none. Auth: none. Rate limits: local stdio process"
            " only; fetch one lesson per call when possible."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Lesson path relative to the repository,"
                        " for example"
                        " lessons/core/auto-merge-ci-pipeline.md."
                    ),
                },
                "id": {
                    "type": "string",
                    "description": (
                        "Lesson ID, usually the filename without"
                        " .md, for example auto-merge-ci-pipeline."
                    ),
                },
            },
        },
    },
    {
        "name": "misakanet_submit_usage",
        "description": (
            "[Experimental] Record that a public lesson helped with"
            " a problem. Use only after the user or calling agent"
            " explicitly chooses to submit usage feedback for a"
            " specific lesson. Input semantics: lesson_id is"
            " required; tool names the calling client; outcome"
            " should be solved, partial, not-helpful, or another"
            " short status. Output schema: JSON with lesson_id,"
            " tool, outcome, and status. Error cases: missing"
            " lesson_id. Side effects: currently returns a local"
            " placeholder report only. Auth: none. Rate limits:"
            " local stdio process only."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "lesson_id": {
                    "type": "string",
                    "description": (
                        "Required ID of the lesson that helped,"
                        " for example auto-merge-ci-pipeline."
                    ),
                },
                "tool": {
                    "type": "string",
                    "description": (
                        "Calling tool or client name, for example"
                        " claude-code, cursor, codex, or aider."
                    ),
                },
                "outcome": {
                    "type": "string",
                    "description": (
                        "Short result label such as solved,"
                        " partial, or not-helpful."
                    ),
                },
            },
            "required": ["lesson_id"],
        },
    },
    {
        "name": "misakanet_submit_intake",
        "description": (
            "Submit a failure-case intake when no matching lesson"
            " exists or a lesson was stale/incorrect. Use after"
            " misakanet_search fails to find a good match, or when"
            " the user resolved a problem not yet documented."
            " Input semantics: problem is required (short"
            " description of the failure); kind defaults to"
            " missing_lesson; error, what_tried, fix, verification,"
            " and matched_lesson_id are optional. Output schema:"
            " JSON with submitted (boolean), intake_id, status"
            " (pending_review), redactions_applied, quality_score,"
            " and receipt. Error cases: missing problem, duplicate"
            " submission. Side effects: writes to"
            " data/contribution_queue.jsonl. Auth: none. Rate"
            " limits: local stdio process only."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": [
                        "missing_lesson",
                        "stale_lesson",
                        "new_lesson_candidate",
                    ],
                    "description": (
                        "Type of intake. missing_lesson = no match"
                        " found; stale_lesson = matched but wrong;"
                        " new_lesson_candidate = user resolved a"
                        " new problem."
                    ),
                },
                "problem": {
                    "type": "string",
                    "description": (
                        "Required short description of the failure"
                        " or gap (max 2000 chars)."
                    ),
                },
                "error": {
                    "type": "string",
                    "description": "Optional short error message.",
                },
                "what_tried": {
                    "type": "string",
                    "description": (
                        "Optional: what was attempted before or"
                        " during the failure."
                    ),
                },
                "fix": {
                    "type": "string",
                    "description": (
                        "Optional: how the problem was resolved,"
                        " if known."
                    ),
                },
                "verification": {
                    "type": "string",
                    "description": (
                        "Optional: how to confirm the fix works."
                    ),
                },
                "matched_lesson_id": {
                    "type": "string",
                    "description": (
                        "Optional: lesson ID that was checked but"
                        " did not help (for stale_lesson)."
                    ),
                },
                "source": {
                    "type": "string",
                    "description": (
                        "Calling client: codex, claude-code,"
                        " cursor, dsh, curl, or other."
                    ),
                },
            },
            "required": ["problem"],
        },
    },
    {
        "name": "misakanet_write_lesson",
        "description": (
            "Submit a complete, structured failure lesson. Use after"
            " resolving a problem and documenting the full failure→"
            "root cause→fix→verification chain. Requires a"
            " registered agent token (not anonymous). Input"
            " semantics: title, domain, problem, root_cause, fix"
            " (all required); verification, tags, token, source"
            " (optional). Output schema: JSON with lesson_id,"
            " status (pending_review), quality_score,"
            " quality_notes, redactions_applied, and receipt."
            " Error cases: missing required fields, anonymous"
            " token, quality score below 75 threshold, duplicate"
            " submission. Side effects: writes to"
            " data/contribution_queue.jsonl. Auth: registered"
            " agent token required."
            " Rate limits: local stdio process only."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": (
                        "Required lesson title — short, specific,"
                        " kebab-case friendly (e.g. 'pip install"
                        " timeout on corporate proxy')."
                    ),
                },
                "domain": {
                    "type": "string",
                    "description": (
                        "Required domain: devops, python, network,"
                        " feishu, rag, fanuc, mcp, docker, git, etc."
                    ),
                },
                "problem": {
                    "type": "string",
                    "description": (
                        "Required description of the failure"
                        " (max 2000 chars)."
                    ),
                },
                "root_cause": {
                    "type": "string",
                    "description": (
                        "Required root cause analysis —"
                        " why did it fail?"
                    ),
                },
                "fix": {
                    "type": "string",
                    "description": (
                        "Required fix — what resolved the problem?"
                    ),
                },
                "verification": {
                    "type": "string",
                    "description": (
                        "Optional: how to confirm the fix works."
                    ),
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Optional tags for categorization"
                        " (e.g. ['proxy', 'pip',"
                        " 'corporate-network'])."
                    ),
                },
                "token": {
                    "type": "string",
                    "description": (
                        "Registered agent token"
                        " (e.g. 'token:abc123')."
                        " Required for write_lesson."
                    ),
                },
                "source": {
                    "type": "string",
                    "description": (
                        "Calling client: codex, claude-code,"
                        " cursor, dsh, or other."
                    ),
                },
            },
            "required": ["title", "domain", "problem", "root_cause", "fix"],
        },
    },
    {
        "name": "misakanet_preflight",
        "description": (
            "Check risk level before executing high-risk operations."
            " Matches agent intent against lesson triggers to"
            " provide proactive warnings. Use before RAG builds,"
            " WSL/GPU tasks, bulk imports, or any operation that"
            " might fail. Input semantics: intent (required),"
            " context (optional). Output schema: JSON with risk"
            " level, matched lessons, and guards. Error cases:"
            " missing intent. Side effects: none. Auth: none."
            " Rate limits: local stdio process only."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "description": (
                        "Task intent description"
                        " (e.g. 'build RAG index from PDFs')"
                    ),
                },
                "context": {
                    "type": "string",
                    "description": (
                        "Environment context"
                        " (e.g. 'WSL, GPU 8GB')"
                    ),
                },
            },
            "required": ["intent"],
        },
    },
    {
        "name": "misakanet_usage_status",
        "description": (
            "Check current usage status and remaining quota."
            " Use to see how many free lesson reads remain and"
            " how many credits are available. Input semantics:"
            " user is optional (defaults to anonymous). Output"
            " schema: JSON with user, free_reads_used,"
            " free_reads_limit, free_reads_remaining, credits,"
            " is_registered, and next steps. Error cases: none."
            " Side effects: none. Auth: none. Rate limits: none."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "user": {
                    "type": "string",
                    "description": (
                        "Optional user identifier (e.g."
                        " 'anon:iphash' or 'token:xxx')."
                        " Defaults to 'anon:mcp-default'."
                    ),
                },
            },
        },
    },
    {
        "name": "misakanet_register",
        "description": (
            "Register an agent and receive a node_id and token"
            " for unlimited remote MCP access. Local stdio MCP"
            " is unlimited and does not need registration."
            " For remote HTTP MCP, call this tool first to get"
            " a token, then pass it as the user parameter in"
            " subsequent calls. Input semantics: agent_type is"
            " optional (defaults to 'unknown'). Output schema:"
            " JSON with node_id, token, registered_at, and"
            " agent_type. Error cases: none. Side effects:"
            " persists registration record. Auth: none."
            " Rate limits: one registration per session."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_type": {
                    "type": "string",
                    "description": (
                        "Optional agent type identifier (e.g."
                        " 'claude-code', 'cursor', 'aider')."
                        " Defaults to 'unknown'."
                    ),
                },
            },
        },
    },
    {
        "name": "misakanet_memory_context",
        "description": (
            "Pull relevant failure-memory lessons as context"
            " before starting a task. Call this at the beginning"
            " of a coding session or before attempting a"
            " non-trivial operation. Returns a condensed context"
            " block with matching lessons (problem + fix"
            " summaries) that can be injected into the agent's"
            " system prompt. Input semantics: task (required),"
            " domain (optional filter), top_n (optional,"
            " default 5, max 10). Output schema: JSON with task,"
            " lesson_count, lessons array, and context_block"
            " (ready-to-inject markdown). Error cases: missing"
            " task. Side effects: none. Auth: none."
            " Rate limits: none."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": (
                        "Task description (e.g. 'set up ChromaDB"
                        " RAG pipeline', 'deploy FastAPI to"
                        " production')."
                    ),
                },
                "domain": {
                    "type": "string",
                    "description": (
                        "Optional domain filter (e.g."
                        " 'search-and-retrieval', 'ci-cd')."
                    ),
                },
                "top_n": {
                    "type": "integer",
                    "description": (
                        "Number of lessons to retrieve"
                        " (default 5, max 10)."
                    ),
                },
            },
            "required": ["task"],
        },
    },
]


def _filtered_tools() -> list[dict]:
    """Return TOOLS filtered by MISAKA_TOOL_FILTER env var.

    Filter format:
        "+search,get_lesson" — allowlist (only these tools)
        "-write_lesson,preflight" — denylist (hide these tools)
        "+misakanet_*" — wildcard allowlist
        "-misakanet_write_*" — wildcard denylist

    Default (no filter): return all tools.
    """
    tool_filter = os.environ.get("MISAKA_TOOL_FILTER", "").strip()
    if not tool_filter:
        return TOOLS

    is_allowlist = tool_filter.startswith("+")
    is_denylist = tool_filter.startswith("-")

    if not (is_allowlist or is_denylist):
        # Default to allowlist if no prefix
        patterns = [
            p.strip() for p in tool_filter.split(",") if p.strip()
        ]
        is_allowlist = True
    else:
        patterns = [
            p.strip() for p in tool_filter[1:].split(",") if p.strip()
        ]

    if not patterns:
        return TOOLS

    def matches_any(tool_name: str) -> bool:
        return any(fnmatch.fnmatch(tool_name, p) for p in patterns)

    if is_allowlist:
        return [t for t in TOOLS if matches_any(t["name"])]
    else:
        return [t for t in TOOLS if not matches_any(t["name"])]
