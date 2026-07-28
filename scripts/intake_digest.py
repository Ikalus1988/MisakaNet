#!/usr/bin/env python3
"""Pull and classify intake submissions from KV export or local JSONL.

Usage:
    python3 scripts/intake_digest.py [--input data/intake-export.jsonl] [--top 20]

If no input file, prints usage. Designed to run against a KV export
or the local data/search-feedback.jsonl for testing.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def load_intakes(path: Path) -> list[dict]:
    """Load intake records from JSONL file."""
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
            except json.JSONDecodeError:
                continue
    return records


def classify(records: list[dict]) -> dict:
    """Classify intakes by type and source."""
    by_type = Counter(r.get("type", "unknown") for r in records)
    by_source = Counter(r.get("source", "unknown") for r in records)
    by_consent = Counter(r.get("consent", "private_only") for r in records)
    return {
        "total": len(records),
        "by_type": dict(by_type.most_common()),
        "by_source": dict(by_source.most_common()),
        "by_consent": dict(by_consent.most_common()),
    }


def main():
    parser = argparse.ArgumentParser(description="Intake digest — pull and classify submissions")
    parser.add_argument("--input", "-i", default="data/intake-export.jsonl",
                        help="Path to JSONL intake export (default: data/intake-export.jsonl)")
    parser.add_argument("--top", type=int, default=20, help="Show top N recent entries")
    args = parser.parse_args()

    path = Path(args.input)
    records = load_intakes(path)

    if not records:
        print("No intake records found.")
        return

    stats = classify(records)
    print(f"\n{'='*50}")
    print(f"  Intake Digest — {stats['total']} records")
    print(f"{'='*50}")
    print(f"\n  By type:")
    for t, c in stats["by_type"].items():
        print(f"    {t:<20} {c}")
    print(f"\n  By source:")
    for s, c in stats["by_source"].items():
        print(f"    {s:<20} {c}")
    print(f"\n  By consent:")
    for cs, c in stats["by_consent"].items():
        print(f"    {cs:<25} {c}")

    print(f"\n  Recent ({min(args.top, len(records))}):")
    print(f"  {'ID':<10} {'Type':<18} {'Source':<10} {'Message'}")
    print(f"  {'-'*10} {'-'*18} {'-'*10} {'-'*40}")
    for r in records[-args.top:]:
        rid = r.get("intakeId", r.get("id", "?"))[:8]
        rtype = r.get("type", "?")[:16]
        rsrc = r.get("source", "?")[:8]
        msg = r.get("message", "")[:50]
        print(f"  {rid:<10} {rtype:<18} {rsrc:<10} {msg}")
    print()


if __name__ == "__main__":
    main()
