"""Inbox handler — check intake status via the hosted worker API."""
from __future__ import annotations

import json as _json
import os as _os
import urllib.error as _url_error
import urllib.request as _url_request


def handle_me_inbox(args: dict) -> dict:
    """Check the status of a previously submitted intake without re-submitting.

    Accepts an intake_id (e.g. 'issue-1234') from a prior submit_intake
    response, or a dedup_key (the 16-char hash). Calls the hosted worker
    endpoint for the actual lookup — the local server has no durable state.

    Returns: {intake_id, status, answer?, lesson_id?, issue_url?, note}
    """
    intake_id = str(args.get("intake_id", "")).strip()
    dedup_key = str(args.get("dedup_key", "")).strip()
    if not intake_id and not dedup_key:
        return {"error": "intake_id or dedup_key is required"}

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