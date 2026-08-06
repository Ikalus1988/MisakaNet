#!/usr/bin/env python3
"""Maintainer review CLI — accept/reject contributions and grant credits.

Usage:
    python3 scripts/contribution_review.py list [--status pending]
    python3 scripts/contribution_review.py show contrib_abc123
    python3 scripts/contribution_review.py accept contrib_abc123 --credits 20 [--note "verified"]
    python3 scripts/contribution_review.py reject contrib_abc123 --reason duplicate
    python3 scripts/contribution_review.py grant contrib_abc123 --credits 20

Credits are only granted on "accept". No auto-accept. No auto-grant.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.contribution_queue import get_contribution, list_contributions, update_status
from scripts.usage_meter import grant_credits

REPO_ROOT = Path(__file__).resolve().parent.parent

CREDIT_REWARDS = {
    "intake": 5,       # accepted intake report
    "lesson": 20,      # accepted lesson draft
}


def accept_contribution(contrib_id: str, credits: int = 0, note: str = "", reviewer: str = "maintainer") -> dict:
    """Accept a contribution and grant credits to the user."""
    contrib = get_contribution(contrib_id)
    if not contrib:
        return {"error": f"Not found: {contrib_id}"}

    if contrib["status"] != "pending":
        return {"error": f"Cannot accept: status is '{contrib['status']}', expected 'pending'"}

    # Update status to accepted
    updated = update_status(contrib_id, "accepted", note=note, reviewer=reviewer)
    if not updated:
        return {"error": "Failed to update status"}

    # Grant credits
    credit_amount = credits or CREDIT_REWARDS.get(contrib["type"], 10)
    user = contrib.get("user", "anonymous")
    grant_result = grant_credits(user, credit_amount, reason="accepted_contribution", contribution_id=contrib_id)

    return {
        "accepted": True,
        "id": contrib_id,
        "user": user,
        "credits_granted": credit_amount,
        "credits_total": grant_result["credits_total"],
        "note": note,
    }


def reject_contribution(contrib_id: str, reason: str = "", reviewer: str = "maintainer") -> dict:
    """Reject a contribution. No credits granted."""
    contrib = get_contribution(contrib_id)
    if not contrib:
        return {"error": f"Not found: {contrib_id}"}

    if contrib["status"] != "pending":
        return {"error": f"Cannot reject: status is '{contrib['status']}', expected 'pending'"}

    updated = update_status(contrib_id, "rejected", note=reason, reviewer=reviewer)
    if not updated:
        return {"error": "Failed to update status"}

    return {
        "rejected": True,
        "id": contrib_id,
        "reason": reason,
    }


def convert_to_draft(contrib_id: str, draft_type: str = "lesson", domain: str = "general") -> dict:
    """Convert a contribution to a lesson draft file."""
    contrib = get_contribution(contrib_id)
    if not contrib:
        return {"error": f"Not found: {contrib_id}"}

    if contrib["status"] not in ("pending", "accepted"):
        return {"error": f"Cannot convert: status is '{contrib['status']}'"}

    from datetime import datetime, timezone
    import re

    now = datetime.now(timezone.utc)
    title = contrib.get("title", "") or contrib.get("message", "")[:60]
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:40] or contrib_id

    # Build draft content
    problem = contrib.get("problem", "") or contrib.get("message", "")
    root_cause = contrib.get("root_cause", "")
    fix = contrib.get("fix", "")
    verification = contrib.get("verification", "")
    source = contrib.get("source", "")

    draft_content = f"""---
title: "{title}"
domain: "{domain}"
tags: [contributed, {draft_type}]
language: en
status: draft
source: "{source}"
contrib_id: "{contrib_id}"
created: "{now.strftime('%Y-%m-%d')}"
confidence: 0.70
---

## Problem

{problem}

## Root Cause

{root_cause if root_cause else '_Not specified in contribution._'}

## Solution

{fix if fix else '_Not specified in contribution._'}

## Verification

{verification if verification else '_Not specified in contribution._'}

## Redaction Note

