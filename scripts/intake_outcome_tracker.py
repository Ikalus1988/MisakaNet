#!/usr/bin/env python3
"""Privacy-preserving intake outcome tracker.

Tracks anonymous intake funnel metrics without storing private text.

Usage:
    python3 scripts/intake_outcome_tracker.py [--input data/contribution_queue.jsonl]
    python3 scripts/intake_outcome_tracker.py --summary

Only aggregate counts and categories are tracked. No raw user text is stored.

⚠️ What `conversion_rate` means (2026-09-17). `data/contribution_queue.jsonl` records submissions
and **nothing ever updates their status** — `by_status` is 100% `pending` — so the rate is 0.0 no
matter how many intakes became lessons. That is *not observed*, not *measured*. The real evidence
is in the corpus, where every converted lesson carries `source: mcp-intake-<n>`. Both numbers are
reported now, and `conversion_rate_is_observable` says which one you are reading.
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
QUEUE_FILE = REPO_ROOT / "data" / "contribution_queue.jsonl"
OUTCOME_FILE = REPO_ROOT / "data" / "intake_outcomes.json"
LESSONS_DIR = REPO_ROOT / "lessons"
# `source: mcp-intake-1069` (issue number, 4 digits) or `mcp-intake-<hex>` (pre-issue intake id,
# e.g. 1dcd078f12) — the marker every converted-intake lesson carries. `[0-9a-f_]{4,}` covers both;
# a `{6,}` bound would have silently dropped every four-digit issue number and undercounted.
_INTAKE_SOURCE = re.compile(r"mcp-intake-([0-9a-f_]{4,})")


def corpus_conversions(root: Path = LESSONS_DIR) -> dict:
    """Intakes that became lessons, counted from the corpus — the part that is checkable.

    Deliberately derived from the lessons themselves (a `source: mcp-intake-…` marker) rather than
    from anything a human has to remember to update, which is exactly why it disagrees with the
    queue-side rate.
    """
    ids: set[str] = set()
    lessons = 0
    for path in sorted(root.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        found = _INTAKE_SOURCE.findall(text)
        if found:
            lessons += 1
            ids.update(found)
    return {"lessons": lessons, "intakes": len(ids), "intake_ids": sorted(ids)}


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

    corpus = corpus_conversions()
    return {
        "total_submitted": total,
        "total_reviewed": reviewed,
        "total_pending": pending,
        "by_type": dict(by_type.most_common()),
        "by_status": dict(by_status.most_common()),
        "by_source": dict(by_source.most_common()),
        "conversion_rate": conversion_rate,
        # Reading `conversion_rate` without these two lines is how "0.0" got quoted as a fact.
        "conversion_rate_is_observable": reviewed > 0,
        "conversion_rate_note": (
            "measured from the queue" if reviewed > 0 else
            "NOT OBSERVABLE: the queue records submissions only and nothing marks intakes "
            "reviewed, so 0.0 means 'we never wrote the outcome', not 'none converted'"
        ),
        "converted_lessons_in_corpus": corpus["lessons"],
        "converted_intakes_in_corpus": corpus["intakes"],
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
