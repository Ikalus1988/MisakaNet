#!/usr/bin/env python3
"""Usage meter — track lesson reads and manage credits.

Tracks anonymous/registered users reading full lessons.
Enforces free quota (5/day for anonymous, 20/day for registered).
Supports credit grants from accepted contributions.

Usage:
    python3 scripts/usage_meter.py status --user anon:iphash
    python3 scripts/usage_meter.py check --user anon:iphash --lesson dco-signoff-failed
    python3 scripts/usage_meter.py record --user anon:iphash --lesson dco-signoff-failed
    python3 scripts/usage_meter.py grant --user anon:iphash --credits 20 --reason accepted_contribution
    python3 scripts/usage_meter.py reset --user anon:iphash
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
USAGE_FILE = REPO_ROOT / "data" / "usage_credits.jsonl"

FREE_READ_LIMIT = 5  # per day for anonymous
REGISTERED_READ_LIMIT = 20  # per day for registered tokens
CREDIT_COST = 1  # credits consumed per private lesson read


def _load_records() -> list[dict]:
    """Load all usage records."""
    if not USAGE_FILE.exists():
        return []
    records = []
    for line in USAGE_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _save_record(record: dict) -> None:
    """Append a single usage record."""
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USAGE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def hash_ip(ip: str) -> str:
    """Hash IP for anonymous user ID."""
    return "anon:" + hashlib.sha256(ip.encode()).hexdigest()[:12]


def get_status(user: str) -> dict:
    """Get usage status for a user."""
    records = _load_records()
    today = _today()

    # Count today's free reads (those consumed within free quota)
    free_reads_today = 0
    # Count today's credit-consuming reads
    credit_reads_today = 0

    for r in records:
        if r.get("user") != user:
            continue
        if r.get("action") != "get_lesson":
            continue
        if not r.get("ts", "").startswith(today):
            continue
        if r.get("action_source") == "credit":
            credit_reads_today += 1
        else:
            free_reads_today += 1

    # Count total credits (grants - credit-consuming reads)
    credits_granted = 0
    credits_consumed = 0
    for r in records:
        if r.get("user") != user:
            continue
        if r.get("action") == "grant":
            credits_granted += r.get("credits", 0)
        elif r.get("action") == "get_lesson" and r.get("action_source") == "credit":
            credits_consumed += CREDIT_COST

    credits = max(0, credits_granted - credits_consumed)

    # Determine if user is registered (has any grant or is not anon:)
    is_registered = not user.startswith("anon:")
    limit = REGISTERED_READ_LIMIT if is_registered else FREE_READ_LIMIT

    return {
        "user": user,
        "free_reads_used": free_reads_today,
        "free_reads_limit": limit,
        "free_reads_remaining": max(0, limit - free_reads_today),
        "credits": credits,
        "credits_granted": credits_granted,
        "credits_consumed": credits_consumed,
        "is_registered": is_registered,
    }


def check_lesson(user: str, lesson_id: str) -> dict:
    """Check if user can read a lesson. Returns allowed/denied status."""
    status = get_status(user)

    # Within free limit
    if status["free_reads_remaining"] > 0:
        return {"allowed": True, "reason": "free_read", "remaining": status["free_reads_remaining"] - 1}

    # Has credits
    if status["credits"] > 0:
        return {"allowed": True, "reason": "credit", "credits_remaining": status["credits"] - CREDIT_COST}

    # Quota exceeded
    return {
        "allowed": False,
        "reason": "quota_exceeded",
        "message": f"You have used {status['free_reads_limit']} free full-lesson reads today.",
        "next": [
            "Submit a redacted intake with misakanet_submit_intake",
            "Contribute a reviewed lesson with misakanet_contribute_lesson",
        ],
    }


def record_read(user: str, lesson_id: str) -> dict:
    """Record a lesson read. Deducts from free quota or credits."""
    status = get_status(user)
    today = _today()

    # Determine cost source
    reads_today = status["free_reads_used"]
    is_registered = status["is_registered"]
    limit = REGISTERED_READ_LIMIT if is_registered else FREE_READ_LIMIT

    if reads_today < limit:
        action_source = "free_read"
    elif status["credits"] > 0:
        action_source = "credit"
    else:
        action_source = "free_read"  # Allow recording even if over quota (for analytics)

    record = {
        "user": user,
        "action": "get_lesson",
        "lesson_id": lesson_id,
        "action_source": action_source,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    _save_record(record)

    return {
        "recorded": True,
        "action_source": action_source,
        "free_reads_remaining": max(0, limit - reads_today - 1) if reads_today < limit else 0,
        "credits_remaining": status["credits"] - CREDIT_COST if action_source == "credit" else status["credits"],
    }


def grant_credits(user: str, credits: int, reason: str = "", contribution_id: str = "") -> dict:
    """Grant credits to a user (called after accepted contribution)."""
    record = {
        "user": user,
        "action": "grant",
        "credits": credits,
        "reason": reason,
        "contribution_id": contribution_id,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    _save_record(record)

    # get_status() now includes this grant in credits_granted
    status = get_status(user)
    return {
        "granted": True,
        "credits_added": credits,
        "credits_total": status["credits"],
    }


def record_reset_event(user: str) -> dict:
    """Record an admin reset event (audit trail only — does not affect quota)."""
    record = {
        "user": user,
        "action": "reset_event",
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    _save_record(record)
    return {"recorded": True, "user": user, "note": "This is an audit event only. To actually reset quota, clear usage_credits.jsonl."}


# Alias for backward compatibility
reset_user = record_reset_event


def main():
    parser = argparse.ArgumentParser(description="Usage meter — lesson read tracking and credits")
    sub = parser.add_subparsers(dest="cmd")

    # status
    p_status = sub.add_parser("status", help="Show usage status")
    p_status.add_argument("--user", required=True, help="User ID (e.g. anon:iphash or token:xxx)")

    # check
    p_check = sub.add_parser("check", help="Check if lesson read is allowed")
    p_check.add_argument("--user", required=True)
    p_check.add_argument("--lesson", required=True, help="Lesson ID")

    # record
    p_record = sub.add_parser("record", help="Record a lesson read")
    p_record.add_argument("--user", required=True)
    p_record.add_argument("--lesson", required=True)

    # grant
    p_grant = sub.add_parser("grant", help="Grant credits to user")
    p_grant.add_argument("--user", required=True)
    p_grant.add_argument("--credits", type=int, required=True)
    p_grant.add_argument("--reason", default="")
    p_grant.add_argument("--contribution-id", default="")

    # reset
    p_reset = sub.add_parser("reset", help="Reset user daily reads")
    p_reset.add_argument("--user", required=True)

    # hash-ip
    p_hash = sub.add_parser("hash-ip", help="Hash an IP address")
    p_hash.add_argument("--ip", required=True)

    args = parser.parse_args()

    if args.cmd == "status":
        status = get_status(args.user)
        print(json.dumps(status, indent=2))

    elif args.cmd == "check":
        result = check_lesson(args.user, args.lesson)
        print(json.dumps(result, indent=2))
        if not result.get("allowed"):
            sys.exit(1)

    elif args.cmd == "record":
        result = record_read(args.user, args.lesson)
        print(json.dumps(result, indent=2))

    elif args.cmd == "grant":
        result = grant_credits(args.user, args.credits, args.reason, args.contribution_id)
        print(json.dumps(result, indent=2))

    elif args.cmd == "reset":
        result = reset_user(args.user)
        print(json.dumps(result, indent=2))

    elif args.cmd == "hash-ip":
        print(hash_ip(args.ip))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
