#!/usr/bin/env python3
"""BM25 Field Weighting Benchmark — Issue #311.

Compares old vs new metadata weights using regression queries.
Measures Precision@K and Mean Reciprocal Rank (MRR).

Usage:
    python3 scripts/benchmark_bm25_weights.py
    python3 scripts/benchmark_bm25_weights.py --json
"""

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from misakanet.search.engine import (
    LESSONS,
    WEIGHT_DOMAIN_MATCH,
    WEIGHT_HAS_REF,
    WEIGHT_STATUS,
    WEIGHT_TITLE_EXACT,
    WEIGHT_TITLE_PARTIAL,
    _load_docs_cached,
    _rank_docs_impl,
    _tokenize,
)

# ── Weight configurations ──

WEIGHTS_OLD = {
    "domain_match": 0.3,
    "title_exact": 0.5,
    "title_partial": 0.2,
    "status_published": 0.2,
    "has_reference": 0.08,
}

# Proposed: boost title match (strongest signal), reduce domain noise,
# remove status weight (published is the default, adds no info).
WEIGHTS_NEW = {
    "domain_match": 0.25,
    "title_exact": 0.80,
    "title_partial": 0.40,
    "status_published": 0.0,  # removed: default state, no signal
    "has_reference": 0.12,
}

# ── Query fixtures ──

QUERIES = [
    {"query": "DCO", "expected": ["dco-auto-fix-workflow"]},
    {"query": "GitHub token", "expected": ["github-api-pr-issue-management"]},
    {"query": "pip timeout", "expected": ["pip-install-timeout-ssl"]},
    {"query": "database locked", "expected": ["agent-state-database-lock-issues-cleanup-protocol"]},
    {"query": "feishu", "expected": ["feishu-block-api-false-success"]},
    {"query": "FANUC", "expected": ["fanuc-io-marker-m-instruction"]},
    {"query": "PROFINET", "expected": ["fanuc-profinet-32bit-real-value-transfer"]},
    {"query": "secret scan", "expected": ["codeql-alert-dismissal-false-positive"]},
    {"query": "Windows Unicode", "expected": ["python-gbk-encoding-error"]},
    {"query": "WSL permission", "expected": ["wsl-permission-ntfs-fix"]},
    {"query": "SSL certificate", "expected": []},  # open-ended
    {"query": "proxy configuration", "expected": []},
    {"query": "git rebase conflict", "expected": []},
    {"query": "Docker build failed", "expected": []},
    {"query": "API rate limit", "expected": []},
    {"query": "JSON parsing error", "expected": []},
    {"query": "memory leak", "expected": []},
    {"query": "timeout connection", "expected": []},
    {"query": "permission denied", "expected": []},
    {"query": "module not found", "expected": []},
    # Edge cases: domain match vs title relevance
    {"query": "FANUC alarm", "expected": []},  # should rank FANUC domain high
    {"query": "agent lock database", "expected": []},  # multi-keyword
    {"query": "python encoding error", "expected": []},
    {"query": "git push rejected", "expected": []},
    {"query": "docker compose failed", "expected": []},
    {"query": "npm install ERESOLVE", "expected": []},
    {"query": "ssh connection refused", "expected": []},
    {"query": "cron not running", "expected": []},
]


def _apply_weights(weights: dict):
    """Monkey-patch engine weights for benchmarking."""
    import misakanet.search.engine as eng
    eng.WEIGHT_DOMAIN_MATCH = weights["domain_match"]
    eng.WEIGHT_TITLE_EXACT = weights["title_exact"]
    eng.WEIGHT_TITLE_PARTIAL = weights["title_partial"]
    eng.WEIGHT_STATUS = {"published": weights["status_published"], "active": 0.1, "draft": 0.0}
    eng.WEIGHT_HAS_REF = weights["has_reference"]


