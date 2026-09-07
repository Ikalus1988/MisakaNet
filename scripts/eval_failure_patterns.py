#!/usr/bin/env python3
"""Evaluate error-signature index (failure_patterns) accuracy and hit-rate delta.

Benchmarks 10 known error<->lesson pairs against:
1. Baseline token overlap / BM25 search without error signatures.
2. Error-signature pattern matcher (failure_patterns sidecar index).
3. Search engine ranking with failure pattern boost.
4. Intake-bot precheck pipeline.

Reports precision, recall, and hit-rate delta.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from misakanet.search.patterns import (
    find_best_pattern_match,
    load_failure_patterns,
)
from misakanet.search.engine import (
    LESSONS,
    _compute_bm25_scores,
    _compute_boost,
    _load_docs,
    _metadata_bonus,
    _normalize,
    _rank_docs_impl,
)
from scripts.intake_bot import _sim, _tokens, precheck

SPOT_CHECK_PAIRS = [
    (
        "dco-auto-fix-workflow",
        "Commit sha: 8f9b1c2, Author: user, Committer: user; Expected \"Signed-off-by: user <user@example.com>\", but got \"\"",
        "DCO sign-off check failure in commit message",
    ),
    (
        "fehler-python-modul-nicht-gefunden",
        "ModuleNotFoundError: No module named 'requests'",
        "Missing python package dependency import",
    ),
    (
        "aider-windows-unicode-error",
        "UnicodeEncodeError: 'gbk' codec can't encode character in position 14: illegal multibyte sequence",
        "Windows terminal GBK encoding failure",
    ),
    (
        "hermes-state-database-lock-issues-cleanup-protocol",
        "sqlite3.OperationalError: database is locked on SQLite state.db",
        "SQLite concurrency lock error",
    ),
    (
        "pull-request-welcome-trigger-trap",
        "Skipping pr-welcome.yml: condition 'contains(fromJSON('[\"FIRST_TIMER\", \"FIRST_TIME_CONTRIBUTOR\"]'), github.event.pull_request.author_association)' evaluated to false",
        "GitHub Actions workflow author association condition skipped",
    ),
    (
        "gitguardian-placeholder-url-credential-safe-form",
        "GitGuardian: Secret type: Basic Auth String detected at lessons/xxx.md:32",
        "GitGuardian secret scanner alert on credential URL",
    ),
    (
        "asyncio-cancellederror-swallows-resources",
        "Python asyncio CancelledError Silently Swallows Resources in Long-Running Services",
        "Asyncio task cancellation resource leak",
    ),
    (
        "n8n-nodejs-econnreset-connection-reset-fix",
        "NodeApiError: read ECONNRESET at TCP.onStreamRead",
        "NodeJS TCP socket reset during HTTP webhook call",
    ),
    (
        "aider-litellm-model-name-rejection",
        "LiteLLM requires provider prefix for custom endpoints: anthropic/claude-sonnet-4-6",
        "LiteLLM model provider routing error",
    ),
    (
        "lesson-07-uv-venv-seed-fix-no-pip",
        "ModuleNotFoundError: No module named 'pip' in Ubuntu WSL",
        "UV virtualenv seed without pip packaging tool",
    ),
]


def run_evaluation() -> dict[str, float]:
    """Execute evaluation across baseline and error-signature pipelines.

    Returns dictionary containing benchmark metrics and hit rates.
    """
    patterns = load_failure_patterns()
    docs = _load_docs(LESSONS, is_lesson=True)

    lessons_file = REPO_ROOT / "data" / "lessons.json"
    corpus = json.loads(lessons_file.read_text(encoding="utf-8")) if lessons_file.exists() else []

    direct_pattern_hits = 0
    search_baseline_hits = 0
    search_boosted_hits = 0
    intake_baseline_hits = 0
    intake_boosted_hits = 0

    total = len(SPOT_CHECK_PAIRS)
    rows: list[dict[str, str | bool | float]] = []

    for expected_id, query, description in SPOT_CHECK_PAIRS:
        matched_id, pat_score, pat_desc = find_best_pattern_match(query, patterns)
        direct_hit = matched_id == expected_id
        if direct_hit:
            direct_pattern_hits += 1

        bm25_raw = _compute_bm25_scores(query, docs)
        bm25_norm = _normalize(bm25_raw)
        scored_baseline = [
            (
                0.5 * bm25_norm[i]
                + 0.3 * _metadata_bonus(query, d)
                + 0.1 * d.score_baseline
                + _compute_boost(d),
                d,
            )
            for i, d in enumerate(docs)
        ]
        scored_baseline.sort(key=lambda x: -x[0])
        base_top1_id = scored_baseline[0][1].filepath.stem if scored_baseline else ""
        search_base_hit = base_top1_id == expected_id
        if search_base_hit:
            search_baseline_hits += 1

        scored_boosted = _rank_docs_impl(query, docs)
        boosted_top1_id = scored_boosted[0][1].filepath.stem if scored_boosted else ""
        search_boost_hit = boosted_top1_id == expected_id
        if search_boost_hit:
            search_boosted_hits += 1

        q_tokens = _tokens(query)
        best_doc, best_token_score = None, 0.0
        for doc in corpus:
            title_tokens = _tokens(doc.get("title") or "")
            body_tokens = _tokens((doc.get("description") or "")[:500])
            token_score = max(_sim(q_tokens, title_tokens) * 2.0, _sim(q_tokens, body_tokens))
            if token_score > best_token_score:
                best_doc, best_token_score = doc, token_score
        intake_base_id = (best_doc.get("id") or best_doc.get("slug")) if (best_doc and best_token_score >= 0.30) else ""
        intake_base_hit = intake_base_id == expected_id
        if intake_base_hit:
            intake_baseline_hits += 1

        precheck_res = precheck(query, sim_threshold=0.30)
        precheck_id = precheck_res.get("id") if precheck_res else ""
        intake_boost_hit = precheck_id == expected_id
        if intake_boost_hit:
            intake_boosted_hits += 1

        rows.append({
            "expected_id": expected_id,
            "pat_score": pat_score,
            "direct_hit": direct_hit,
            "search_base_hit": search_base_hit,
            "search_boost_hit": search_boost_hit,
            "intake_base_hit": intake_base_hit,
            "intake_boost_hit": intake_boost_hit,
        })

    print(f"{'Target Lesson ID':<46} | {'Direct':<8} | {'Srch Base':<10} | {'Srch Boost':<10} | {'Intk Base':<10} | {'Intk Boost':<10}")
    print("-" * 105)
    for r in rows:
        print(
            f"{str(r['expected_id']):<46} | "
            f"{str(r['direct_hit']):<8} | "
            f"{str(r['search_base_hit']):<10} | "
            f"{str(r['search_boost_hit']):<10} | "
            f"{str(r['intake_base_hit']):<10} | "
            f"{str(r['intake_boost_hit']):<10}"
        )

    direct_acc = direct_pattern_hits / total
    search_base_acc = search_baseline_hits / total
    search_boost_acc = search_boosted_hits / total
    intake_base_acc = intake_baseline_hits / total
    intake_boost_acc = intake_boosted_hits / total

    print("\nBenchmark Summary:")
    print(f"- Direct Pattern Top-1 Accuracy:     {direct_pattern_hits}/{total} ({direct_acc:.1%})")
    print(f"- Search Engine Baseline Top-1:      {search_baseline_hits}/{total} ({search_base_acc:.1%})")
    print(f"- Search Engine Boosted Top-1:       {search_boosted_hits}/{total} ({search_boost_acc:.1%}) [Delta: +{(search_boost_acc - search_base_acc):.1%}]")
    print(f"- Intake Bot Baseline Top-1:         {intake_baseline_hits}/{total} ({intake_base_acc:.1%})")
    print(f"- Intake Bot Boosted Top-1:          {intake_boosted_hits}/{total} ({intake_boost_acc:.1%}) [Delta: +{(intake_boost_acc - intake_base_acc):.1%}]")

    return {
        "direct_acc": direct_acc,
        "search_base_acc": search_base_acc,
        "search_boost_acc": search_boost_acc,
        "intake_base_acc": intake_base_acc,
        "intake_boost_acc": intake_boost_acc,
    }


if __name__ == "__main__":
    metrics = run_evaluation()
    if metrics["direct_acc"] < 0.80 or metrics["intake_boost_acc"] < 0.80:
        sys.exit(1)
    sys.exit(0)