This draft was auto-generated from a redacted contribution ({contrib_id}).
Review before publishing. Original contribution had {contrib.get('redaction_summary', {}).get('total', 0)} redactions applied.
"""

    # Write draft
    drafts_dir = REPO_ROOT / "lessons" / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    draft_path = drafts_dir / f"{slug}.md"
    draft_path.write_text(draft_content, encoding="utf-8")

    # Update status
    update_status(contrib_id, "converted", note=f"Draft: {draft_path.name}")

    return {
        "converted": True,
        "id": contrib_id,
        "draft_path": str(draft_path.relative_to(REPO_ROOT)),
        "draft_type": draft_type,
    }


def show_review_summary() -> dict:
    """Show summary of pending contributions for review."""
    pending = list_contributions(status="pending")
    accepted = list_contributions(status="accepted")
    rejected = list_contributions(status="rejected")

    return {
        "pending": len(pending),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "pending_items": [
            {"id": i["id"], "type": i["type"], "title": (i.get("title") or i.get("message", ""))[:60]}
            for i in pending
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Contribution review — accept/reject/grant")
    sub = parser.add_subparsers(dest="cmd")

    # list
    p_list = sub.add_parser("list", help="List contributions")
    p_list.add_argument("--status", default="pending")
    p_list.add_argument("--json", action="store_true")

    # show
    p_show = sub.add_parser("show", help="Show contribution details")
    p_show.add_argument("id")

    # accept
    p_accept = sub.add_parser("accept", help="Accept contribution and grant credits")
    p_accept.add_argument("id")
    p_accept.add_argument("--credits", type=int, default=0, help="Override credit amount (0=auto)")
    p_accept.add_argument("--note", default="")
    p_accept.add_argument("--reviewer", default="maintainer")

    # reject
    p_reject = sub.add_parser("reject", help="Reject contribution")
    p_reject.add_argument("id")
    p_reject.add_argument("--reason", default="")
    p_reject.add_argument("--reviewer", default="maintainer")

    # summary
    sub.add_parser("summary", help="Show review summary")

    # convert
    p_convert = sub.add_parser("convert", help="Convert contribution to lesson draft")
    p_convert.add_argument("id")
    p_convert.add_argument("--type", default="lesson", choices=["lesson", "rescue"])
    p_convert.add_argument("--domain", default="general")

    args = parser.parse_args()

    if args.cmd == "list":
        items = list_contributions(args.status)
        if getattr(args, "json", False):
            print(json.dumps(items, ensure_ascii=False, indent=2))
        else:
            if not items:
                print(f"  No {args.status} contributions.")
                return
            print(f"\n  {'ID':<22} {'Type':<8} {'User':<20} {'Title'}")
            print(f"  {'-'*22} {'-'*8} {'-'*20} {'-'*40}")
            for i in items:
                title = (i.get("title") or i.get("message", ""))[:40]
                print(f"  {i['id']:<22} {i['type']:<8} {i.get('user',''):<20} {title}")
        print()

    elif args.cmd == "show":
        contrib = get_contribution(args.id)
        if contrib:
            print(json.dumps(contrib, ensure_ascii=False, indent=2))
        else:
            print(f"  Not found: {args.id}", file=sys.stderr)
            sys.exit(1)

    elif args.cmd == "accept":
        result = accept_contribution(args.id, args.credits, args.note, args.reviewer)
        if "error" in result:
            print(f"  Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
        print(f"  Accepted: {result['id']}")
        print(f"  User: {result['user']}")
        print(f"  Credits granted: {result['credits_granted']}")
        print(f"  Credits total: {result['credits_total']}")

    elif args.cmd == "reject":
        result = reject_contribution(args.id, args.reason, args.reviewer)
        if "error" in result:
            print(f"  Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
        print(f"  Rejected: {result['id']}")
        if result["reason"]:
            print(f"  Reason: {result['reason']}")

    elif args.cmd == "convert":
        result = convert_to_draft(args.id, args.type, args.domain)
        if "error" in result:
            print(f"  Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
        print(f"  Converted: {result['id']}")
        print(f"  Draft: {result['draft_path']}")

    elif args.cmd == "summary":
        summary = show_review_summary()
        print(f"\n  Contribution Review Summary")
        print(f"  Pending:  {summary['pending']}")
        print(f"  Accepted: {summary['accepted']}")
        print(f"  Rejected: {summary['rejected']}")
        if summary["pending_items"]:
            print(f"\n  Pending items:")
            for item in summary["pending_items"]:
                print(f"    {item['id']}  [{item['type']}]  {item['title']}")
        print()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
