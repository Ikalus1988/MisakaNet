"""Lesson quality scorer — uses search telemetry to rank lessons by relevance.

Reads query history from the langchain_telemetry.db and scores each lesson
in lessons/contrib/ and lessons/core/ by how often its content matches
search queries (BM25 token overlap).
"""
from __future__ import annotations

import math
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent.parent
LESSONS_CONTRIB = REPO / "lessons" / "contrib"
LESSONS_CORE = REPO / "lessons" / "core"
DEFAULT_TELEMETRY = REPO / ".cache" / "langchain_telemetry.db"

# BM25 parameters (same as search engine)
K1 = 1.5
B = 0.75


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words, splitting CJK characters individually."""
    t = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", text.lower())
    tokens = []
    for part in t.split():
        if re.search(r"[\u4e00-\u9fff]", part):
            for ch in part:
                tokens.append(ch)
        else:
            tokens.append(part)
    return tokens


def _read_telemetry_queries(telemetry_path: Path) -> list[str]:
    """Read all query strings from the telemetry database."""
    if not telemetry_path.exists():
        return []
    conn = sqlite3.connect(str(telemetry_path), timeout=5)
    try:
        rows = conn.execute(
            "SELECT query FROM search_telemetry"
        ).fetchall()
        return [row[0] for row in rows if row[0]]
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return []
    finally:
        conn.close()


def _load_lessons() -> list[tuple[str, str, str]]:
    """Load all lessons from core/ and contrib/.

    Returns list of (slug, title, content) tuples.
    Slug is the filename without .md extension.
    """
    lessons = []
    for dir_path in [LESSONS_CORE, LESSONS_CONTRIB]:
        if not dir_path.exists():
            continue
        for f in sorted(dir_path.glob("**/*.md")):
            if f.name == "index.md" or f.name.startswith("."):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue
            if not content.strip():
                continue
            slug = f.stem
            # Extract title from frontmatter or first heading
            title = _extract_title(content, slug)
            lessons.append((slug, title, content))
    return lessons


def _extract_title(content: str, fallback: str) -> str:
    """Extract title from JSON/YAML frontmatter or first markdown heading."""
    # JSON frontmatter
    m = re.match(r"^---\s*\n?(\{.*?\})\n?---", content, re.DOTALL)
    if m:
        import json
        try:
            meta = json.loads(m.group(1))
            if "title" in meta:
                return meta["title"]
        except json.JSONDecodeError:
            pass
    # YAML frontmatter
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if m:
        for line in m.group(1).split("\n"):
            line = line.strip()
            if line.startswith("title:"):
                return line[6:].strip().strip('"').strip("'")
    # First heading
    m = re.search(r"^#{1,3}\s+(.+)$", content, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return fallback


def score_lessons(
    telemetry_path: str | Path | None = None,
) -> list[dict]:
    """Score lessons by how often their content matches search telemetry queries.

    Args:
        telemetry_path: Path to langchain_telemetry.db.
                        Defaults to .cache/langchain_telemetry.db.

    Returns:
        List of dicts sorted by score descending:
        [{"lesson": "slug", "score": 0.85, "searches": 12}, ...]
        Lessons with zero matches have score 0.0.
    """
    if telemetry_path is None:
        tp = DEFAULT_TELEMETRY
    else:
        tp = Path(telemetry_path)

    queries = _read_telemetry_queries(tp)
    lessons = _load_lessons()

    if not lessons:
        return []

    # Pre-tokenize all lessons
    lesson_tokens = []
    for slug, title, content in lessons:
        # Combine title (weighted 3x) + content for matching
        combined = f"{title} {title} {title} {content}"
        lesson_tokens.append(Counter(_tokenize(combined)))

    # Pre-tokenize all queries
    query_token_lists = [_tokenize(q) for q in queries]

    # Score each lesson: count how many queries have meaningful overlap
    results = []
    total_queries = len(queries)

    for idx, (slug, title, content) in enumerate(lessons):
        lt = lesson_tokens[idx]
        if not lt:
            results.append({"lesson": slug, "score": 0.0, "searches": 0})
            continue

        match_count = 0
        total_bm25 = 0.0

        for qt in query_token_lists:
            if not qt:
                continue
            # Check token overlap
            overlap = sum(1 for t in qt if lt.get(t, 0) > 0)
            if overlap == 0:
                continue
            match_count += 1

            # Compute BM25 score for this query-lesson pair
            N = len(lessons)
            doc_len = sum(lt.values())
            avg_doc_len = sum(sum(lt.values()) for lt in lesson_tokens) / max(N, 1)
            score = 0.0
            for term in qt:
                tf = lt.get(term, 0)
                if tf == 0:
                    continue
                # Document frequency: how many lessons contain this term
                df = sum(1 for lt2 in lesson_tokens if lt2.get(term, 0) > 0)
                idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
                numerator = tf * (K1 + 1)
                denominator = tf + K1 * (1 - B + B * doc_len / max(avg_doc_len, 1))
                score += idf * numerator / denominator
            total_bm25 += score

        # Normalize score to 0-1 range
        if match_count > 0 and total_queries > 0:
            raw_score = total_bm25 / match_count
            # Normalize: divide by a reasonable max (empirically ~10 for BM25)
            normalized = min(raw_score / 10.0, 1.0)
        else:
            normalized = 0.0

        results.append({
            "lesson": slug,
            "score": round(normalized, 4),
            "searches": match_count,
        })

    # Sort by score descending, then by searches descending
    results.sort(key=lambda x: (-x["score"], -x["searches"]))
    return results
