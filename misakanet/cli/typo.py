"""Typo-tolerant retry and zero-result fallback helpers.

Extracted from search_knowledge.py (audit 2026-09-05, T1.1 stage 2): fuzzy
title matching (_edit_distance / _typo_retry_search), closest-match and
relaxed-query suggestions, and the _smart_fallback UX. The CLI entry keeps
the original names via a module-level re-import.
"""
import json
import re
from pathlib import Path


def _edit_distance(s1: str, s2: str) -> int:
    """Levenshtein edit distance — O(len(s1)*len(s2))."""
    if len(s1) < len(s2):
        return _edit_distance(s2, s1)
    if not s2:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[len(s2)]


def _typo_retry_search(
    query: str, docs: list, titles_only: bool, broad_only: bool, top_k: int
) -> tuple[list[tuple[float, object]], str]:
    """Retry search with edit-distance fuzzy matching on title keywords.

    For each query token, find title tokens within edit distance ≤2.
    Build a corrected query from the best matches, then re-rank.
    Returns (ranked_results, corrected_query) or ([], original_query).
    """
    query_tokens = query.lower().split()
    if not query_tokens:
        return [], query

    # Build vocabulary from all doc titles
    title_vocab: dict[str, list[str]] = {}  # token -> [original forms]
    for doc in docs:
        for tok in re.findall(r'\w+', doc.title.lower()):
            if len(tok) >= 2:
                title_vocab.setdefault(tok, []).append(tok)

    # For each query token, find best fuzzy match in title vocab
    corrected_tokens = []
    has_correction = False
    for qt in query_tokens:
        if qt in title_vocab:
            corrected_tokens.append(qt)
            continue
        best_dist = 999
        best_match = qt
        for vocab_tok in title_vocab:
            # Skip if length difference > 2 (pruning for speed)
            if abs(len(vocab_tok) - len(qt)) > 2:
                continue
            dist = _edit_distance(qt, vocab_tok)
            if dist <= 2 and dist < best_dist:
                best_dist = dist
                best_match = vocab_tok
        corrected_tokens.append(best_match)
        if best_match != qt:
            has_correction = True

    if not has_correction:
        return [], query

    corrected_query = " ".join(corrected_tokens)
    from misakanet.search.engine import _rank_docs_impl
    ranked = _rank_docs_impl(corrected_query, docs, titles_only, broad_only)
    filtered = [(s, d) for s, d in ranked if s >= 0.1]
    if not filtered:
        return [], query
    return filtered[:top_k], corrected_query


def _find_closest_matches(query: str, docs: list, top_n: int = 3) -> list:
    """Find closest matches by keyword overlap scoring."""
    query_words = set(re.findall(r'\w+', query.lower()))
    if not query_words:
        return []

    scored = []
    for doc in docs:
        doc_words = set(re.findall(r'\w+', (doc.title + " " + doc.content[:500]).lower()))
        if not doc_words:
            continue
        overlap = len(query_words & doc_words)
        if overlap > 0:
            score = overlap / len(query_words)
            scored.append((score, doc))

    scored.sort(key=lambda x: -x[0])
    return scored[:top_n]


def _suggest_relaxed_query(query: str) -> list:
    """Suggest relaxed queries by dropping stop words."""
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                  "being", "have", "has", "had", "do", "does", "did", "will",
                  "would", "could", "should", "may", "might", "can", "shall",
                  "of", "in", "on", "at", "to", "for", "with", "by", "from",
                  "as", "into", "through", "during", "before", "after", "and",
                  "but", "or", "not", "so", "very", "just", "than", "too"}
    words = query.lower().split()
    meaningful = [w for w in words if w not in stop_words]
    if len(meaningful) >= 2:
        # Suggest dropping last word
        return [" ".join(meaningful[:-1])]
    if len(meaningful) == 1:
        return [meaningful[0]]
    return []


def _log_zero_result(query: str):
    """Log zero-result query for gap analysis."""
    import datetime
    log_dir = Path.home() / ".misakanet"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "search_telemetry.jsonl"

    entry = {
        "query": query,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "result": "zero",
    }

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # Non-critical, don't fail search

    # Check if same query failed >3 times → suggest creating issue
    try:
        if log_file.exists():
            lines = log_file.read_text(encoding="utf-8").strip().split("\n")
            count = sum(1 for ln in lines if f'"query": "{query}"' in ln)
            if count >= 3:
                print(f"  ⚠️  This query has returned 0 results {count} times.")
                print("     Consider creating an issue for a missing lesson:")
                url = (
                    "https://github.com/Ikalus1988/MisakaNet/issues/new"
                    f"?title=Missing+lesson:+{query.replace(' ', '+')}"
                )
                print(f"     {url}")
                print()
    except Exception:
        pass


def _smart_fallback(query: str, docs: list):
    """Smart fallback when search returns 0 results."""
    print(f"\n  ❌ No exact match for '{query}'")
    print()

    # 1. Top-3 closest matches by keyword overlap
    closest = _find_closest_matches(query, docs, top_n=3)
    if closest:
        print("  📋 Closest matches:")
        for score, doc in closest:
            title = doc.title[:60] or doc.filename
            print(f"     [{score:.0%}] {title}")
        print()

    # 2. "Did you mean: ..." with relaxed query
    suggestions = _suggest_relaxed_query(query)
    if suggestions:
        print(f"  💡 Did you mean: \"{suggestions[0]}\"?")
        print()

    # 3. Domain suggestions
    all_domains = {d.domain.lower() for d in docs if d.domain}
    q = query.lower()
    domain_matches = [d for d in all_domains if d in q or q in d]
    if domain_matches:
        print("  💡 Try domain filter:")
        for dm in domain_matches[:3]:
            print(f"     --domain {dm}")

    # 4. Broad mode hint
    print("  💡 Try broader search: --broad or --ref")

    # 5. Contribution link
    print("  💡 Add new knowledge:")
    print(f"     python3 scripts/queue_lesson.py -t \"{query}\" ...")

    # 6. Available domains
    if all_domains:
        top_domains = sorted(all_domains)[:8]
        print(f"  💡 Available domains: {', '.join(top_domains)}")

    print()


