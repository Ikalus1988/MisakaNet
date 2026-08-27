#!/usr/bin/env python3
"""Demand board — track intake clusters and their triage states.

States: new → reviewed → routed | rejected
Maintainers can override category and state.

Usage:
    # Add an intake signal
    python3 scripts/demand_board.py record --family python-env --reason "pip timeout" --source curl

    # List all demand items
    python3 scripts/demand_board.py list

    # Override category/state
    python3 scripts/demand_board.py override --id <item-id> --state reviewed --category lesson

    # Summary (for API/dashboard)
    python3 scripts/demand_board.py summary --json
"""
import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BOARD_FILE = REPO_ROOT / "data" / "demand-board.jsonl"

TASK_FAMILY_WHITELIST = [
    "github-auth", "npm-publish", "cloudflare-worker", "mcp-registry",
    "glama-release", "python-env", "database-lock", "crawler-block",
    "agent-tooling", "lesson-feedback", "rescue-feedback", "bug-report",
    "unclassified",
]

VALID_STATES = {"new", "reviewed", "routed", "rejected"}
VALID_CATEGORIES = {"lesson", "rescue", "bug", "noise", "unknown"}


def normalize_family(family: str) -> str:
    """Constrain to whitelist."""
    return family if family in TASK_FAMILY_WHITELIST else "unclassified"


def load_board() -> list[dict]:
    """Load all demand board items."""
    if not BOARD_FILE.exists():
        return []
    items = []
    for line in BOARD_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items


def save_board(items: list[dict]) -> None:
    """Write board items to JSONL."""
    BOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(BOARD_FILE, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def record_signal(family: str, reason: str = "", source: str = "", category: str = "unknown") -> dict:
    """Record a new unsolved signal."""
    items = load_board()
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "id": uuid.uuid4().hex[:12],
        "family": normalize_family(family),
        "reason": reason[:200] if reason else "unspecified",
        "source": source[:50] if source else "unknown",
        "category": category if category in VALID_CATEGORIES else "unknown",
        "state": "new",
        "count": 1,
        "first_seen": now,
        "last_seen": now,
        "override_history": [],
    }

    # Check for existing item with same family+reason (aggregate)
    for existing in items:
        if existing["family"] == item["family"] and existing["reason"] == item["reason"]:
            existing["count"] += 1
            existing["last_seen"] = now
            save_board(items)
            return existing

    items.append(item)
    save_board(items)
    return item


def override_item(item_id: str, state: str = "", category: str = "", note: str = "") -> dict | None:
    """Maintainer override: change state or category."""
    items = load_board()
    for item in items:
        if item["id"] == item_id:
            history_entry = {"ts": datetime.now(timezone.utc).isoformat()}

            if state and state in VALID_STATES:
                history_entry["old_state"] = item["state"]
                history_entry["new_state"] = state
                item["state"] = state

            if category and category in VALID_CATEGORIES:
                history_entry["old_category"] = item["category"]
                history_entry["new_category"] = category
                item["category"] = category

            if note:
                history_entry["note"] = note[:200]

            item["override_history"].append(history_entry)
            save_board(items)
            return item
    return None


def get_summary() -> dict:
    """Aggregate summary for API/dashboard."""
    items = load_board()
    by_state = {}
    by_family = {}
    by_category = {}

    for item in items:
        state = item.get("state", "new")
        family = item.get("family", "unclassified")
        category = item.get("category", "unknown")

        by_state[state] = by_state.get(state, 0) + 1
        by_family[family] = by_family.get(family, 0) + 1
        by_category[category] = by_category.get(category, 0) + 1

    return {
        "total": len(items),
        "by_state": dict(sorted(by_state.items())),
        "by_family": dict(sorted(by_family.items(), key=lambda x: -x[1])),
        "by_category": dict(sorted(by_category.items(), key=lambda x: -x[1])),
        "states": list(VALID_STATES),
        "categories": list(VALID_CATEGORIES),
    }


def list_items(state: str = "", family: str = "", limit: int = 50) -> list[dict]:
    """List items with optional filters."""
    items = load_board()
    if state:
        items = [i for i in items if i.get("state") == state]
    if family:
        items = [i for i in items if i.get("family") == family]
    return items[-limit:]


# ── Gap analysis: zero-result search queries (Issue #1164) ──

GAPS_FILE = REPO_ROOT / "data" / "search_gaps.jsonl"


