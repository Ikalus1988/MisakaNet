#!/usr/bin/env python3
"""Pull and classify intake submissions from JSONL.

Usage:
    python3 scripts/intake_digest.py [--input data/contribution_queue.jsonl] [--since 7d] [--top 20]

Reads intake or contribution records, classifies them, and prints a summary.
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


def _parse_since(duration: str) -> datetime | None:
    m = re.fullmatch(r"(\d+)([dhm])", duration.strip())
    if not m:
        return None
    value, unit = int(m.group(1)), m.group(2)
    now = datetime.now(timezone.utc)
    if unit == "d":
        return now - __import__("datetime").timedelta(days=value)
    if unit == "h":
        return now - __import__("datetime").timedelta(hours=value)
    if unit == "m":
        return now - __import__("datetime").timedelta(minutes=value)
    return None


def _parse_ts(record: dict) -> datetime | None:
    for key in ("submitted_at", "timestamp", "created_at", "ts"):
        raw = record.get(key)
        if not raw:
            continue
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
    return None


def load_intakes(path: Path) -> list[dict]:
    records = []
    if not path.exists():
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONError:
                continue
    return records


def _dedup_key(item: dict) -> str:
    text = item.get("title", "") or item.get("message", "") or ""
    import hashlib
    return hashlib.sha256(text.lower().strip().encode()).hexdigest()[:16]


def classify(records: list[dict]) -> dict:
    by_type = Counter(r.get("type", "unknown") for r in records)
    by_source = Counter(r.get("source", "unknown") for r in records)
    by_status = Counter(r.get("status", "unknown") for r in records)
    by_consent = Counter(r.get("consent", "private_only") for r in records)
    return {
        "total": len(records),
        "by_type": dict(by_type.most_common()),
        "by_source": dict(by_source.most_common()),
        "by_status": dict(by_status.most_common()),
        "by_consent": dict(by_consent.most_common()),
    }


def summarize(records: list[dict]) -> dict:
    stats = classify(records)
    pending = [r for r in records if r.get("status") == "pending"]
    duplicates = defaultdict(list)
    for r in records:
        duplicates[_dedup_key(r)].append(r.get("id", "?"))
    dup_groups = {k: v for k, v in duplicates.items() if len(v) > 1}
    redacted = sum(1 for r in records if r.get("redaction_summary", {}).get("total", 0) > 0)
    categories = defaultdict(int)
    for r in records:
        categories[r.get("type", "unknown")] += 1
    return {
        "stats": stats,
        "pending_count": len(pending),
        "pending_ids": [r.get("id", "?") for r in pending[:20]],
        "redacted_count": redacted,
        "duplicate_groups": dup_groups,
        "categories": dict(sorted(categories.items(), key=lambda x: -x[1])),
    }


def main():
    parser = argparse.ArgumentParser(description="Intake digest — summarize submissions")
    parser.add_argument("--input", "-i", default="data/contribution_queue.jsonl",
                        help="Path to JSONL input (default: data/contribution_queue.jsonl)")
    parser.add_argument(
        "--since", default="",
        help="Filter records since duration (e.g. 7d, 12h, 30m)"
    )
    parser.add_argument("--top", type=int, default=20, help="Show top N recent entries")
    args = parser.parse_args()

    path = Path(args.input)
    records = load_intakes(path)

    cutoff = _parse_since(args.since) if args.since else None
    if cutoff:
        records = [r for r in records if (_parse_ts(r) or datetime.now(timezone.utc)) >= cutoff]

    if not records:
        print("No intake records found.")
        return

    summary = summarize(records)
    stats = summary["stats"]

    print(f"\n{'='*50}")
    print(f"  Intake Digest — {stats['total']} records")
    print(f"{'='*50}")
    print("\n  By type:")
    for t, c in stats["by_type"].items():
        print(f"    {t:<20} {c}")
    print("\n  By status:")
    for s, c in stats["by_status"].items():
        print(f"    {s:<20} {c}")
    print("\n  By source:")
    for s, c in stats["by_source"].items():
        print(f"    {s:<20} {c}")
    print(f"\n  Redacted count: {summary['redacted_count']}")
    print(f"  Pending review: {summary['pending_count']}")
    if summary["pending_ids"]:
        for pid in summary["pending_ids"]:
            print(f"    - {pid}")
    if summary["duplicate_groups"]:
        print(f"\n  Duplicate groups ({len(summary['duplicate_groups'])}):")
        for dk, ids in summary["duplicate_groups"].items():
            print(f"    {dk}: {', '.join(ids)}")

    print(f"\n  Recent ({min(args.top, len(records))}):")
    print(f"  {'ID':<10} {'Type':<18} {'Status':<12} {'Title/Message'}")
    print(f"  {'-'*10} {'-'*18} {'-'*12} {'-'*40}")
    for r in records[-args.top:]:
        rid = r.get("id", "?")[:10]
        rtype = r.get("type", "?")[:16]
        rstatus = r.get("status", "?")[:10]
        msg = r.get("title", "") or r.get("message", "") or ""
        msg = msg[:40]
        print(f"  {rid:<10} {rtype:<18} {rstatus:<12} {msg}")
    print()


if __name__ == "__main__":
    main()
