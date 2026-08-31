#!/usr/bin/env python3
"""Verify regression queries against search results.

Run before each release to ensure core failure lessons are retrievable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load_queries(queries_file: Path) -> dict:
    """Load regression queries from JSON file."""
    with open(queries_file, encoding="utf-8") as f:
        return json.load(f)


def run_search(query: str, lessons_dir: Path) -> list[str]:
    """Run a simple BM25-like search (keyword matching)."""
    query_lower = query.lower()
    results = []

    for lesson_file in lessons_dir.rglob("*.md"):
        try:
            content = lesson_file.read_text(encoding="utf-8").lower()
            # Simple keyword matching
            if all(word in content for word in query_lower.split()):
                results.append(str(lesson_file))
        except Exception:
            continue

    return results


def verify_query(query: dict, lessons_dir: Path) -> dict:
    """Verify a single query."""
    query_text = query["query"]
    expected = query.get("expected_lessons", [])
    min_results = query.get("min_results", 0)

    # Run search
    results = run_search(query_text, lessons_dir)

    # Check if expected lessons are found
    found_expected = []
    missing_expected = []
    for exp in expected:
        # Normalize path - extract just the filename
        exp_filename = Path(exp).name
        # Check if filename appears in any result path
        if any(exp_filename in r for r in results):
            found_expected.append(exp)
        else:
            missing_expected.append(exp)

    # Determine status
    status = "PASS"
    if missing_expected:
        status = "FAIL"
    elif len(results) < min_results:
        status = "WARN"

    return {
        "query": query_text,
        "id": query.get("id", "unknown"),
        "category": query.get("category", "unknown"),
        "status": status,
        "results_count": len(results),
        "expected_count": len(expected),
        "found_expected": found_expected,
        "missing_expected": missing_expected,
        "min_results": min_results
    }


def main() -> int:
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Verify regression queries")
    parser.add_argument("--queries", default="data/regression_queries.json",
                        help="Path to regression queries JSON")
    parser.add_argument("--lessons-dir", default="lessons", help="Lessons directory")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--fail-on-warn", action="store_true", help="Fail on warnings too")
    args = parser.parse_args()

    queries_file = Path(args.queries)
    lessons_dir = Path(args.lessons_dir)

    if not queries_file.exists():
        print(f"Error: {queries_file} not found", file=sys.stderr)
        return 1

    if not lessons_dir.exists():
        print(f"Error: {lessons_dir} not found", file=sys.stderr)
        return 1

    # Load queries
    data = load_queries(queries_file)
    queries = data.get("queries", [])

    if not queries:
        print("No queries found", file=sys.stderr)
        return 1

    # Run verification
    results = []
    for query in queries:
        result = verify_query(query, lessons_dir)
        results.append(result)

    # Output
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("## Regression Query Verification\n")
        print(f"**Queries:** {len(results)}\n")

        # Count by status
        passed = sum(1 for r in results if r["status"] == "PASS")
        warned = sum(1 for r in results if r["status"] == "WARN")
        failed = sum(1 for r in results if r["status"] == "FAIL")
        print(f"**Results:** {passed} passed, {warned} warnings, {failed} failed\n")

        for result in results:
            status = result["status"]
            icon = {"PASS": "[OK]", "WARN": "[WARN]", "FAIL": "[FAIL]"}.get(status, "[???]")
            print(f"{icon} **{result['query']}** ({result['category']})")
            print(f"   Results: {result['results_count']}, Expected: {result['expected_count']}")
            if result["missing_expected"]:
                print(f"   Missing: {', '.join(result['missing_expected'])}")
            print()

    # Determine exit code
    has_failures = any(r["status"] == "FAIL" for r in results)
    has_warnings = any(r["status"] == "WARN" for r in results)

    if has_failures:
        return 1
    if args.fail_on_warn and has_warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
