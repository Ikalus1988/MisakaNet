#!/usr/bin/env python3
"""Faithfulness evaluator: detect lesson usage via RAGAS-style scoring (Issue #1162).

Captures (query, response, result_ids) tuples and evaluates whether
the agent's response was actually informed by the retrieved lessons.

Usage:
    # Evaluate a single interaction
    python scripts/faithfulness_eval.py --query "..." --response "..." --result-ids "id1,id2"

    # Batch evaluate from log file
    python scripts/faithfulness_eval.py --log usage_log.jsonl

    # Show stats
    python scripts/faithfulness_eval.py --stats
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
USAGE_LOG = REPO_ROOT / "data" / "usage_log.jsonl"


def extract_claims(text: str) -> list[str]:
    """Extract factual claims from agent response.

    Simple heuristic: split by sentences, filter short ones.
    A production version would use an LLM for claim decomposition.
    """
    # Split by sentence boundaries
    sentences = re.split(r'[.!?]+', text)
    claims = []
    for s in sentences:
        s = s.strip()
        # Filter short fragments and common filler
        if len(s) > 20 and not s.lower().startswith(('i think', 'maybe', 'perhaps')):
            claims.append(s)
    return claims


def check_claim_support(claim: str, lesson_contents: list[str]) -> bool:
    """Check if a claim can be inferred from retrieved lessons.

    Simple word overlap heuristic. Production version would use LLM judge.
    """
    claim_words = set(claim.lower().split())
    if len(claim_words) < 3:
        return False

    for content in lesson_contents:
        content_words = set(content.lower().split())
        overlap = len(claim_words & content_words)
        if overlap / len(claim_words) >= 0.3:  # 30% word overlap threshold
            return True
    return False


def evaluate_faithfulness(
    query: str,
    response: str,
    lesson_contents: list[str],
) -> dict:
    """Evaluate faithfulness of response given retrieved lessons.

    Returns dict with:
        - claims: list of extracted claims
        - supported: list of booleans (one per claim)
        - score: fraction of supported claims (0-1)
        - was_used: bool (score >= 0.5)
    """
    claims = extract_claims(response)
    if not claims:
        return {"claims": [], "supported": [], "score": 0.0, "was_used": False}

    supported = [check_claim_support(c, lesson_contents) for c in claims]
    score = sum(supported) / len(supported) if supported else 0.0

    return {
        "claims": claims,
        "supported": supported,
        "score": round(score, 3),
        "was_used": score >= 0.5,
    }


def log_usage(query: str, response: str, result_ids: list[str], was_used: bool):
    """Log interaction for batch analysis."""
    entry = {
        "query": query,
        "response_preview": response[:200],
        "result_ids": result_ids,
        "was_used": was_used,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(USAGE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_usage_log() -> list[dict]:
    """Load usage log entries."""
    if not USAGE_LOG.exists():
        return []
    entries = []
    with open(USAGE_LOG, encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
    return entries


def get_usage_stats() -> dict:
    """Compute usage statistics."""
    entries = load_usage_log()
    if not entries:
        return {"total": 0, "used": 0, "unused": 0, "usage_rate": 0.0}

    used = sum(1 for e in entries if e.get("was_used"))
    return {
        "total": len(entries),
        "used": used,
        "unused": len(entries) - used,
        "usage_rate": round(used / len(entries), 3) if entries else 0.0,
    }


def main():
    parser = argparse.ArgumentParser(description="Faithfulness evaluator")
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--response", help="Agent response to evaluate")
    parser.add_argument("--result-ids", help="Comma-separated lesson IDs used")
    parser.add_argument("--contents", help="JSON file with lesson contents")
    parser.add_argument("--log", help="Batch evaluate from JSONL log file")
    parser.add_argument("--stats", action="store_true", help="Show usage stats")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if args.stats:
        stats = get_usage_stats()
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print(f"\n  Usage Statistics")
            print(f"  {'Total:':<15} {stats['total']}")
            print(f"  {'Used:':<15} {stats['used']}")
            print(f"  {'Unused:':<15} {stats['unused']}")
            print(f"  {'Usage Rate:':<15} {stats['usage_rate']:.1%}")
        return

    if args.query and args.response:
        # Load lesson contents if provided
        contents = []
        if args.contents:
            with open(args.contents) as f:
                contents = json.load(f)
        elif args.result_ids:
            # Try to load from lessons directory
            for lid in args.result_ids.split(","):
                lid = lid.strip()
                lesson_path = REPO_ROOT / "lessons" / f"{lid}.md"
                if lesson_path.exists():
                    contents.append(lesson_path.read_text())

        result = evaluate_faithfulness(args.query, args.response, contents)

        result_ids = args.result_ids.split(",") if args.result_ids else []
        log_usage(args.query, args.response, result_ids, result["was_used"])

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\n  Faithfulness Evaluation")
            print(f"  Query: {args.query[:60]}")
            print(f"  Claims: {len(result['claims'])}")
            print(f"  Supported: {sum(result['supported'])}/{len(result['claims'])}")
            print(f"  Score: {result['score']:.1%}")
            print(f"  Was Used: {'✅' if result['was_used'] else '❌'}")

    elif args.log:
        # Batch evaluate
        with open(args.log) as f:
            entries = [json.loads(line) for line in f if line.strip()]

        results = []
        for entry in entries:
            result = evaluate_faithfulness(
                entry["query"],
                entry.get("response", ""),
                entry.get("contents", []),
            )
            results.append({**entry, **result})

        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            used = sum(1 for r in results if r["was_used"])
            print(f"\n  Batch Evaluation: {len(results)} interactions")
            print(f"  Used: {used} ({used/len(results):.1%})")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
