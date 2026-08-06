#!/usr/bin/env python3
"""Contribution queue — intake/lesson drafts pending maintainer review.

No auto-accept. No auto-grant. Contributions enter as "pending" and
only move to "accepted"/"rejected" via contribution_review.py.

Usage:
    python3 scripts/contribution_queue.py submit --type intake --message "DCO failed" --source curl
    python3 scripts/contribution_queue.py submit --type lesson --title "Fix X" --problem "..." --fix "..."
    python3 scripts/contribution_queue.py list [--status pending]
    python3 scripts/contribution_queue.py show <id>
"""
import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.intake_redact import redact_payload, redaction_summary

REPO_ROOT = Path(__file__).resolve().parent.parent
QUEUE_FILE = REPO_ROOT / "data" / "contribution_queue.jsonl"

VALID_TYPES = {"intake", "lesson"}
VALID_STATUSES = {"pending", "needs_repro", "accepted", "rejected", "duplicate", "converted"}


def _load_queue() -> list[dict]:
    """Load all queued contributions."""
    if not QUEUE_FILE.exists():
        return []
    items = []
    for line in QUEUE_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items


def _save_queue(items: list[dict]) -> None:
    """Write queue to JSONL."""
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _dedup_key(item: dict) -> str:
    """Generate a dedup key from type + title/message hash."""
    text = item.get("title", "") or item.get("message", "") or ""
    return hashlib.sha256(text.lower().strip().encode()).hexdigest()[:16]


QUALITY_THRESHOLD = 75


def _quick_quality_check(item: dict) -> tuple[int, list[str]]:
    """Quick text-based quality check on contribution content. Returns (score, notes)."""
    score = 0
    notes = []

    # Has title (10 pts)
    title = item.get("title", "")
    if title and len(title) > 5:
        score += 10
    else:
        notes.append("Missing or short title")

    # Has problem description (20 pts)
    problem = item.get("problem", "") or item.get("message", "")
    if problem and len(problem) > 20:
        score += 20
    else:
        notes.append("Missing or short problem description")

    # Has root cause or fix (20 pts)
    fix = item.get("fix", "") or item.get("root_cause", "")
    if fix and len(fix) > 20:
        score += 20
    else:
        notes.append("Missing or short fix/root_cause")

    # Has verification (10 pts)
    verification = item.get("verification", "")
    if verification and len(verification) > 10:
        score += 10
    else:
        notes.append("Missing verification")

    # Content length bonus (10 pts)
    total_text = " ".join(str(v) for v in item.values() if isinstance(v, str))
    if len(total_text) > 200:
        score += 10

    # Structure bonus (10 pts)
    has_sections = any(
        item.get(f, "")
        for f in ("problem", "root_cause", "fix", "verification")
    )
    if has_sections:
        score += 10

    return min(score, 100), notes


def submit_contribution(
    contrib_type: str,
    user: str = "anonymous",
    title: str = "",
    message: str = "",
    problem: str = "",
    root_cause: str = "",
    fix: str = "",
    verification: str = "",
    source: str = "",
    lesson_id: str = "",
) -> dict:
    """Submit a contribution to the review queue."""
    if contrib_type not in VALID_TYPES:
        return {"error": f"Invalid type: {contrib_type}. Must be one of: {VALID_TYPES}"}

    # Build raw payload for redaction
    raw = {
        "title": title,
        "message": message,
        "problem": problem,
        "root_cause": root_cause,
        "fix": fix,
        "verification": verification,
    }

    # Redact secrets
    safe = redact_payload(raw)
    redact_sum = redaction_summary(raw, safe)

    # Check for empty content
    content_fields = [safe.get("title"), safe.get("message"), safe.get("problem"), safe.get("fix")]
    if not any(f and str(f).strip() for f in content_fields):
        return {"error": "At least one of title, message, problem, or fix must be non-empty"}

    # Dedup check
    queue = _load_queue()
    dk = _dedup_key(safe)
    for existing in queue:
        if existing.get("dedup_key") == dk and existing.get("status") == "pending":
            return {
                "error": "duplicate",
                "message": "A similar contribution is already pending review.",
                "existing_id": existing["id"],
            }

    now = datetime.now(timezone.utc).isoformat()
    item = {
        "id": "contrib_" + uuid.uuid4().hex[:10],
        "type": contrib_type,
        "user": user[:100],
        "status": "pending",
        "title": str(safe.get("title", ""))[:200],
        "message": str(safe.get("message", ""))[:2000],
        "problem": str(safe.get("problem", ""))[:2000],
        "root_cause": str(safe.get("root_cause", ""))[:2000],
        "fix": str(safe.get("fix", ""))[:2000],
        "verification": str(safe.get("verification", ""))[:1000],
        "source": source[:50],
        "lesson_id": lesson_id[:200],
        "dedup_key": dk,
        "redaction_summary": redact_sum,
        "submitted_at": now,
        "updated_at": now,
        "review_history": [],
    }

    # Quality check
    quality_score, quality_notes = _quick_quality_check(item)
    item["quality_score"] = quality_score
    item["quality_notes"] = quality_notes

    queue.append(item)
    _save_queue(queue)

    return {
        "submitted": True,
        "id": item["id"],
        "status": "pending",
        "dedup_key": dk,
        "quality_score": quality_score,
        "quality_notes": quality_notes,
        "redactions_applied": redact_sum.get("total", 0),
    }


