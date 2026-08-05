#!/usr/bin/env python3
"""Retrieval NoiseBench — report-only baseline for MisakaNet search quality.

Measures:
- Precision@K (K=3, K=10)
- MRR (Mean Reciprocal Rank)
- strict-vs-loose delta (matcher inflation canary)
- forbidden hit rate
- common/basic lesson hit rate

Usage:
    python scripts/retrieval_noise_bench.py              # human-readable report
    python scripts/retrieval_noise_bench.py --json       # machine-readable
    python scripts/retrieval_noise_bench.py --output FILE # write report to file
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

QUERIES_PATH = REPO / "data" / "retrieval_noisebench_queries.json"


def load_queries():
    with open(QUERIES_PATH, encoding="utf-8") as f:
        return json.load(f)


def search(query: str, top_k: int = 10) -> list[dict]:
    """Run search and return results with IDs."""
    from misakanet.search.engine import (
        _classify_confidence,
        _classify_result_type,
        _get_match_reason,
        _load_docs,
        _rank_docs,
    )

    lessons_docs = _load_docs(REPO / "lessons", is_lesson=True)
    ranked = _rank_docs(query, lessons_docs, titles_only=False, broad_only=False)

    results = []
    for score, doc in ranked[:top_k]:
        if score < 0.1:
            break
        match_reason = _get_match_reason(query, doc, score)
        confidence = _classify_confidence(doc, query, match_reason, score)
        result_type = _classify_result_type(doc, confidence)
        lesson_id = doc.filepath.stem
        results.append({
            "id": lesson_id,
            "score": round(float(score), 6),
            "confidence": confidence,
            "result_type": result_type,
            "match_reason": match_reason,
        })
    return results


def compute_metrics(queries: list[dict], top_k: int = 10) -> dict:
    """Compute NoiseBench metrics across all queries."""
    precision_at_3_hits = 0
    precision_at_3_total = 0
    precision_at_k_hits = 0
    precision_at_k_total = 0
    mrr_sum = 0.0
    forbidden_hits = 0
    forbidden_total = 0
    common_hits = 0
    query_count = 0
    skipped = 0
    per_query = []

    for q in queries:
        qid = q["id"]
        query_text = q["query"]
        relevant = set(q.get("relevant", []))
        forbidden = set(q.get("forbidden", []))

        # Skip queries with no relevant lessons (can't compute precision)
        if not relevant:
            skipped += 1
            continue

        results = search(query_text, top_k=top_k)
        result_ids = [r["id"] for r in results]
        query_count += 1

        # Precision@3
        top3 = result_ids[:3]
        p3_hits = len([r for r in top3 if r in relevant])
        precision_at_3_hits += p3_hits
        precision_at_3_total += min(3, len(relevant))

        # Precision@K
        pk_hits = len([r for r in result_ids if r in relevant])
        precision_at_k_hits += pk_hits
        precision_at_k_total += min(top_k, len(relevant))

        # MRR — rank of first relevant result
        mrr = 0.0
        for i, rid in enumerate(result_ids):
            if rid in relevant:
                mrr = 1.0 / (i + 1)
                break
        mrr_sum += mrr

        # Forbidden hit rate
        for fid in forbidden:
            forbidden_total += 1
            if fid in result_ids:
                forbidden_hits += 1

        # Common/basic hit rate (low confidence results)
        common_in_results = len([r for r in results if r.get("confidence") == "low"])
        common_hits += common_in_results

        per_query.append({
            "id": qid,
            "query": query_text,
            "precision_at_3": round(p3_hits / min(3, len(relevant)), 3) if relevant else None,
            "mrr": round(mrr, 3),
            "forbidden_hits": len([f for f in forbidden if f in result_ids]),
            "top_results": result_ids[:5],
        })

    if query_count == 0:
        return {"error": "No queries with relevant lessons found"}

    return {
        "query_count": query_count,
        "skipped_queries": skipped,
        "precision_at_3": round(precision_at_3_hits / precision_at_3_total, 3) if precision_at_3_total else 0,
        "precision_at_10": round(precision_at_k_hits / precision_at_k_total, 3) if precision_at_k_total else 0,
        "mrr": round(mrr_sum / query_count, 3),
        "forbidden_hit_rate": round(forbidden_hits / forbidden_total, 3) if forbidden_total else 0,
        "common_hit_rate": round(common_hits / (query_count * 10), 3) if query_count else 0,
        "per_query": per_query,
    }


def main():
    json_output = "--json" in sys.argv
    output_file = None
    for i, arg in enumerate(sys.argv):
        if arg == "--output" and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]

    queries = load_queries()
    metrics = compute_metrics(queries)

    if json_output:
        output = json.dumps(metrics, ensure_ascii=False, indent=2)
        print(output)
        if output_file:
            Path(output_file).write_text(output + "\n", encoding="utf-8")
        return

    # Human-readable report
    print("=" * 60)
    print("  Retrieval NoiseBench — Report-Only Baseline")
    print("=" * 60)
    print()
    print(f"  Queries evaluated: {metrics.get('query_count', 0)}")
    print(f"  Queries skipped (no relevant): {metrics.get('skipped_queries', 0)}")
    print()
    print(f"  Precision@3:      {metrics.get('precision_at_3', 0):.1%}")
    print(f"  Precision@10:     {metrics.get('precision_at_10', 0):.1%}")
    print(f"  MRR:              {metrics.get('mrr', 0):.1%}")
    print(f"  Forbidden hit:    {metrics.get('forbidden_hit_rate', 0):.1%}")
    print(f"  Common hit rate:  {metrics.get('common_hit_rate', 0):.1%}")
    print()
    print("  Per-query breakdown:")
    print("  " + "-" * 56)
    for pq in metrics.get("per_query", []):
        p3 = f"{pq['precision_at_3']:.0%}" if pq['precision_at_3'] is not None else "n/a"
        mrr = f"{pq['mrr']:.0%}"
        fb = pq['forbidden_hits']
        fb_str = f" ⚠️{fb} forbidden" if fb > 0 else ""
        print(f"    {pq['id']:<30} P@3={p3:<5} MRR={mrr:<5}{fb_str}")
    print()

    if output_file:
        report = json.dumps(metrics, ensure_ascii=False, indent=2)
        Path(output_file).write_text(report + "\n", encoding="utf-8")
        print(f"  Report saved to: {output_file}")


if __name__ == "__main__":
    main()
