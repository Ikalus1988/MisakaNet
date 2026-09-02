"""Write lesson handler for MisakaNet MCP server."""
from __future__ import annotations


def handle_write_lesson(args: dict) -> dict:
    """Submit a structured lesson via registered agent token."""
    from scripts.contribution_queue import submit_contribution

    title = args.get("title", "")
    domain = args.get("domain", "")
    problem = args.get("problem", "")
    root_cause = args.get("root_cause", "")
    fix = args.get("fix", "")
    verification = args.get("verification", "")
    tags = args.get("tags", [])
    source = args.get("source", "mcp-agent")
    token = args.get("token", "")

    # Validate required fields
    missing = []
    if not title:
        missing.append("title")
    if not domain:
        missing.append("domain")
    if not problem:
        missing.append("problem")
    if not root_cause:
        missing.append("root_cause")
    if not fix:
        missing.append("fix")

    if missing:
        return {
            "submitted": False,
            "error": f"Missing required fields: {', '.join(missing)}",
            "hint": (
                "write_lesson requires title, domain, problem,"
                " root_cause, and fix."
            ),
        }

    # Require registered agent token
    if not token or token.startswith("anon:"):
        return {
            "submitted": False,
            "error": "Registered agent token required",
            "hint": (
                "Use misakanet_submit_intake for anonymous submissions."
                " write_lesson requires a registered agent token."
            ),
        }

    # Build structured message
    parts = [
        f"# {title}",
        f"Domain: {domain}",
        f"Tags: {', '.join(tags) if tags else 'none'}",
        "",
        "## Problem",
        problem,
        "",
        "## Root Cause",
        root_cause,
        "",
        "## Fix",
        fix,
    ]
    if verification:
        parts.extend(["", "## Verification", verification])
    message = "\n".join(parts)

    result = submit_contribution(
        contrib_type="lesson",
        user=token,
        title=title,
        message=message,
        problem=problem,
        root_cause=root_cause,
        fix=fix,
        verification=verification,
        source=source,
    )

    if "error" in result:
        return {
            "submitted": False,
            "error": result["error"],
            "message": result.get("message", ""),
            "existing_id": result.get("existing_id", ""),
        }

    quality_score = result.get("quality_score", 0)
    if quality_score < 75:
        return {
            "submitted": False,
            "error": (
                f"Quality score too low: {quality_score}/100"
                " (minimum 75)"
            ),
            "quality_score": quality_score,
            "quality_notes": result.get("quality_notes", []),
            "hint": (
                "Improve problem description, root cause analysis,"
                " or add verification steps."
            ),
        }

    return {
        "submitted": True,
        "lesson_id": result["id"],
        "status": "pending_review",
        "quality_score": quality_score,
        "quality_notes": result.get("quality_notes", []),
        "redactions_applied": result.get("redactions_applied", 0),
        "receipt": (
            f"Lesson {result['id']} queued for review."
            f" Quality: {quality_score}/100."
        ),
    }
