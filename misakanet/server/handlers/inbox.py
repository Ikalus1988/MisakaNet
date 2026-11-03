"""Inbox handler — poll an intake's status without re-submitting it.

Why this is a proxy to the hosted *tool* (2026-11-03, #3577)
-----------------------------------------------------------
This handler used to GET `<origin>/api/inbox?...`. No such route exists: the worker answers
`404 {"error":"Not found"}`, so every lookup that was not in the local contribution queue was
reported as `status: "not_found"` — a claim the data cannot support. Measured against the live
endpoint on 2026-11-03 for the same intake:

    stdio   {"intake_id": "issue-1528", "status": "not_found",
             "note": "No intake found with this ID or dedup_key."}
    hosted  {"intake_id": "issue-1528", "status": "unknown",
             "note": "Nothing found in the D1 question table, the lesson corpus, or the dedup
                      store. Read this as 'cannot be determined', not 'never happened' ..."}

"Does not exist" and "cannot be determined" are different answers, and the stdio surface was
giving the stronger one. The hosted service exposes this read as the `misakanet_me_inbox` tool
(D1 `questions` → lesson-corpus citations → KV dedup store), so the local server calls that tool
through the package's one MCP client (`misakanet/remote.py`) instead of inventing a second wire
contract. `tests/test_me_inbox.py` pins the routing, the argument names, and the status vocabulary
against the hosted schema.

The local contribution queue is still consulted first: a `contrib_…` id only ever existed on this
machine, so no hosted lookup can answer for it.
"""
from __future__ import annotations

from misakanet import remote

# The hosted read is a few D1/KV lookups; keep the proxy short so a black-holed connection fails
# this call rather than the session (same bound as `me_events`).
_TIMEOUT_SECONDS = 15.0

_TOOL = "misakanet_me_inbox"


def _local_entry(intake_id: str, dedup_key: str) -> dict | None:
    """Find an intake in the local contribution queue, if there is one.

    A local queue id (`contrib_…`) only ever existed on this machine, so the hosted endpoint will
    never answer for it. Looking here first is what makes the local fallback's `poll_hint` true
    instead of a promise nothing can keep.
    """
    try:
        from scripts.contribution_queue import get_contribution, list_contributions
    except ImportError:
        return None  # not a repo checkout — `scripts/` is not shipped in the wheel
    if intake_id:
        try:
            entry = get_contribution(intake_id)
        except Exception:
            entry = None
        if entry:
            return entry
    if not dedup_key:
        return None
    try:
        entries = list_contributions(status="", limit=500)
    except Exception:
        return None
    for entry in entries:
        if entry.get("dedup_key") == dedup_key:
            return entry
    return None


def _local_answer(entry: dict) -> dict:
    """Answer for an intake that is still in the local queue."""
    issue_number = entry.get("issue_number") or entry.get("github_issue")
    issue_url = f"https://github.com/Ikalus1988/MisakaNet/issues/{issue_number}" if issue_number else ""
    return {
        "intake_id": entry.get("id", ""),
        "status": entry.get("status", "pending"),
        "delivery": "local_queue",
        "issue_url": issue_url,
        "note": "This intake is still in the local contribution queue — it has not reached "
                "MisakaNet, so there is no maintainer answer and no GitHub issue yet.",
    }


def handle_me_inbox(args: dict) -> dict:
    """Check the status of a previously submitted intake without re-submitting.

    Accepts an `intake_id` (e.g. 'issue-1234') or a `dedup_key` from a prior `submit_intake`
    response. The local contribution queue is consulted first — a locally queued intake has no
    hosted counterpart — and the hosted tool answers for everything else in its own words,
    including its own `unknown` when a lookup finds nothing but cannot conclude absence.

    Returns: {intake_id, status, answer?, lesson_id?, issue_url?, note}
    """
    intake_id = str(args.get("intake_id", "")).strip()
    dedup_key = str(args.get("dedup_key", "")).strip()
    if not intake_id and not dedup_key:
        return {"error": "intake_id or dedup_key is required"}

    local = _local_entry(intake_id, dedup_key)
    if local is not None:
        return _local_answer(local)

    payload: dict[str, str] = {}
    if intake_id:
        payload["intake_id"] = intake_id
    if dedup_key:
        payload["dedup_key"] = dedup_key

    try:
        result = remote.call(_TOOL, payload, timeout=_TIMEOUT_SECONDS)
    except Exception as exc:  # RemoteError, McpReplyUnreadable, McpRpcError, OSError
        # A read failure is not a verdict on the intake: name the failure instead of answering
        # `not_found`, which would claim the report never existed.
        return {
            "intake_id": intake_id or f"dedup-{dedup_key}",
            "status": "unknown",
            "error": "hosted_endpoint_unavailable",
            "note": f"Could not read the intake status from the hosted endpoint "
                    f"({type(exc).__name__}: {exc}). This answers nothing about whether the "
                    "intake exists — retry when the network is up.",
        }

    if not isinstance(result, dict):
        return {
            "intake_id": intake_id or f"dedup-{dedup_key}",
            "status": "unknown",
            "error": "unexpected_reply",
            "note": "The hosted endpoint answered with something that is not a tool payload.",
        }
    return result
