#!/usr/bin/env python3
"""Build pre-computed BM25 index for Worker-side search.

This script generates a lightweight JSON index that the Cloudflare Worker
can use for BM25 scoring instead of naive keyword matching.

Usage:
    python scripts/build_worker_index.py --lessons lessons/ --output data/worker-index.json
    python scripts/build_worker_index.py --lessons lessons/ --output data/worker-index.json --k1 1.5 --b 0.75

The index format is optimized for Worker KV storage and fast lookups.
"""

import argparse
import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# BM25 parameters (standard defaults)
DEFAULT_K1 = 1.5
DEFAULT_B = 0.75

# Minimum term length to index
MIN_TERM_LENGTH = 2

# Stopwords to exclude from indexing
STOPWORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her",
    "she", "or", "an", "will", "my", "one", "all", "would", "there",
    "their", "what", "so", "up", "out", "if", "about", "who", "get",
    "which", "go", "me", "when", "make", "can", "like", "time", "no",
    "just", "him", "know", "take", "people", "into", "year", "your",
    "good", "some", "could", "them", "see", "other", "than", "then",
    "now", "look", "only", "come", "its", "over", "think", "also",
    "back", "after", "use", "two", "how", "our", "work", "first",
    "well", "way", "even", "new", "want", "because", "any", "these",
    "give", "day", "most", "us",
}


def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase terms, filtering stopwords."""
    # Split on non-alphanumeric, convert to lowercase
    terms = re.findall(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", text.lower())
    return [t for t in terms if len(t) >= MIN_TERM_LENGTH and t not in STOPWORDS]


def extract_lesson_text(lesson: dict) -> str:
    """Extract searchable text from a lesson."""
    parts = []
    for field in ["title", "name", "description", "problem", "root_cause", "solution"]:
        if lesson.get(field):
            parts.append(str(lesson[field]))
    if lesson.get("tags") and isinstance(lesson["tags"], list):
        parts.extend(lesson["tags"])
    if lesson.get("domain"):
        parts.append(lesson["domain"])
    return " ".join(parts)


def load_lessons(lessons_dir: str) -> list[dict]:
    """Load all lessons from directory."""
    lessons = []
    lessons_path = Path(lessons_dir)

    for md_file in lessons_path.rglob("*.md"):
        if md_file.name == "README.md" or md_file.name == "TEMPLATE.md":
            continue

        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Parse frontmatter (YAML or JSON)
        lesson = {"path": str(md_file.relative_to(lessons_path))}

        if content.startswith("---"):
            # YAML frontmatter
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    import yaml

                    fm = yaml.safe_load(parts[1])
                    if isinstance(fm, dict):
                        lesson.update(fm)
                except Exception:
                    # Try JSON in YAML
                    try:
                        fm = json.loads(parts[1].strip())
                        if isinstance(fm, dict):
                            lesson.update(fm)
                    except Exception:
                        pass
        elif content.startswith("{"):
            # JSON frontmatter
            try:
                end = content.index("}") + 1
                fm = json.loads(content[:end])
                if isinstance(fm, dict):
                    lesson.update(fm)
            except Exception:
                pass

        if not lesson.get("id"):
            lesson["id"] = md_file.stem

        lessons.append(lesson)

    return lessons


def build_index(lessons: list[dict], k1: float, b: float) -> dict:
    """Build BM25 inverted index."""
    doc_count = len(lessons)
    if doc_count == 0:
        return {"version": 1, "docCount": 0, "avgDocLen": 0, "terms": {}, "docs": []}

    # Document metadata
    docs = []
    doc_lengths = []
    term_doc_freq = defaultdict(list)  # term -> [(doc_id, tf, doc_len)]

    for i, lesson in enumerate(lessons):
        text = extract_lesson_text(lesson)
        terms = tokenize(text)
        doc_len = len(terms)
        doc_lengths.append(doc_len)

        # Term frequency for this document
        tf_map = defaultdict(int)
        for term in terms:
            tf_map[term] += 1

        doc_info = {
            "id": lesson.get("id", f"doc_{i}"),
            "title": lesson.get("title", lesson.get("name", "")),
            "domain": lesson.get("domain", ""),
            "path": lesson.get("path", ""),
            "len": doc_len,
        }
        docs.append(doc_info)

        # Add to inverted index
        for term, tf in tf_map.items():
            term_doc_freq[term].append({"doc": i, "tf": tf, "len": doc_len})

    avg_doc_len = sum(doc_lengths) / doc_count if doc_count > 0 else 0

    # Build terms dictionary with IDF
    terms_dict = {}
    for term, doc_entries in term_doc_freq.items():
        df = len(doc_entries)
        # BM25 IDF: log((N - df + 0.5) / (df + 0.5) + 1)
        idf = math.log((doc_count - df + 0.5) / (df + 0.5) + 1)
        terms_dict[term] = {
            "df": df,
            "idf": round(idf, 4),
            "docs": doc_entries,
        }

    return {
        "version": 1,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "docCount": doc_count,
        "avgDocLen": round(avg_doc_len, 1),
        "k1": k1,
        "b": b,
        "terms": terms_dict,
        "docs": docs,
    }


def optimize_index(index: dict) -> dict:
    """Optimize index for smaller size."""
    # Remove low-frequency terms (df=1) to reduce size
    # These terms are too rare to be useful and add noise
    optimized_terms = {}
    for term, data in index["terms"].items():
        if data["df"] >= 2:
            optimized_terms[term] = data
        elif len(term) > 5:  # Keep long unique terms (likely specific)
            optimized_terms[term] = data

    index["terms"] = optimized_terms
    return index


def main():
    parser = argparse.ArgumentParser(
        description="Build BM25 index for Worker-side search"
    )
    parser.add_argument(
        "--lessons",
        required=True,
        help="Path to lessons directory",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON file path",
    )
    parser.add_argument(
        "--k1",
        type=float,
        default=DEFAULT_K1,
        help=f"BM25 k1 parameter (default: {DEFAULT_K1})",
    )
    parser.add_argument(
        "--b",
        type=float,
        default=DEFAULT_B,
        help=f"BM25 b parameter (default: {DEFAULT_B})",
    )
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Optimize index to reduce size",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print index statistics",
    )
    args = parser.parse_args()

    print(f"Loading lessons from {args.lessons}...")
    lessons = load_lessons(args.lessons)
    print(f"Loaded {len(lessons)} lessons")

    print("Building BM25 index...")
    index = build_index(lessons, args.k1, args.b)

    if args.optimize:
        print("Optimizing index...")
        index = optimize_index(index)

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write index
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

    file_size = output_path.stat().st_size
    print(f"Index written to {args.output} ({file_size:,} bytes)")

    if args.stats:
        print("\nIndex Statistics:")
        print(f"  Documents: {index['docCount']}")
        print(f"  Unique terms: {len(index['terms'])}")
        print(f"  Avg doc length: {index['avgDocLen']} tokens")
        print(f"  BM25 parameters: k1={index['k1']}, b={index['b']}")

        # Top terms by document frequency
        top_terms = sorted(
            index["terms"].items(), key=lambda x: x[1]["df"], reverse=True
        )[:20]
        print("\n  Top 20 terms by document frequency:")
        for term, data in top_terms:
            print(f"    {term}: df={data['df']}, idf={data['idf']}")


if __name__ == "__main__":
    main()
