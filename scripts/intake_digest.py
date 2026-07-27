#!/usr/bin/env python3
"""
Intake Digest — Pull and classify intakes from KV or local test data.

Reads intakes from a JSON file (typically exported from KV) and classifies
them using the same triage engine as email feedback. Outputs a summary
report grouped by classification.

Usage:
    python scripts/intake_digest.py [intakes.json]

If no file is provided, looks for intakes.json in the current directory.
"""

import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# Use existing triage engine
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from triage_feedback import classify_feedback
except ImportError:
    def classify_feedback(text):
        """Fallback lightweight classifier if triage_feedback is unavailable."""
        text_lower = text.lower()
        if len(text.split()) < 5:
            return "noise", 0.95, {"reason": "too_short"}
        fix_words = ["fixed by", "solution:", "fix:", "resolved", "workaround"]
        problem_words = ["error:", "failed", "cannot", "unable", "bug:", "issue:"]
        has_fix = any(w in text_lower for w in fix_words)
        has_problem = any(w in text_lower for w in problem_words)
        if has_fix and has_problem:
            return "lesson_candidate", 0.88, {}
        if has_problem:
            return "rescue_card", 0.85, {}
        return "noise", 0.70, {"reason": "no_signal"}


def load_intakes(path: str) -> list:
    """Load intake records from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # May be a KV export map {key: value}
        return [v for v in data.values() if isinstance(v, dict) and "type" in v]
    return []


def digest_intakes(intakes: list) -> dict:
    """Classify intakes and produce a summary report."""
    results = {
        "total": len(intakes),
        "classified": Counter(),
        "by_source": Counter(),
        "by_type": Counter(),
        "by_consent": Counter(),
        "items": [],
    }

    for item in intakes:
        msg = item.get("message", "")
        intake_type = item.get("type", "unknown")
        source = item.get("source", "unknown")
        consent = item.get("consent", "private_only")

        category, confidence, meta = classify_feedback(msg)

        results["classified"][category] += 1
        results["by_source"][source] += 1
        results["by_type"][intake_type] += 1
        results["by_consent"][consent] += 1

        results["items"].append({
            "intake_id": item.get("intakeId", item.get("intake_id", "")),
            "type": intake_type,
            "source": source,
            "consent": consent,
            "category": category,
            "confidence": round(confidence, 2),
            "message_preview": msg[:100],
            "ts": item.get("ts", ""),
        })

    return results


def print_report(results: dict):
    """Print a human-readable digest report."""
    print("=" * 60)
    print("  MisakaNet Intake Digest")
    print(f"  Generated: {datetime.now().isoformat()}")
    print("=" * 60)
    print(f"\nTotal intakes: {results['total']}")

    if results["total"] == 0:
        print("\nNo intakes to classify.")
        return

    print("\n📊 Classification:")
    for cat, count in results["classified"].most_common():
        pct = count / results["total"] * 100
        print(f"  {cat:<25} {count:>4}  ({pct:.0f}%)")

    print("\n📡 By source:")
    for src, count in results["by_source"].most_common():
        print(f"  {src:<25} {count:>4}")

    print("\n🏷️  By intake type:")
    for typ, count in results["by_type"].most_common():
        print(f"  {typ:<25} {count:>4}")

    print("\n🔒 By consent:")
    for con, count in results["by_consent"].most_common():
        print(f"  {con:<25} {count:>4}")

    print("\n" + "-" * 60)
    print("📋 Detailed items:")
    for item in results["items"]:
        print(f"\n  [{item['category']}] {item['type']} from {item['source']}")
        print(f"  ID: {item['intake_id']}")
        print(f"  Consent: {item['consent']} | Confidence: {item['confidence']}")
        print(f"  Preview: {item['message_preview']}")

    print("\n" + "=" * 60)


def main():
    # Determine input file
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    else:
        input_path = "intakes.json"

    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        print("Usage: python scripts/intake_digest.py [intakes.json]")
        sys.exit(1)

    intakes = load_intakes(input_path)
    if not intakes:
        print(f"No valid intake records found in {input_path}")
        sys.exit(0)

    results = digest_intakes(intakes)
    print_report(results)

    # Write JSON output for CI/automation
    output_path = "intake_digest_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nFull report written to: {output_path}")


if __name__ == "__main__":
    main()
