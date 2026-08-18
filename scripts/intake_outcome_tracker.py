#!/usr/bin/env python3
"""Privacy-preserving intake outcome tracker.

Tracks anonymous intake funnel metrics without storing private text.

Usage:
    python3 scripts/intake_outcome_tracker.py [--input data/contribution_queue.jsonl]
    python3 scripts/intake_outcome_tracker.py --summary

Only aggregate counts and categories are tracked. No raw user text is stored.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
QUEUE_FILE = REPO_ROOT / "data" / "contribution_queue.jsonl"
OUTCOME_FILE = REPO_ROOT / "data" / "intake_outcomes.json"


def load_queue(path: Path) -> list[dict]:
    """Load intake records from JSONL file."""
    records = []
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def compute_outcomes(records: list[dict]) -> dict:
    """Compute aggregate outcomes. No private text is stored."""
    total = len(records)
    by_type = Counter(r.get("type", "unknown") for r in records)
    by_status = Counter(r.get("status", "unknown") for r in records)
    by_source = Counter(r.get("source", "unknown") for r in records)

    accepted = by_status.get("accepted", 0)
    rejected = by_status.get("rejected", 0)
    converted = by_status.get("converted", 0)
    pending = by_status.get("pending", 0)

    reviewed = accepted + rejected + converted
    conversion_rate = round(converted / reviewed, 3) if reviewed > 0 else 0.0

    return {
        "total_submitted": total,
        "total_reviewed": reviewed,
        "total_pending": pending,
        "by_type": dict(by_type.most_common()),
        "by_status": dict(by_status.most_common()),
        "by_source": dict(by_source.most_common()),
        "conversion_rate": conversion_rate,
    }


def main():
    parser = argparse.ArgumentParser(description="Privacy-preserving intake outcome tracker")
    parser.add_argument("--input", type=Path, default=QUEUE_FILE)
    parser.add_argument("--output", type=Path, default=OUTCOME_FILE)
    parser.add_argument("--summary", action="store_true", help="Print summary only, don't write")
    args = parser.parse_args()

    records = load_queue(args.input)
    outcomes = compute_outcomes(records)

    if args.summary:
        print(json.dumps(outcomes, indent=2, ensure_ascii=False))
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(outcomes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote outcomes to {args.output}")


if __name__ == "__main__":
    main()
