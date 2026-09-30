"""Agent-readable inbox for answers and conversion receipts (#2056).

Polls D1 for answered questions and conversion receipts, keyed by
intake_id or dedup_key.  This is the pull-based channel that closes
the feedback loop for anonymous MCP users who can't receive email.

Usage from MCP:
    misakanet_me_inbox(intake_id="abc123")
    misakanet_me_inbox(dedup_key="def456")
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request


def _query_d1(sql: str, params: list | None = None) -> list[dict]:
    """Query D1 via the worker API."""
    base = os.environ.get("MISAKANET_API_BASE", "https://misakanet.org").rstrip("/")
    payload = {"sql": sql, "params": params or []}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/api/d1/query",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "MisakaNet-MCP"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
            return body.get("results", [])
    except (OSError, urllib.error.URLError, urllib.error.HTTPError):
        return []


def handle_me_inbox(args: dict) -> dict:
    """Check inbox for answered questions and conversion receipts.

    Input:
        intake_id: optional — the intake ID from submit_intake
        dedup_key: optional — the dedup hash from submit_intake

    Output:
        {events: [...], count: N, poll_hint: "..."} or {events: [], count: 0, ...}
    """
    intake_id = args.get("intake_id", "")
    dedup_key = args.get("dedup_key", "")

    if not intake_id and not dedup_key:
        return {
            "error": "Provide intake_id or dedup_key (from misakanet_submit_intake response)",
            "hint": "Use the intake_id or dedup_key returned when you submitted the intake.",
        }

    events = []

    # Try D1 questions table first (answered questions)
    try:
        if dedup_key:
            rows = _query_d1(
                "SELECT * FROM questions WHERE dedup_hash = ? AND status = 'answered' ORDER BY answered_at DESC LIMIT 5",
                [dedup_key],
            )
        elif intake_id:
            rows = _query_d1(
                "SELECT * FROM questions WHERE issue_number = ? AND status = 'answered' ORDER BY answered_at DESC LIMIT 5",
                [intake_id],
            )
        else:
            rows = []

        for row in rows:
            events.append({
                "type": "answered",
                "question": row.get("problem", ""),
                "answer": row.get("answer", ""),
                "issue_number": row.get("issue_number"),
                "answered_at": row.get("answered_at", ""),
                "evidence_level": row.get("evidence_level", "unverified"),
            })
    except Exception:
        pass  # D1 may be unavailable

    # Check local contribution queue for conversion receipts
    from pathlib import Path

    repo = Path(__file__).resolve().parent.parent.parent.parent
    queue_path = repo / "data" / "contribution_queue.jsonl"
    if queue_path.exists():
        try:
            for line in queue_path.read_text(encoding="utf-8").splitlines():
                entry = json.loads(line.strip())
                # Match by intake_id or dedup_key
                entry_id = entry.get("id", "")
                entry_dedup = hashlib.sha256(
                    f"{entry.get('kind', '')}:{entry.get('title', '')}:{entry.get('message', '')}".encode()
                ).hexdigest()[:16]

                if intake_id and entry_id != intake_id:
                    continue
                if dedup_key and entry_dedup != dedup_key:
                    continue

                status = entry.get("status", "")
                if status == "converted":
                    events.append({
                        "type": "converted",
                        "intake_id": entry_id,
                        "lesson_path": entry.get("note", ""),
                        "converted_at": entry.get("reviewed_at", ""),
                    })
                elif status == "accepted":
                    events.append({
                        "type": "accepted",
                        "intake_id": entry_id,
                        "note": entry.get("note", ""),
                    })
        except (json.JSONDecodeError, OSError):
            pass

    # Check intake receipts log
    receipts_path = repo / "data" / "intake_receipts.jsonl"
    if receipts_path.exists() and (intake_id or dedup_key):
        try:
            for line in receipts_path.read_text(encoding="utf-8").splitlines():
                entry = json.loads(line.strip())
                if intake_id and entry.get("contrib_id") == intake_id:
                    events.append({
                        "type": "lesson_published",
                        "lesson_path": entry.get("lesson_path", ""),
                        "evidence_level": entry.get("evidence_level", "unverified"),
                        "emitted_at": entry.get("emitted_at", ""),
                    })
        except (json.JSONDecodeError, OSError):
            pass

    if not events:
        return {
            "events": [],
            "count": 0,
            "status": "pending",
            "poll_hint": (
                "No answer yet. Questions are typically answered within 24-48 hours."
                " Call misakanet_me_inbox again later with the same intake_id or dedup_key."
            ),
        }

    return {
        "events": events,
        "count": len(events),
        "status": "resolved",
        "poll_hint": "Your submission has been processed. See events above for details.",
    }