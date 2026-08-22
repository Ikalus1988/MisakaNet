#!/usr/bin/env python3
"""Cluster zero-result search queries to identify content gaps.

Reads search_telemetry.jsonl and groups similar queries together.
Outputs top clusters ranked by frequency.

Usage:
    python scripts/gap_cluster.py --top 20
    python scripts/gap_cluster.py --input ~/.misakanet/search_telemetry.jsonl --output data/gap_clusters.json
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path


def normalize_query(query: str) -> str:
    """Normalize query for clustering."""
    q = query.lower().strip()
    q = re.sub(r'[^\w\s]', ' ', q)  # Remove punctuation
    q = re.sub(r'\s+', ' ', q)       # Collapse whitespace
    return q.strip()


def ngram_similarity(a: str, b: str, n: int = 2) -> float:
    """Simple n-gram similarity between two strings."""
    if not a or not b:
        return 0.0

    def ngrams(s, n):
        return set(s[i:i+n] for i in range(len(s) - n + 1))

    a_ng = ngrams(a, n)
    b_ng = ngrams(b, n)
    if not a_ng or not b_ng:
        return 0.0
    return len(a_ng & b_ng) / len(a_ng | b_ng)


def cluster_queries(queries: list[str], threshold: float = 0.3) -> list[dict]:
    """Cluster similar queries together."""
    normalized = [(q, normalize_query(q)) for q in queries]
    clusters = []
    used = set()

    for i, (orig_i, norm_i) in enumerate(normalized):
        if i in used:
            continue
        cluster = [orig_i]
        used.add(i)

        for j, (orig_j, norm_j) in enumerate(normalized):
            if j in used:
                continue
            if ngram_similarity(norm_i, norm_j) >= threshold:
                cluster.append(orig_j)
                used.add(j)

        clusters.append({
            "queries": cluster,
            "count": len(cluster),
            "representative": Counter(cluster).most_common(1)[0][0],
        })

    return sorted(clusters, key=lambda c: c["count"], reverse=True)


def main():
    parser = argparse.ArgumentParser(description="Cluster zero-result search queries")
    parser.add_argument("--input", type=str, default="~/.misakanet/search_telemetry.jsonl",
                        help="Path to search_telemetry.jsonl")
    parser.add_argument("--output", type=str, default="data/gap_clusters.json",
                        help="Output path for clusters")
    parser.add_argument("--top", type=int, default=20,
                        help="Number of top clusters to show")
    parser.add_argument("--threshold", type=float, default=0.3,
                        help="Similarity threshold for clustering (0-1)")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser()
    if not input_path.exists():
        print(f"❌ Input file not found: {input_path}")
        print("   Run some searches first to generate telemetry data.")
        return 1

    # Read queries
    queries = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if entry.get("result") == "zero":
                    queries.append(entry["query"])
            except json.JSONDecodeError:
                continue

    if not queries:
        print("✅ No zero-result queries found.")
        return 0

    print(f"📊 Found {len(queries)} zero-result queries")
    print()

    # Cluster
    clusters = cluster_queries(queries, threshold=args.threshold)

    # Show top clusters
    print(f"Top {min(args.top, len(clusters))} content gaps:")
    print("-" * 60)
    for i, cluster in enumerate(clusters[:args.top], 1):
        print(f"{i:2d}. [{cluster['count']:3d} queries] {cluster['representative']}")
        if cluster['count'] > 1:
            # Show a few example queries
            examples = list(set(cluster['queries']))[:3]
            for ex in examples:
                if ex != cluster['representative']:
                    print(f"        → {ex}")

    # Save to file
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_queries": len(queries),
            "total_clusters": len(clusters),
            "threshold": args.threshold,
            "clusters": clusters[:args.top],
        }, f, indent=2, ensure_ascii=False)

    print()
    print(f"💾 Saved to {output_path}")
    return 0


if __name__ == "__main__":
    exit(main())