def _run_benchmark(docs, weights, top_k=5):
    """Run all queries with given weights, return metrics."""
    _apply_weights(weights)

    precisions = []
    mrrs = []
    results_detail = []

    for q in QUERIES:
        ranked = _rank_docs_impl(q["query"], docs, titles_only=False, broad_only=False)
        top_results = ranked[:top_k]
        top_filenames = [d.filename.replace(".md", "") for _, d in top_results]

        expected = set(q["expected"])
        if expected:
            hits = sum(1 for f in top_filenames if f in expected)
            precision = hits / min(top_k, len(expected))
            precisions.append(precision)

            # MRR
            rr = 0.0
            for i, f in enumerate(top_filenames):
                if f in expected:
                    rr = 1.0 / (i + 1)
                    break
            mrrs.append(rr)

        results_detail.append({
            "query": q["query"],
            "expected": q["expected"],
            "top_hits": top_filenames[:3],
            "precision_at_5": hits / min(top_k, len(expected)) if expected else None,
            "rr": rr if expected else None,
        })

    return {
        "mean_precision_at_5": sum(precisions) / len(precisions) if precisions else 0,
        "mean_mrr": sum(mrrs) / len(mrrs) if mrrs else 0,
        "queries_with_expected": len(precisions),
        "details": results_detail,
    }


def main():
    json_mode = "--json" in sys.argv

    docs = _load_docs_cached(LESSONS, is_lesson=True)
    print(f"Loaded {len(docs)} lessons\n")

    print("=" * 60)
    print("BM25 Field Weighting Benchmark — Issue #311")
    print("=" * 60)

    # Old weights
    print("\n--- OLD weights ---")
    for k, v in WEIGHTS_OLD.items():
        print(f"  {k}: {v}")
    t0 = time.time()
    old_result = _run_benchmark(docs, WEIGHTS_OLD)
    old_time = time.time() - t0
    print(f"\n  Precision@5: {old_result['mean_precision_at_5']:.3f}")
    print(f"  MRR:         {old_result['mean_mrr']:.3f}")
    print(f"  Time:        {old_time*1000:.0f}ms")

    # New weights
    print("\n--- NEW weights ---")
    for k, v in WEIGHTS_NEW.items():
        print(f"  {k}: {v}")
    t0 = time.time()
    new_result = _run_benchmark(docs, WEIGHTS_NEW)
    new_time = time.time() - t0
    print(f"\n  Precision@5: {new_result['mean_precision_at_5']:.3f}")
    print(f"  MRR:         {new_result['mean_mrr']:.3f}")
    print(f"  Time:        {new_time*1000:.0f}ms")

    # Delta
    p_delta = new_result['mean_precision_at_5'] - old_result['mean_precision_at_5']
    m_delta = new_result['mean_mrr'] - old_result['mean_mrr']
    print(f"\n--- DELTA ---")
    print(f"  Precision@5: {p_delta:+.3f}")
    print(f"  MRR:         {m_delta:+.3f}")

    # Per-query comparison
    print(f"\n--- PER-QUERY COMPARISON (queries with expected results) ---")
    print(f"  {'Query':<25} {'Old P@5':>8} {'New P@5':>8} {'Delta':>8}")
    print(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*8}")
    for i, q in enumerate(QUERIES):
        if q["expected"]:
            old_p = old_result['details'][i]['precision_at_5']
            new_p = new_result['details'][i]['precision_at_5']
            delta = (new_p or 0) - (old_p or 0)
            marker = "✅" if delta > 0 else ("❌" if delta < 0 else "  ")
            print(f"  {q['query']:<25} {old_p:>8.3f} {new_p:>8.3f} {delta:>+8.3f} {marker}")

    report = {
        "old_weights": WEIGHTS_OLD,
        "new_weights": WEIGHTS_NEW,
        "old_result": {k: v for k, v in old_result.items() if k != 'details'},
        "new_result": {k: v for k, v in new_result.items() if k != 'details'},
        "delta_precision": p_delta,
        "delta_mrr": m_delta,
    }

    if json_mode:
        print(json.dumps(report, indent=2))
    else:
        report_path = REPO / "data" / "bm25_weight_benchmark.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
