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


# The hosted endpoint's `misakanet_submit_intake` has a schema. Forwarding an unknown key is a
# silent no-op at best, so the field list is explicit here.
_INTAKE_FIELDS = (
    "kind", "problem", "error", "what_tried", "fix", "verification",
    "matched_lesson_id", "source",
)

# How long a caller should wait before re-checking, mirroring the hosted endpoint's own advice:
# a question gets a maintainer answer in hours, a failure report waits for a review.
_RECHECK_SECONDS = {"question": 21600}
_RECHECK_SECONDS_DEFAULT = 86400


def _submit_intake_remote(args: dict) -> tuple[dict | None, str]:
    """File the intake on the network. Returns `(payload, "")` or `(None, reason)`.

    The hosted worker is the only place an intake becomes a GitHub issue. The local queue is a
    repo-checkout staging area and **nothing drains it into an issue** — the only reader is the
    maintainer CLI `scripts/contribution_review.py` (verified 2026-10-20). So "submit" has to mean
    the network, and the local path is the degraded one that has to say so.
    """
    if _os.environ.get("MISAKANET_INTAKE_DISABLE_REMOTE") == "1":
        return None, "remote intake disabled by env"
    try:
        from ... import remote
    except ImportError as exc:  # pragma: no cover - the package always ships remote.py
        return None, f"remote client unavailable ({exc})"
    payload = {k: args[k] for k in _INTAKE_FIELDS if args.get(k) not in (None, "")}
    try:
        result = remote.call("misakanet_submit_intake", payload)
    except Exception as exc:  # RemoteError, McpReplyUnreadable, McpRpcError, OSError
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(result, dict):
        return None, "the endpoint answered with something that is not a tool payload"
    return result, ""


def _submit_intake_local(args: dict, reason: str) -> dict:
    """Queue the intake locally, with a receipt that says exactly that.

    The local queue is only reachable from a repo checkout (`scripts/` is not in the wheel —
    `pyproject.toml` ships `misakanet*` only), so an installed client that is also offline has
    nowhere to put the report and gets an error instead of a false success.
    """
    try:
        from scripts.contribution_queue import submit_contribution
    except ImportError as exc:
        return {
            "submitted": False,
            "error": "MisakaNet is unreachable and this installation has no local contribution queue",
            "detail": f"{reason}; local queue unavailable ({exc})",
            "hint": "Retry when the network is up, or file the report on GitHub: "
                    "https://github.com/Ikalus1988/MisakaNet/issues/new",
        }

    kind = args.get("kind", "missing_lesson")
    problem = args.get("problem", "")
    error = args.get("error", "")
    what_tried = args.get("what_tried", "")
    fix = args.get("fix", "")
    verification = args.get("verification", "")
    matched_lesson_id = args.get("matched_lesson_id", "")
    source = args.get("source", "other")

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

    intake_id = result["id"]
    # The key the queue actually stored — not a second, unrelated hash. A dedup key that names
    # nothing the queue holds cannot dedup anything.
    dedup_key = result.get("dedup_key", "")
    return {
        "submitted": True,
        "delivery": "local_queue",
        "intake_id": intake_id,
        "status": result.get("status", "pending"),
        "redactions_applied": result.get("redactions_applied", 0),
        "quality_score": result.get("quality_score", 0),
        "dedup_key": dedup_key,
        "poll_hint": {
            "tool": "misakanet_me_inbox",
            "argument": f"intake_id=\"{intake_id}\"",
            "how": "This intake is still in the local queue — it has not reached MisakaNet, so it "
                   "has no GitHub issue yet. me_inbox reports its local state; re-send the same "
                   "problem once the network is back.",
            "recheck_after_seconds": _RECHECK_SECONDS.get(kind, _RECHECK_SECONDS_DEFAULT),
        },
        "note": f"Worker unreachable ({reason}) — recorded in the local queue only. Nothing was "
                "filed on MisakaNet, and no maintainer will answer this one yet.",
        "receipt": (
            f"Keep this ID ({intake_id});"
            " it is a local queue id, not a GitHub issue number."
        ),
    }


def handle_submit_intake(args: dict) -> dict:
    """Submit a failure-case intake.

    Remote-first, the same shape as `handle_submit_usage` above: the report goes to the network,
    and only an unreachable network sends it to the local queue — with a receipt that says the
    report did not reach MisakaNet. The hosted worker owns the intake contract, so its receipt
    (`intake_id`, `dedup_key`, `poll_hint`) is passed through unchanged; the local path mirrors
    its shape so one reader handles both.
    """
    if not args.get("problem", ""):
        return {
            "error": "problem is required",
            "hint": "Describe the failure or gap you encountered.",
        }

    payload, reason = _submit_intake_remote(args)
    if payload is not None:
        result = dict(payload)
        result["delivery"] = "remote"
        return result
    return _submit_intake_local(args, reason)