def list_contributions(status: str = "", limit: int = 50) -> list[dict]:
    """List contributions with optional status filter."""
    items = _load_queue()
    if status:
        items = [i for i in items if i.get("status") == status]
    return items[-limit:]


def get_contribution(contrib_id: str) -> dict | None:
    """Get a single contribution by ID."""
    items = _load_queue()
    for item in items:
        if item["id"] == contrib_id:
            return item
    return None


def update_status(contrib_id: str, new_status: str, note: str = "", reviewer: str = "maintainer") -> dict | None:
    """Update contribution status (used by contribution_review.py)."""
    if new_status not in VALID_STATUSES:
        return None

    items = _load_queue()
    for item in items:
        if item["id"] == contrib_id:
            old_status = item["status"]
            item["status"] = new_status
            item["updated_at"] = datetime.now(timezone.utc).isoformat()
            item["review_history"].append({
                "from": old_status,
                "to": new_status,
                "note": note[:200],
                "reviewer": reviewer[:50],
                "ts": item["updated_at"],
            })
            _save_queue(items)
            return item
    return None


def main():
    parser = argparse.ArgumentParser(description="Contribution queue — submit and list")
    sub = parser.add_subparsers(dest="cmd")

    # submit
    p_submit = sub.add_parser("submit", help="Submit a contribution")
    p_submit.add_argument("--type", required=True, choices=["intake", "lesson"])
    p_submit.add_argument("--user", default="anonymous")
    p_submit.add_argument("--title", default="")
    p_submit.add_argument("--message", default="")
    p_submit.add_argument("--problem", default="")
    p_submit.add_argument("--root-cause", default="")
    p_submit.add_argument("--fix", default="")
    p_submit.add_argument("--verification", default="")
    p_submit.add_argument("--source", default="")
    p_submit.add_argument("--lesson-id", default="")

    # list
    p_list = sub.add_parser("list", help="List contributions")
    p_list.add_argument("--status", default="")
    p_list.add_argument("--limit", type=int, default=50)
    p_list.add_argument("--json", action="store_true")

    # show
    p_show = sub.add_parser("show", help="Show contribution details")
    p_show.add_argument("id", help="Contribution ID")

    args = parser.parse_args()

    if args.cmd == "submit":
        result = submit_contribution(
            contrib_type=args.type,
            user=args.user,
            title=args.title,
            message=args.message,
            problem=args.problem,
            root_cause=args.root_cause,
            fix=args.fix,
            verification=args.verification,
            source=args.source,
            lesson_id=args.lesson_id,
        )
        if "error" in result:
            print(f"  Error: {result['error']}", file=sys.stderr)
            if "existing_id" in result:
                print(f"  Existing: {result['existing_id']}", file=sys.stderr)
            sys.exit(1)
        print(f"  Submitted: {result['id']} (status={result['status']}, redactions={result['redactions_applied']})")

    elif args.cmd == "list":
        items = list_contributions(args.status, args.limit)
        if getattr(args, "json", False):
            print(json.dumps(items, ensure_ascii=False, indent=2))
        else:
            if not items:
                print("  No contributions.")
                return
            print(f"\n  {'ID':<22} {'Status':<12} {'Type':<8} {'Title'}")
            print(f"  {'-'*22} {'-'*12} {'-'*8} {'-'*40}")
            for i in items:
                print(f"  {i['id']:<22} {i['status']:<12} {i['type']:<8} {(i.get('title') or i.get('message',''))[:40]}")
        print()

    elif args.cmd == "show":
        item = get_contribution(args.id)
        if item:
            print(json.dumps(item, ensure_ascii=False, indent=2))
        else:
            print(f"  Not found: {args.id}", file=sys.stderr)
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
