#!/usr/bin/env python3
"""Intake classifier — reads intake records and routes to demand board.

Reads from data/intake-export.jsonl or stdin, classifies each entry,
and records demand signals for items without matching lessons.

Usage:
    python3 scripts/intake_classify.py --input data/intake-export.jsonl
    python3 scripts/intake_classify.py --json '{"type":"bug","message":"search crashes"}'
    python3 scripts/intake_classify.py --stdin < intake.jsonl

Classification:
    lesson_candidate → "lesson-feedback" family
    bug              → "bug-report" family
    diagnostic/friction/node_join → "unclassified" family
    noise            → skipped
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.demand_board import record_signal

# ── Classifier ──

LESSON_SIGNALS = [
    "fixed", "solved", "solution", "workaround", "here's how",
    "i figured out", "the fix was", "resolved", "tip", "trick",
]

BUG_SIGNALS = [
    "bug", "regression", "broken", "crash", "500", "internal error",
    "misakanet", "search_knowledge", "worker", "endpoint",
]

RESCUE_SIGNALS = [
    "help", "stuck", "error", "fail", "timeout", "not working",
    "can't", "cannot", "how do i", "urgent", "blocked",
]


def classify(entry: dict) -> str:
    """Classify intake entry. Returns category."""
    # Explicit type takes priority
    explicit = str(entry.get("type", "") or "").lower()
    if explicit == "lesson_candidate":
        return "lesson"
    if explicit == "bug":
        return "bug"
    if explicit in ("diagnostic", "friction"):
        return "rescue"
    if explicit == "noise":
        return "noise"

    # Positive feedback = noise (check before keyword matching)
    if entry.get("feedback") in ("helpful", "y", "yes"):
        return "noise"

    # Keyword-based classification
    text = " ".join([
        str(entry.get("message", "")),
        str(entry.get("query", "")),
        str(entry.get("feedback", "")),
    ]).lower()

    if not text.strip():
        return "noise"

    bug_score = sum(1 for kw in BUG_SIGNALS if kw in text)
    rescue_score = sum(1 for kw in RESCUE_SIGNALS if kw in text)
    lesson_score = sum(1 for kw in LESSON_SIGNALS if kw in text)

    if lesson_score > bug_score and lesson_score > rescue_score:
        return "lesson"
    if bug_score > rescue_score:
        return "bug"
    if rescue_score > 0:
        return "rescue"

    return "noise"


def process_entry(entry: dict, verbose: bool = True) -> tuple[str, str]:
    """Classify and route a single intake entry. Returns (category, family)."""
    category = classify(entry)

    if category == "noise":
        if verbose:
            print(f"  [noise] skipped")
        return "noise", "skipped"

    # Map category to demand board family
    family_map = {
        "lesson": "lesson-feedback",
        "bug": "bug-report",
        "rescue": "unclassified",
    }
    family = family_map.get(category, "unclassified")

    # Record demand signal
    reason = str(entry.get("message", entry.get("query", "")))[:64]
    source = entry.get("source", "unknown")
    item = record_signal(family, reason=reason, source=source, category=category)

    if verbose:
        icon = {"lesson": "\U0001f4d6", "bug": "\U0001f41b", "rescue": "\U0001f6a8"}.get(category, "?")
        print(f"  {icon} [{category}] family={family} id={item['id']} count={item['count']}")

    return category, family


def main():
    parser = argparse.ArgumentParser(description="Intake classifier — route to demand board")
    parser.add_argument("--input", "-i", help="JSONL file of intake records")
    parser.add_argument("--json", "-j", help="Single JSON entry")
    parser.add_argument("--stdin", action="store_true", help="Read from stdin")
    parser.add_argument("--quiet", "-q", action="store_true")
    args = parser.parse_args()

    entries = []

    if args.json:
        try:
            entries = [json.loads(args.json)]
        except json.JSONDecodeError as e:
            print(f"Error: invalid JSON: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.input:
        path = Path(args.input)
        if not path.exists():
            print(f"Error: {path} not found", file=sys.stderr)
            sys.exit(1)
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    elif args.stdin or not sys.stdin.isatty():
        for line in sys.stdin:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    else:
        parser.print_help()
        sys.exit(1)

    if not entries:
        print("No entries to classify.")
        return

    verbose = not args.quiet
    if verbose:
        print(f"\n  Classifying {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}...\n")

    stats = {"lesson": 0, "bug": 0, "rescue": 0, "noise": 0}
    for entry in entries:
        cat, _ = process_entry(entry, verbose=verbose)
        stats[cat] = stats.get(cat, 0) + 1

    if verbose:
        print(f"\n  Done: {stats['lesson']} lessons, {stats['bug']} bugs, "
              f"{stats['rescue']} rescues, {stats['noise']} noise\n")


if __name__ == "__main__":
    main()
