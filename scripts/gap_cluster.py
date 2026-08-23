#!/usr/bin/env python3
"""Cluster similar zero-result search queries for demand analysis.

Reads data/search_gaps.jsonl, groups similar queries, outputs ranked clusters.

Usage:
    python3 scripts/gap_cluster.py
    python3 scripts/gap_cluster.py --top 10 --threshold 0.6 --json
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
GAPS_FILE = REPO_ROOT / "data" / "search_gaps.jsonl"
CLUSTERS_FILE = REPO_ROOT / "data" / "gap_clusters.json"


def normalize_query(query: str) -> str:
    """Normalize query: lowercase, collapse whitespace, strip punctuation."""
    q = query.lower().strip()
    q = re.sub(r"[^\w\s]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q


def ngram_similarity(a: str, b: str, n: int = 2) -> float:
    """Simple n-gram Jaccard similarity between two strings."""
    if not a or not b:
        return 0.0

    def ngrams(s: str) -> set:
        tokens = s.split()
        return {" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)} if len(tokens) >= n else {s}

    sa, sb = ngrams(a), ngrams(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def cluster_queries(
    queries: list[str],
    threshold: float = 0.5,
) -> list[dict]:
    """Cluster similar queries using greedy n-gram matching.

    Returns list of clusters sorted by size (descending).
    Each cluster: {"label": representative_query, "count": N, "queries": [...]}
    """
    normalized = [normalize_query(q) for q in queries if q.strip()]
    if not normalized:
        return []

    # Count exact normalized duplicates first
    freq = Counter(normalized)

    # Greedy clustering: merge similar entries
    clusters: list[dict] = []
    used: set[str] = set()

    for query, count in freq.most_common():
        if query in used:
            continue

        cluster_queries_list = [query]
        cluster_count = count

        for other_query, other_count in freq.items():
            if other_query in used or other_query == query:
                continue
            if ngram_similarity(query, other_query) >= threshold:
                cluster_queries_list.append(other_query)
                cluster_count += other_count
                used.add(other_query)

        used.add(query)
        clusters.append({
            "label": query,
            "count": cluster_count,
            "queries": cluster_queries_list[:10],  # cap sample size
        })

    clusters.sort(key=lambda c: c["count"], reverse=True)
    return clusters


def load_queries() -> list[str]:
    """Load queries from gaps file."""
    if not GAPS_FILE.exists():
        return []
    queries = []
    for line in GAPS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            q = entry.get("query", "").strip()
            if q:
                queries.append(q)
        except json.JSONDecodeError:
            continue
    return queries


def main():
    parser = argparse.ArgumentParser(description="Cluster zero-result search queries")
    parser.add_argument("--top", type=int, default=20, help="Show top N clusters")
    parser.add_argument("--threshold", type=float, default=0.5, help="Similarity threshold (0-1)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--save", action="store_true", help="Save clusters to gap_clusters.json")
    args = parser.parse_args()

    queries = load_queries()
    if not queries:
        print("No gap queries found. Run searches first to populate data/search_gaps.jsonl")
        return

    clusters = cluster_queries(queries, threshold=args.threshold)
    top = clusters[: args.top]

    if args.json:
        output = {
            "total_queries": len(queries),
            "total_clusters": len(clusters),
            "threshold": args.threshold,
            "top_clusters": top,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"Total queries: {len(queries)}")
        print(f"Clusters: {len(clusters)} (threshold={args.threshold})")
        print(f"\nTop {len(top)} gaps:")
        for i, c in enumerate(top, 1):
            samples = ", ".join(c["queries"][:3])
            print(f"  {i:2d}. [{c['count']:3d}x] {samples}")

    if args.save:
        output = {
            "total_queries": len(queries),
            "total_clusters": len(clusters),
            "threshold": args.threshold,
            "clusters": clusters,
        }
        CLUSTERS_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nSaved to {CLUSTERS_FILE}")


if __name__ == "__main__":
    main()
