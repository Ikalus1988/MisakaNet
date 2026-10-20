"""Inbox handler — check intake status via the hosted worker API."""
from __future__ import annotations

import json as _json
import os as _os
import urllib.error as _url_error
import urllib.request as _url_request


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

    Accepts an intake_id (e.g. 'issue-1234') from a prior submit_intake
    response, or a dedup_key (the 16-char hash). The local contribution queue
    is consulted first — a locally queued intake has no hosted counterpart —
    and the hosted worker endpoint answers for everything else.

    Returns: {intake_id, status, answer?, lesson_id?, issue_url?, note}
    """
    intake_id = str(args.get("intake_id", "")).strip()
    dedup_key = str(args.get("dedup_key", "")).strip()
    if not intake_id and not dedup_key:
        return {"error": "intake_id or dedup_key is required"}

    local = _local_entry(intake_id, dedup_key)
    if local is not None:
        return _local_answer(local)

    base = _os.environ.get("MISAKANET_API_BASE", "https://misakanet.org").rstrip("/")

    # Build query params
    params = []
    if intake_id:
        params.append(f"intake_id={intake_id}")
    if dedup_key:
        params.append(f"dedup_key={dedup_key}")
    query = "&".join(params)

    try:
        url = f"{base}/api/inbox?{query}"
        req = _url_request.Request(
            url,
            method="GET",
            headers={"User-Agent": "MisakaNet-MCP"},
        )
        with _url_request.urlopen(req, timeout=10) as resp:
            body = resp.read() or b"{}"
            return _json.loads(body.decode("utf-8", errors="replace"))
    except _url_error.HTTPError as exc:
        if exc.code == 404:
            return {
                "intake_id": intake_id or f"dedup-{dedup_key}",
                "status": "not_found",
                "note": "No intake found with this ID or dedup_key.",
            }
        return {
            "error": f"Worker returned HTTP {exc.code}",
            "intake_id": intake_id or f"dedup-{dedup_key}",
            "status": "unknown",
        }
    except (OSError, _url_error.URLError, ValueError) as exc:
        return {
            "error": f"Worker unreachable: {exc}",
            "intake_id": intake_id or f"dedup-{dedup_key}",
            "status": "unknown",
            "note": "Could not reach the hosted endpoint. Try again later.",
        }