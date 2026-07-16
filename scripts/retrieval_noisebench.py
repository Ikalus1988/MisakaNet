#!/usr/bin/env python3
"""Retrieval NoiseBench — Issue #481.

Measures retrieval quality: Precision@K, MRR, forbidden hit rate,
and strict-vs-loose matcher inflation delta.

Usage:
    python3 scripts/retrieval_noisebench.py
    python3 scripts/retrieval_noisebench.py --json
    python3 scripts/retrieval_noisebench.py --queries data/custom_queries.json
"""

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from misakanet.search.engine import LESSONS, _load_docs_cached, _rank_docs_impl


def _precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Precision@K: fraction of top-k results that are relevant."""
    top_k = retrieved[:k]
    hits = sum(1 for r in top_k if r in relevant)
    return hits / k if k > 0 else 0.0


def _mrr(retrieved: list[str], relevant: set[str]) -> float:
    """Mean Reciprocal Rank: 1/rank of first relevant result."""
    for i, r in enumerate(retrieved):
        if r in relevant:
            return 1.0 / (i + 1)
    return 0.0


def _forbidden_hit_rate(retrieved: list[str], forbidden: set[str], k: int) -> float:
    """How often forbidden/near-miss lessons appear in top-k."""
    top_k = retrieved[:k]
    hits = sum(1 for r in top_k if r in forbidden)
    return hits / k if k > 0 else 0.0


def _run_noisebench(queries: list[dict], docs: list, top_k: int = 10) -> dict:
    """Run noisebench queries and compute metrics."""
    results = []
    precisions_at_3 = []
    precisions_at_10 = []
    mrrs = []
    forbidden_rates = []

    for q in queries:
        ranked = _rank_docs_impl(q["query"], docs, titles_only=False, broad_only=False)
        top_results = [d.filename.replace(".md", "") for _, d in ranked[:top_k]]

        relevant = set(q.get("relevant", []))
        forbidden = set(q.get("forbidden", []))

        p3 = _precision_at_k(top_results, relevant, 3)
        p10 = _precision_at_k(top_results, relevant, top_k)
        mrr = _mrr(top_results, relevant)
        fhr = _forbidden_hit_rate(top_results, forbidden, top_k)

        precisions_at_3.append(p3)
        precisions_at_10.append(p10)
        mrrs.append(mrr)
        forbidden_rates.append(fhr)

        results.append({
            "id": q["id"],
            "query": q["query"],
            "relevant": list(relevant),
            "forbidden": list(forbidden),
            "top_results": top_results[:5],
            "precision_at_3": round(p3, 3),
            "precision_at_10": round(p10, 3),
            "mrr": round(mrr, 3),
            "forbidden_hit_rate": round(fhr, 3),
        })

    return {
        "summary": {
            "num_queries": len(queries),
            "mean_precision_at_3": round(sum(precisions_at_3) / len(precisions_at_3), 3) if precisions_at_3 else 0,
            "mean_precision_at_10": round(sum(precisions_at_10) / len(precisions_at_10), 3) if precisions_at_10 else 0,
            "mean_mrr": round(sum(mrrs) / len(mrrs), 3) if mrrs else 0,
            "mean_forbidden_hit_rate": round(sum(forbidden_rates) / len(forbidden_rates), 3) if forbidden_rates else 0,
        },
        "per_query": results,
    }


def _strict_vs_loose(docs: list, queries: list[dict]) -> dict:
    """Compare strict (word-level) vs loose (substring) matching inflation.

    Uses the metadata bonus as a proxy for matcher strictness.
    """
    # This is a simplified version — the real inflation delta comes from
    # changing the matching algorithm, but we can measure the score delta
    # between title_exact and title_partial as a proxy.
    deltas = []
    for q in queries:
        ranked = _rank_docs_impl(q["query"], docs, titles_only=False, broad_only=False)
        if ranked:
            top_score = ranked[0][0]
            # Check if top result is in relevant set
            relevant = set(q.get("relevant", []))
            top_name = ranked[0][1].filename.replace(".md", "")
            is_relevant = top_name in relevant
            deltas.append({
                "id": q["id"],
                "top_score": round(top_score, 3),
                "top_result": top_name,
                "is_relevant": is_relevant,
            })

    relevant_scores = [d["top_score"] for d in deltas if d["is_relevant"]]
    irrelevant_scores = [d["top_score"] for d in deltas if not d["is_relevant"]]

    return {
        "relevant_avg_top_score": round(sum(relevant_scores) / len(relevant_scores), 3) if relevant_scores else 0,
        "irrelevant_avg_top_score": round(sum(irrelevant_scores) / len(irrelevant_scores), 3) if irrelevant_scores else 0,
        "score_gap": round(
            (sum(relevant_scores) / len(relevant_scores) if relevant_scores else 0)
            - (sum(irrelevant_scores) / len(irrelevant_scores) if irrelevant_scores else 0),
            3
        ),
        "details": deltas,
    }


def main():
    json_mode = "--json" in sys.argv
    queries_path = REPO / "data" / "retrieval_noisebench_queries.json"

    for i, arg in enumerate(sys.argv):
        if arg == "--queries" and i + 1 < len(sys.argv):
            queries_path = Path(sys.argv[i + 1])

    if not queries_path.exists():
        print(f"Error: queries file not found: {queries_path}", file=sys.stderr)
        sys.exit(1)

    queries = json.loads(queries_path.read_text())
    docs = _load_docs_cached(LESSONS, is_lesson=True)

    print(f"Loaded {len(docs)} lessons, {len(queries)} queries\n")

    t0 = time.time()
    bench = _run_noisebench(queries, docs)
    bench_time = time.time() - t0

    strict_loose = _strict_vs_loose(docs, queries)

    report = {
        "bench_time_ms": round(bench_time * 1000),
        "benchmark": bench,
        "strict_vs_loose": strict_loose,
    }

    if json_mode:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    # Pretty print
    s = bench["summary"]
    print("=" * 60)
    print("Retrieval NoiseBench — Issue #481")
    print("=" * 60)
    print(f"\n  Precision@3:  {s['mean_precision_at_3']:.3f}")
    print(f"  Precision@10: {s['mean_precision_at_10']:.3f}")
    print(f"  MRR:          {s['mean_mrr']:.3f}")
    print(f"  Forbidden:    {s['mean_forbidden_hit_rate']:.3f}")
    print(f"  Time:         {bench_time*1000:.0f}ms")

    print(f"\n--- Strict vs Loose ---")
    print(f"  Relevant avg top score:   {strict_loose['relevant_avg_top_score']:.3f}")
    print(f"  Irrelevant avg top score: {strict_loose['irrelevant_avg_top_score']:.3f}")
    print(f"  Score gap:                {strict_loose['score_gap']:.3f}")

    print(f"\n--- Per-Query Results ---")
    print(f"  {'ID':<25} {'P@3':>5} {'P@10':>5} {'MRR':>5} {'FHR':>5} Top Result")
    print(f"  {'-'*25} {'-'*5} {'-'*5} {'-'*5} {'-'*5} {'-'*30}")
    for r in bench["per_query"]:
        top = r["top_results"][0] if r["top_results"] else "—"
        marker = "✅" if r["mrr"] > 0 else "❌"
        print(f"  {r['id']:<25} {r['precision_at_3']:>5.2f} {r['precision_at_10']:>5.2f} "
              f"{r['mrr']:>5.2f} {r['forbidden_hit_rate']:>5.2f} {top[:30]} {marker}")

    # Save report
    report_path = REPO / "data" / "retrieval_noisebench_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