def load_gaps() -> list[dict]:
    """Load zero-result search queries."""
    if not GAPS_FILE.exists():
        return []
    gaps = []
    with open(GAPS_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                gaps.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
    return gaps


def get_gap_summary(top: int = 20) -> dict:
    """Aggregate gap data: cluster similar queries, rank by frequency."""
    gaps = load_gaps()
    if not gaps:
        return {"total": 0, "clusters": []}

    # Count query frequencies
    from collections import Counter
    query_counts = Counter(g["query"].lower().strip() for g in gaps)

    # Simple clustering: merge queries with >50% word overlap
    clusters = []
    used = set()
    for query, count in query_counts.most_common():
        if query in used:
            continue
        words = set(query.split())
        cluster = {"queries": [query], "count": count}
        used.add(query)

        for other_query, other_count in query_counts.items():
            if other_query in used:
                continue
            other_words = set(other_query.split())
            if not words or not other_words:
                continue
            overlap = len(words & other_words) / max(len(words), len(other_words))
            if overlap >= 0.5:
                cluster["queries"].append(other_query)
                cluster["count"] += other_count
                used.add(other_query)

        cluster["representative"] = cluster["queries"][0]
        clusters.append(cluster)

    clusters.sort(key=lambda c: c["count"], reverse=True)
    return {
        "total": len(gaps),
        "unique_queries": len(query_counts),
        "clusters": clusters[:top],
    }


def main():
    parser = argparse.ArgumentParser(description="Demand board — intake cluster tracking")
    sub = parser.add_subparsers(dest="cmd")

    # record
    p_rec = sub.add_parser("record", help="Record an unsolved signal")
    p_rec.add_argument("--family", required=True, help="Task family")
    p_rec.add_argument("--reason", default="", help="Short reason (max 200 chars)")
    p_rec.add_argument("--source", default="", help="Source type (curl, mcp, agent, etc.)")
    p_rec.add_argument("--category", default="unknown", help="Initial category")

    # list
    p_list = sub.add_parser("list", help="List demand items")
    p_list.add_argument("--state", default="", help="Filter by state")
    p_list.add_argument("--family", default="", help="Filter by family")
    p_list.add_argument("--limit", type=int, default=50)
    p_list.add_argument("--json", action="store_true")

    # override
    p_ovr = sub.add_parser("override", help="Maintainer override")
    p_ovr.add_argument("--id", required=True, help="Item ID")
    p_ovr.add_argument("--state", default="", help="New state")
    p_ovr.add_argument("--category", default="", help="New category")
    p_ovr.add_argument("--note", default="", help="Override note")

    # gaps
    p_gaps = sub.add_parser("gaps", help="Show zero-result search gap clusters")
    p_gaps.add_argument("--top", type=int, default=10, help="Top N clusters")
    p_gaps.add_argument("--json", action="store_true")

    # summary
    p_sum = sub.add_parser("summary", help="Show summary")
    p_sum.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.cmd == "record":
        item = record_signal(args.family, args.reason, args.source, args.category)
        print(f"  Recorded: {item['id']} ({item['family']}) count={item['count']}")

    elif args.cmd == "list":
        items = list_items(args.state, args.family, args.limit)
        if getattr(args, "json", False):
            print(json.dumps(items, ensure_ascii=False, indent=2))
        else:
            if not items:
                print("  No items.")
                return
            print(f"\n  {'ID':<14} {'State':<10} {'Family':<20} {'Cat':<10} {'Count':<6} {'Reason'}")
            print(f"  {'-'*14} {'-'*10} {'-'*20} {'-'*10} {'-'*6} {'-'*40}")
            for i in items:
                print(f"  {i['id']:<14} {i['state']:<10} {i['family']:<20} {i['category']:<10} {i['count']:<6} {i['reason'][:40]}")
        print()

    elif args.cmd == "override":
        item = override_item(args.id, args.state, args.category, args.note)
        if item:
            print(f"  Updated: {item['id']} state={item['state']} category={item['category']}")
        else:
            print(f"  Not found: {args.id}", file=sys.stderr)
            sys.exit(1)

    elif args.cmd == "gaps":
        gap_summary = get_gap_summary(args.top)
        if getattr(args, "json", False):
            print(json.dumps(gap_summary, ensure_ascii=False, indent=2))
        else:
            print(f"\n  Search Gaps — {gap_summary['total']} zero-result queries")
            if gap_summary.get("unique_queries"):
                print(f"  Unique queries: {gap_summary['unique_queries']}")
            if not gap_summary["clusters"]:
                print("  No gap data yet. Search queries with zero results are logged to data/search_gaps.jsonl")
            else:
                print(f"\n  {'#':<4} {'Count':<8} Representative")
                print(f"  {'-'*4} {'-'*8} {'-'*50}")
                for idx, c in enumerate(gap_summary["clusters"], 1):
                    print(f"  {idx:<4} {c['count']:<8} {c['representative']}")
        print()

    elif args.cmd == "summary":
        summary = get_summary()
        if getattr(args, "json", False):
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(f"\n  Demand Board — {summary['total']} items")
            print(f"\n  By state:")
            for s, c in summary["by_state"].items():
                print(f"    {s:<12} {c}")
            print(f"\n  By family:")
            for f, c in summary["by_family"].items():
                print(f"    {f:<20} {c}")
            print(f"\n  By category:")
            for cat, c in summary["by_category"].items():
                print(f"    {cat:<12} {c}")

        # Gap integration in summary
        gap_summary = get_gap_summary(5)
        if gap_summary["total"] > 0:
            print(f"\n  Top Content Gaps ({gap_summary['total']} zero-result queries):")
            for idx, c in enumerate(gap_summary["clusters"][:5], 1):
                print(f"    {idx}. {c['representative']} ({c['count']}x)")
        print()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
