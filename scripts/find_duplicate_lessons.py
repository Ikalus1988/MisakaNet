#!/usr/bin/env python3
"""Find duplicate/near-duplicate lessons — Issue #310.

Scans lessons/ for title + content similarity and produces a merge report.

Usage:
    python3 scripts/find_duplicate_lessons.py
    python3 scripts/find_duplicate_lessons.py --json
    python3 scripts/find_duplicate_lessons.py --threshold 0.5
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from misakanet.search.engine import LESSONS, _load_docs_cached, _tokenize


def _content_similarity(tokens1: set, tokens2: set) -> float:
    """Jaccard similarity between two token sets."""
    if not tokens1 or not tokens2:
        return 0.0
    return len(tokens1 & tokens2) / len(tokens1 | tokens2)


def find_duplicates(threshold: float = 0.5):
    """Find duplicate lesson pairs above similarity threshold."""
    docs = _load_docs_cached(LESSONS, is_lesson=True)

    pairs = []
    for i, d1 in enumerate(docs):
        t1_title = set(_tokenize(d1.title))
        t1_content = set(_tokenize(d1.content[:2000]))  # first 2k chars
        t1_all = t1_title | t1_content

        for j, d2 in enumerate(docs):
            if j <= i:
                continue
            t2_title = set(_tokenize(d2.title))
            t2_content = set(_tokenize(d2.content[:2000]))
            t2_all = t2_title | t2_content

            # Title similarity
            title_sim = 0.0
            if t1_title and t2_title:
                title_sim = len(t1_title & t2_title) / min(len(t1_title), len(t2_title))

            # Content similarity
            content_sim = _content_similarity(t1_content, t2_content)

            # Combined score (title weighted more)
            combined = 0.6 * title_sim + 0.4 * content_sim

            if combined >= threshold:
                pairs.append({
                    "score": round(combined, 3),
                    "title_sim": round(title_sim, 3),
                    "content_sim": round(content_sim, 3),
                    "file1": d1.filename,
                    "file2": d2.filename,
                    "title1": d1.title[:60],
                    "title2": d2.title[:60],
                    "domain1": d1.domain,
                    "domain2": d2.domain,
                })

    pairs.sort(key=lambda x: -x["score"])
    return pairs


def main():
    json_mode = "--json" in sys.argv
    threshold = 0.5
    for i, arg in enumerate(sys.argv):
        if arg == "--threshold" and i + 1 < len(sys.argv):
            threshold = float(sys.argv[i + 1])

    pairs = find_duplicates(threshold)

    if json_mode:
        print(json.dumps(pairs, indent=2, ensure_ascii=False))
        return

    print(f"Duplicate Lesson Analysis — Issue #310")
    print(f"Threshold: {threshold}")
    print(f"Found {len(pairs)} duplicate pairs\n")

    print(f"{'Score':>6} {'Title Sim':>10} {'Content':>10}  File 1 ↔ File 2")
    print(f"{'-'*6} {'-'*10} {'-'*10}  {'-'*60}")
    for p in pairs:
        print(f"{p['score']:>6.3f} {p['title_sim']:>10.3f} {p['content_sim']:>10.3f}  "
              f"{p['file1'][:40]} ↔ {p['file2'][:40]}")

    # Merge recommendations
    print(f"\n{'='*60}")
    print("Merge Recommendations (score >= 0.8):")
    print(f"{'='*60}")
    high = [p for p in pairs if p["score"] >= 0.8]
    for i, p in enumerate(high, 1):
        print(f"\n  {i}. {p['title1']}")
        print(f"     ↔ {p['title2']}")
        print(f"     Score: {p['score']} (title: {p['title_sim']}, content: {p['content_sim']})")
        print(f"     Action: Keep higher-quality version, archive the other")


if __name__ == "__main__":
    main()
