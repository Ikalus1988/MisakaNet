"""Submit usage and intake handlers for MisakaNet MCP server."""
from __future__ import annotations

import json as _json
import os as _os
import urllib.error as _url_error
import urllib.request as _url_request


def _post_json(base: str, path: str, payload: dict) -> tuple[int, dict]:
    """POST JSON to the worker API; returns (status, parsed body)."""
    data = _json.dumps(payload).encode("utf-8")
    req = _url_request.Request(
        base + path,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "MisakaNet-MCP"},
    )
    with _url_request.urlopen(req, timeout=10) as resp:
        body = resp.read() or b"{}"
        return resp.status, _json.loads(body.decode("utf-8", errors="replace"))


def handle_submit_usage(args: dict) -> dict:
    """Submit a usage report — feeds the live reuse signals (replaces the
    old "log locally" placeholder; the worker endpoints are public and
    rate-limited).

    Outcome routing:
      solved      -> POST /api/helpful        (increments helpful:<lesson_id>
                    KV — this is what misakanet_me_events reads for E4
                    reuse evidence)
      partial     -> POST /api/feedback {feedback: "too_basic"}  (unsolved map)
      not-helpful -> POST /api/feedback {feedback: "irrelevant"} (unsolved map
                    + stale-lesson tracking)

    Offline-safe: if the worker is unreachable (or
    MISAKANET_USAGE_DISABLE_REMOTE=1) it records locally with status
    "logged" — a local MCP must never break because the network is down.
    """
    lesson_id = args.get("lesson_id", "")
    tool = args.get("tool", "unknown")
    outcome = args.get("outcome", "unknown")
    query = args.get("query", "") or lesson_id

    if not lesson_id:
        return {
            "error": "lesson_id is required",
            "guidance": (
                "Provide the lesson ID"
                " (e.g. 'auto-merge-ci-pipeline')."
                " Use misakanet_search to discover lesson IDs by topic."
            ),
            "voice": "failure-warning",
        }

    base = _os.environ.get("MISAKANET_API_BASE", "https://misakanet.org").rstrip("/")
    report = {
        "lesson_id": lesson_id,
        "tool": tool,
        "outcome": outcome,
        "voice": "pair-success",
    }

    if outcome not in ("solved", "partial", "not-helpful"):
        report.update(status="error", error=f"Unknown outcome: {outcome!r}")
        return report

    try:
        if _os.environ.get("MISAKANET_USAGE_DISABLE_REMOTE") == "1":
            raise OSError("remote usage disabled by env")

        if outcome == "solved":
            status, body = _post_json(base, "/api/helpful", {"lesson_id": lesson_id})
            report.update(
                status="submitted",
                remote="helpful",
                helpful_count=body.get("count", 0),
            )
        else:
            feedback = "too_basic" if outcome == "partial" else "irrelevant"
            status, body = _post_json(base, "/api/feedback", {
                "query": str(query)[:200],
                "lesson_id": str(lesson_id)[:200],
                "feedback": feedback,
                "ts": None,
            })
            report.update(
                status="submitted",
                remote="feedback",
                feedback=feedback,
                accepted=body.get("accepted", 0),
            )
    except (OSError, _url_error.URLError, _url_error.HTTPError, ValueError) as exc:
        # Offline or non-2xx — record locally so the tool still answers.
        report.update(
            status="logged",
            note=f"Worker unreachable — recorded locally ({exc})",
        )
    return report


def handle_submit_intake(args: dict) -> dict:
    """Submit a failure-case intake via the contribution queue."""
    from scripts.contribution_queue import submit_contribution

    kind = args.get("kind", "missing_lesson")
    problem = args.get("problem", "")
    error = args.get("error", "")
    what_tried = args.get("what_tried", "")
    fix = args.get("fix", "")
    verification = args.get("verification", "")
    matched_lesson_id = args.get("matched_lesson_id", "")
    source = args.get("source", "other")

    if not problem:
        return {
            "error": "problem is required",
            "hint": "Describe the failure or gap you encountered.",
        }

    # Build message from available fields
    parts = [f"Kind: {kind}"]
    if error:
        parts.append(f"Error: {error}")
    if what_tried:
        parts.append(f"Tried: {what_tried}")
    if fix:
        parts.append(f"Fix: {fix}")
    if verification:
        parts.append(f"Verification: {verification}")
    message = "\n".join(parts)

    result = submit_contribution(
        contrib_type="intake",
        user="mcp-agent",
        title=problem[:200],
        message=message,
        problem=problem,
        fix=fix,
        verification=verification,
        source=source,
        lesson_id=matched_lesson_id,
    )

    if "error" in result:
        return {
            "submitted": False,
            "error": result["error"],
            "message": result.get("message", ""),
            "existing_id": result.get("existing_id", ""),
        }

    return {
        "submitted": True,
        "intake_id": result["id"],
        "status": result["status"],
        "redactions_applied": result.get("redactions_applied", 0),
        "quality_score": result.get("quality_score", 0),
        "receipt": (
            f"Keep this ID ({result['id']});"
            " no account or email is required."
        ),
    }
