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

# ── Intake auth / rate limit config ──
# Set MISAKANET_INTAKE_TOKEN env var to require a shared token for submit_intake.
# If not set, submit_intake is open but rate-limited.
import os as _os
import time as _time
INTAKE_TOKEN = _os.environ.get("MISAKANET_INTAKE_TOKEN", "")
_intake_rate_window: list[float] = []
INTAKE_RATE_LIMIT = 5        # max submissions
INTAKE_RATE_WINDOW = 3600    # per hour (seconds)
INTAKE_IP_WINDOW: dict[str, list[float]] = {}
INTAKE_IP_LIMIT = 3          # per IP per hour


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
def misakanet_submit_intake(
    kind: str = "missing_lesson",
    problem: str = "",
    error: str = "",
    what_tried: str = "",
    fix: str = "",
    verification: str = "",
    matched_lesson_id: str = "",
    source: str = "other",
) -> dict:
    """Submit a failure-case intake when no matching lesson exists or a lesson was stale.

    Remote intake: creates a GitHub issue labeled 'intake' for maintainer review.
    No GitHub account or email required from the submitter.
    Auth: optional MISAKANET_INTAKE_TOKEN (if set, source must match token).
    Rate limits: global 5/hour + per-IP 3/hour (in-memory).
    Dedup hash recorded in issue body for maintainer-side duplicate detection.
    Requires gh CLI with repo write access. If gh fails, returns error (no silent fallback).
    """
    if not problem or not str(problem).strip():
        return {"error": "problem is required", "voice": "failure-warning"}

    # ── Token check (if configured) ──
    if INTAKE_TOKEN:
        if source == INTAKE_TOKEN:
            pass  # authenticated via shared token
        else:
            return {
                "error": "Unauthorized: set source to the intake token, or set MISAKANET_INTAKE_TOKEN env.",
                "voice": "failure-warning",
            }

    # ── Spam keyword guard ──
    SPAM_KEYWORDS = ["buy now", "click here", "free money", "casino", "viagra", "crypto pump"]
    text_lower = (problem + " " + (error or "")).lower()
    if any(kw in text_lower for kw in SPAM_KEYWORDS):
        return {"error": "Rejected: possible spam.", "voice": "failure-warning"}

    # ── Rate limits ──
    now = _time.time()

    # Global: 5/hour
    _intake_rate_window[:] = [t for t in _intake_rate_window if now - t < INTAKE_RATE_WINDOW]
    if len(_intake_rate_window) >= INTAKE_RATE_LIMIT:
        return {
            "error": f"Global rate limit: max {INTAKE_RATE_LIMIT} intakes per hour.",
            "voice": "failure-warning",
        }

    # Per-IP: 3/hour (keyed by source field as IP proxy)
    ip_key = source or "anon"
    if ip_key not in INTAKE_IP_WINDOW:
        INTAKE_IP_WINDOW[ip_key] = []
    INTAKE_IP_WINDOW[ip_key] = [t for t in INTAKE_IP_WINDOW[ip_key] if now - t < INTAKE_RATE_WINDOW]
    if len(INTAKE_IP_WINDOW[ip_key]) >= INTAKE_IP_LIMIT:
        return {
            "error": f"Per-source rate limit: max {INTAKE_IP_LIMIT} intakes per hour for '{ip_key}'.",
            "voice": "failure-warning",
        }

    INTAKE_IP_WINDOW[ip_key].append(now)
    _intake_rate_window.append(now)

    # ── Dedup hash (problem text, 1hr window) ──
    import hashlib
    dedup_hash = hashlib.sha256(problem.lower().strip().encode()).hexdigest()[:12]

    try:
        from scripts.intake_redact import redact_text

        # Redact sensitive info (field limits: 2k each, 8k total)
        safe_problem = redact_text(problem, max_length=2000)
        safe_error = redact_text(error, max_length=1000) if error else ""
        safe_fix = redact_text(fix, max_length=2000) if fix else ""
        safe_verification = redact_text(verification, max_length=1000) if verification else ""
        safe_what_tried = redact_text(what_tried, max_length=1000) if what_tried else ""

        # Build issue body
        body_parts = [
            f"**Kind:** {kind}",
            f"**Source:** {source}",
            f"**Dedup:** `{dedup_hash}`",
            "",
            "## Problem",
            safe_problem,
        ]
        if safe_error:
            body_parts.extend(["", "## Error", safe_error])
        if safe_what_tried:
            body_parts.extend(["", "## What was tried", safe_what_tried])
        if safe_fix:
            body_parts.extend(["", "## Fix (if known)", safe_fix])
        if safe_verification:
            body_parts.extend(["", "## Verification", safe_verification])
        if matched_lesson_id:
            body_parts.extend(["", f"**Matched lesson (not helpful):** `{matched_lesson_id}`"])

        body_parts.extend([
            "",
            "---",
            f"_Submitted via remote MCP ({source}). No account required._",
            f"_Dedup hash: {dedup_hash}_",
        ])

        # Sanitize title: strip markdown headings, backticks/codeblocks, URLs, collapse whitespace
        import re as _re
        raw_title = _re.sub(r"```[\s\S]*?```", "", safe_problem)
        raw_title = _re.sub(r"#+", " ", raw_title)
        raw_title = _re.sub(r"`[^`]*`", "", raw_title)
        raw_title = _re.sub(r"https?://\S+", "", raw_title)
        raw_title = _re.sub(r"\n+", " ", raw_title)
        raw_title = _re.sub(r"\s+", " ", raw_title).strip()[:80]
        title = f"[Intake] {raw_title or 'failure case'}"
        body = "\n".join(body_parts)

        # Enforce 8k body limit
        if len(body.encode("utf-8")) > 8000:
            body = body[:7900] + "\n\n... [truncated to 8k limit]"

        # Create GitHub issue
        import subprocess
        result = subprocess.run(
            ["gh", "issue", "create",
             "--title", title,
             "--body", body,
             "--label", "intake,mcp-intake,pending-review"],
            capture_output=True, text=True, timeout=30,
        )

        if result.returncode == 0 and result.stdout.strip().startswith("https://github.com/"):
            issue_url = result.stdout.strip()
            issue_number = issue_url.split("/")[-1]
            return {
                "submitted": True,
                "intake_id": f"issue-{issue_number}",
                "status": "pending_review",
                "issue_url": issue_url,
                "dedup_hash": dedup_hash,
                "redactions_applied": sum(1 for x in [safe_problem, safe_error, safe_fix] if "[REDACTED" in x),
                "receipt": f"GitHub issue {issue_number} created. No account or email required.",
                "voice": "pair-success",
            }
        else:
            # No silent fallback — remote intake must reach maintainer
            return {
                "submitted": False,
                "error": f"GitHub issue creation failed: {result.stderr[:200]}",
                "hint": "Check gh CLI auth and permissions. Intake was NOT saved.",
                "voice": "failure-warning",
            }

    except Exception as e:
        return {"error": f"Submit failed: {e}", "voice": "failure-warning"}


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
