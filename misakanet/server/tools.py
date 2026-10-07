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
            " defaults to 5. kind filters by result type: 'lessons'"
            " (lesson files only), 'evidence' (results with"
            " evidence_refs or verification), 'related'"
            " (cross-referenced/tag-overlap), 'all' (default)."
            " kind is auto-detected from query intent when omitted"
            " (e.g. 'lesson about X' → lessons, 'evidence for X'"
            " → evidence). Set explain=true to return matched terms,"
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
                "kind": {
                    "type": "string",
                    "enum": ["all", "lessons", "evidence", "related"],
                    "description": (
                        "Filter results by kind: 'lessons' returns"
                        " only lesson files, 'evidence' returns"
                        " results with evidence_refs or high"
                        " evidence_level, 'related' returns"
                        " cross-referenced/tag-overlap results."
                        " Default 'all' returns everything."
                        " Auto-detected from query intent when"
                        " omitted (e.g. 'lesson about X' → lessons,"
                        " 'evidence for X' → evidence)."
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
                "include_stale": {
                    "type": "boolean",
                    "description": (
                        "Include stale and superseded lessons in"
                        " results. Default false — these are"
                        " filtered out to avoid误导 agents"
                        " with outdated information."
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
            " Input semantics: provide exactly one of path or id"
            " (path takes precedence if both are supplied); if"
            " neither is supplied the handler returns {error}."
            " `path` is a repo-relative path like"
            " lessons/core/auto-merge-ci-pipeline.md and is"
            " validated against directory traversal (must resolve"
            " under lessons/). `id` is the filename stem like"
            " auto-merge-ci-pipeline and is matched across the"
            " canonical (deduplicated) lesson set — mirrors and"
            " translations are reachable only by explicit path."
            " Output schema: JSON with {path, content}; content is"
            " truncated to 5000 characters for MCP context window."
            " Error cases: missing both path and id, lesson not"
            " found (returns a suggestion to search), path outside"
            " lessons/ directory. Side effects: none. Auth: none."
            " Rate limits: local stdio process only; fetch one"
            " lesson per call when possible."
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
            " a problem. Call this AFTER a lesson has been used"
            " and the outcome is known — use"
            " misakanet_usage_status to check remaining quota"
            " before submitting. Input semantics: lesson_id is"
            " required (the lesson that helped); tool names the"
            " calling client (e.g. 'claude-code', 'cursor');"
            " outcome should be solved, partial, not-helpful, or"
            " another short status. Output schema: JSON with"
            " {lesson_id, tool, outcome, status}. Error cases:"
            " missing lesson_id. Side effects: currently returns"
            " a local placeholder report only (remote submission"
            " is disabled when MISAKANET_USAGE_DISABLE_REMOTE=1)."
            " Auth: none. Rate limits: local stdio process only."
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
            " Matches agent intent against lesson triggers and"
            " risk profiles to provide proactive warnings before"
            " you start. Use before RAG builds, WSL/GPU tasks,"
            " bulk imports, or any operation that might fail."
            " Input semantics: intent (required) describes what"
            " you plan to do in concrete terms (e.g. 'build RAG"
            " pipeline with ChromaDB'); context (optional)"
            " describes the environment (e.g. 'WSL, GPU 8GB')."
            " Output schema: JSON with {risk_level"
            " (low|medium|high), intent, matched_lessons: [{id,"
            " title, domain, relevance}], guards: [string]}."
            " Matched lessons are pulled from the local corpus"
            " using keyword overlap — a high risk_level with"
            " empty matched_lessons means the profile matched"
            " (e.g. 'GPU' triggers the WSL profile) but no"
            " specific lesson was close enough. Guards are"
            " concrete 'do X before Y' suggestions drawn from"
            " matched profiles and lessons. Error cases: missing"
            " intent returns {error}. Side effects: none — this"
            " is a read-only check. Auth: none. Rate limits:"
            " local stdio process only."
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
            " Use before calling misakanet_submit_usage to see"
            " how many free lesson reads remain and whether"
            " registration is needed. Call misakanet_register"
            " if is_registered is false and you need write"
            " access. Input semantics: user is optional"
            " (defaults to 'anon:mcp-default'); pass the token"
            " from misakanet_register (e.g. 'token:xxx') to"
            " check a registered agent's quota. Output schema:"
            " JSON with {user, free_reads_used, free_reads_limit,"
            " free_reads_remaining, credits, is_registered,"
            " next}. Error cases: none (returns defaults on"
            " failure). Side effects: none. Auth: none."
            " Rate limits: none."
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
            " for unlimited remote MCP access. Reading needs no"
            " registration; only write tools do. Local stdio MCP"
            " is unlimited and does not need registration."
            " For remote HTTP MCP, call this tool first to get"
            " a token, then pass it as the user parameter in"
            " subsequent calls. Input semantics: agent_type is"
            " optional (defaults to 'unknown'); client_id is an"
            " optional stable identifier (8-64 chars of A-Z a-z"
            " 0-9 . _ : -) you generate once and keep private —"
            " with it, later calls return the same node_id and"
            " token (reused=true), without it each call mints a"
            " new node. SECURITY: client_id is a key, not a"
            " label — the server derives a deterministic node_id"
            " from it and returns the stored token if one exists,"
            " so knowing someone's client_id is enough to obtain"
            " their token. Generate a random UUID and store it"
            " like a secret; do not derive from hostname or"
            " workspace id. Output schema: JSON with {node_id,"
            " token, registered_at, agent_type, reused?}."
            " Error cases: invalid_client_id (wrong format)."
            " Side effects: persists registration record in"
            " usage_meter. Auth: none."
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
                "client_id": {
                    "type": "string",
                    "description": (
                        "Optional stable identifier for this client"
                        " (8-64 chars of A-Z a-z 0-9 . _ : -)."
                        " Generate it once and reuse it so later"
                        " calls return the same node instead of a"
                        " new one."
                    ),
                },
            },
        },
    },
    {
        "name": "misakanet_memory_context",
        "description": (
            "Proactive half of the pair: call this BEFORE starting a task so"
            " failure-memory is in context from the first step; call"
            " misakanet_search once a specific error has actually appeared."
            " Input semantics: `task` is required and is matched as lexical"
            " keyword/token overlap over lesson"
            " titles, summaries and tags (BM25 when the index is present, a"
            " plain scorer otherwise) — not embeddings — so pass the"
            " concrete nouns, tools and error words you are about to meet"
            " ('chromadb on an NTFS mount', 'docker multi-stage build OOM')"
            " rather than a goal ('make it faster'); intent-only phrasing"
            " retrieves nothing. How `domain` behaves: a hard filter over a"
            " closed vocabulary of the domains the lesson corpus declares (the"
            " repository's data/domains.json is the list; rag, devops, fanuc,"
            " python, ci, mcp are examples), and a value outside it returns"
            " zero lessons with no"
            " error — so leave it out unless you know the domain; an empty"
            " result *with* a domain set is usually the filter, not an empty"
            " corpus. How `top_n` behaves: silently clamped to 10 (larger"
            " values are accepted and reduced), and each lesson is trimmed to"
            " 200 characters per field inside context_block — past roughly five"
            " matches you spend prompt space faster than you gain information."
            " Output schema: Returns {task, lesson_count, lessons,"
            " context_block}; context_block is ready-to-inject markdown, and"
            " lesson_count 0 (voice='failure-warning') means the corpus has no"
            " match yet — retry with the raw error text or submit an intake,"
            " rather than reading it as a tool failure."
            " Error cases: a missing or empty `task` returns {error, hint,"
            " voice} instead of lessons; a `domain` outside the declared"
            " vocabulary returns zero lessons rather than an error; a missing"
            " or empty index degrades to the plain lexical scorer instead of"
            " failing."
            " Side effects: none — this is a read-only call, and it does not"
            " record usage or touch the network."
            " Auth: none."
            " Rate limits: none — matching runs against the lessons/ directory"
            " of the checkout this server was started from, so results are only"
            " as current as that checkout. Local stdio server only — the hosted"
            " endpoint exposes misakanet_search and misakanet_get_lesson"
            " instead."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": (
                        "What you are about to do, in the vocabulary of the"
                        " tools, systems and errors involved (e.g. 'set up a"
                        " ChromaDB RAG pipeline on WSL', 'deploy FastAPI behind"
                        " a corporate proxy'). Matched lexically, so include the"
                        " distinctive terms a lesson would use in its title or"
                        " problem statement."
                    ),
                },
                "domain": {
                    "type": "string",
                    "description": (
                        "Optional hard filter on the lesson's frontmatter"
                        " domain, from a closed vocabulary (e.g. 'rag',"
                        " 'devops', 'fanuc', 'python', 'ci', 'mcp'). It narrows"
                        " and never widens: an unknown value yields zero lessons"
                        " without an error, so omit it when unsure."
                    ),
                },
                "top_n": {
                    "type": "integer",
                    "description": (
                        "How many lessons to return (default 5). Values above 10"
                        " are accepted and silently clamped to 10. Each returned"
                        " lesson is truncated to 200 characters per field in"
                        " context_block, so ~5 is where extra matches start"
                        " costing more prompt budget than they add."
                    ),
                },
            },
            "required": ["task"],
        },
    },
    {
        # Added 2026-09-30 (owner decision D4=A, intake #2000 / #2486). The local stdio server used to
        # lack this tool while the hosted endpoint had it, so the skill's reuse-evidence step — the
        # one flow that verifies a contribution was actually reused — answered "Unknown tool" on a
        # local install, and neither surface's tool set contained the other. It is a proxy of the
        # hosted tool, because the evidence it returns is aggregated server-side (helpful votes,
        # regression citations, cross-node confirmation) and no checkout can compute it locally.
        #
        # The description below is the hosted definition verbatim (workers/register-proxy-sw.js,
        # MCP_TOOLS) followed by the local operating contract every stdio tool carries. Keeping the
        # hosted text as a prefix is not decoration: tests/test_mcp_capability_parity.py asserts it, so
        # the two surfaces cannot start teaching different behaviour for one tool name.
        "name": "misakanet_me_events",
        "description": (
            "[READ-ONLY EVIDENCE] Return evidence of a lesson being reused (E4 signals): "
            "helpful votes, regression-benchmark citations, and cross-node confirmation. Use "
            "to check whether a lesson is proven by real usage, not just self-reported. "
            "Provide lesson_id or lesson_path — if neither is supplied the tool returns "
            "{error}. Semantically 'misakanet_get_my_events' (evidence for the lessons your "
            "node submitted/used); kept as me_events for backward compatibility. No auth "
            "required (read-only, rate-limited).\n"
            "Returns: object {lesson_id, events: [{type, count|queries|sources, "
            "evidence_level}], evidence: 'E0'|'E3'|'E4', note}.\n"
            "Example: misakanet_me_events(lesson_id='dco-auto-fix-workflow')\n"
            "Input semantics: lesson_id (filename stem, e.g. dco-auto-fix-workflow) or "
            "lesson_path (e.g. lessons/core/dco-auto-fix-workflow.md) — the endpoint derives "
            "the id from the path the same way. Passing neither is refused before any network "
            "call. Output schema: proxied unchanged from the hosted tool (lesson_id, events[], "
            "evidence, note). Error cases: missing_lesson_reference when both arguments are "
            "absent; hosted_endpoint_unavailable when the hosted service cannot be reached or "
            "refuses the call — this is a proxy, so there is no local fallback, and an empty "
            "events list would be a different, wrong answer. Side effects: none (read-only, no "
            "local writes). Auth: none. Rate limits: the hosted endpoint's anonymous read "
            "burst window applies; the proxy adds no local limit."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "lesson_id": {
                    "type": "string",
                    "description": (
                        "Lesson ID (filename stem), e.g. dco-auto-fix-workflow. Either "
                        "lesson_id or lesson_path is required."
                    ),
                },
                "lesson_path": {
                    "type": "string",
                    "description": (
                        "Optional full path, e.g."
                        " lessons/core/dco-auto-fix-workflow.md. Either lesson_id or"
                        " lesson_path is required."
                    ),
                },
            },
            # Kept in step with the worker's definition; see the note there. `minProperties` is
            # outside the keyword subset a conservative MCP client accepts, and an unrecognised
            # keyword makes such a client register zero tools (#2967). These three branches say
            # "at least one of" and also allow both, which the handler resolves by preferring
            # lesson_id.
            "oneOf": [
                {"required": ["lesson_id"]},
                {"required": ["lesson_path"]},
                {"required": ["lesson_id", "lesson_path"]},
            ],
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
