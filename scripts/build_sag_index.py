#!/usr/bin/env python3
"""Build SAG-Lite SQLite FTS5 index from OKF bundle.

Usage:
    python3 scripts/build_sag_index.py                      # build from default OKF path
    python3 scripts/build_sag_index.py --okf data/okf/      # custom OKF path
    python3 scripts/build_sag_index.py --output data/sag.db # custom output

Then query:
    python3 scripts/build_sag_index.py --query "database locked"
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OKF = REPO_ROOT / "data" / "okf"
DEFAULT_DB = REPO_ROOT / "data" / "sag.db"
LESSONS_DIR = REPO_ROOT / "lessons"

# The export is a *tracked* file with no writer in CI (issue #2185), so it can be arbitrarily old
# while looking perfectly healthy: it exists, it parses, and this script is happy to build an index
# from it. Measured 2026-09-25 — a fresh export covers 411 of the 458 `lessons/**/*.md` files (the
# 47 it skips are READMEs and templates), and the version committed on 2026-07-07 covered 179. So
# the threshold sits in a wide gap, and anything below it is a stale export rather than a corpus
# that legitimately shrank.
COVERAGE_FLOOR = 0.8


def corpus_lesson_files() -> set[str]:
    """The `lessons/**/*.md` files, excluding READMEs — what a fresh export is expected to cover."""
    if not LESSONS_DIR.is_dir():
        return set()
    return {p.relative_to(REPO_ROOT).as_posix() for p in LESSONS_DIR.rglob("*.md")
            if p.name != "README.md"}


def export_coverage(records: list[dict]) -> tuple[int, int]:
    """(covered, corpus size) — how much of the corpus the export actually names."""
    corpus = corpus_lesson_files()
    if not corpus:
        return (0, 0)
    paths = {str(r.get("path") or "") for r in records}
    return (len(corpus & paths), len(corpus))


def warn_if_export_is_stale(records: list[dict]) -> bool:
    """Say so, loudly, when the export cannot be describing the corpus we are indexing.

    Not a hard failure: an old checkout, a filtered export or a partial clone are all legitimate,
    and a build script that refuses to run is a worse trap than the one it closes. But silence here
    is what let a 61%-missing index sit in the repository for two and a half months — and because
    the search path prefers SAG over BM25, the resulting index made recall *worse* than building
    nothing.
    """
    covered, total = export_coverage(records)
    if not total or covered >= total * COVERAGE_FLOOR:
        return False
    missing = total - covered
    print(f"⚠️  the OKF export looks stale: it names {covered} of {total} lessons "
          f"({missing} missing, {100 * missing / total:.0f}%).")
    print("    data/okf/lessons.jsonl is tracked and nothing regenerates it in CI (issue #2185).")
    print("    Run `python3 scripts/export_okf.py` first — otherwise this index will be preferred")
    print("    over the complete BM25 path while covering only part of the corpus.")
    return True


def build_index(okf_path: Path, db_path: Path) -> int:
    """Build FTS5 index from OKF JSONL bundle."""
    jsonl_file = okf_path / "lessons.jsonl"
    if not jsonl_file.exists():
        print(f"Error: {jsonl_file} not found. Run export_okf.py first.")
        sys.exit(1)

    # Read OKF records
    records = []
    with open(jsonl_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    warn_if_export_is_stale(records)

    # Create SQLite database
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    # Main table
    conn.execute("""
        CREATE TABLE lessons (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            domain TEXT,
            tags TEXT,
            source TEXT,
            status TEXT,
            path TEXT,
            timestamp TEXT,
            verified_date TEXT,
            domain_expert TEXT
        )
    """)

    # FTS5 virtual table for full-text search
    conn.execute("""
        CREATE VIRTUAL TABLE lessons_fts USING fts5(
            title,
            description,
            tags,
            domain,
            content=lessons,
            content_rowid=id
        )
    """)

    # Insert records
    for r in records:
        tags_str = ", ".join(r.get("tags", []))
        conn.execute(
            "INSERT INTO lessons (title, description, domain, tags, source, status, path,"
            " timestamp, verified_date, domain_expert) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                r.get("title", ""),
                r.get("description", ""),
                r.get("domain", ""),
                tags_str,
                r.get("source", ""),
                r.get("status", ""),
                r.get("path", ""),
                r.get("timestamp", ""),
                r.get("verified_date", ""),
                r.get("domain_expert", ""),
            ),
        )

    # Populate FTS index
    conn.execute("INSERT INTO lessons_fts(lessons_fts) VALUES('rebuild')")

    conn.commit()
    conn.close()

    return len(records)


# FTS5 treats a bare query as an expression language: `-`, `:`, `*`, `"`, `(`, `)`,
# and the operators AND/OR/NOT are all syntax. Real error text is full of them
# ("ModuleNotFoundError: No module named x", "docker multi-stage build OOM",
# "GH013: Secret scanning found"), so passing the raw string to MATCH raises
# sqlite3.OperationalError and the caller never sees a result. Extract the word
# tokens and quote each one, which is the only form FTS5 cannot misparse.
_FTS_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def _fts_expression(query: str, operator: str = "AND") -> str:
    """Build a quoted FTS5 expression from arbitrary user text.

    Returns "" when the query has no word characters, which callers treat as
    "no results" rather than sending an empty MATCH (itself a syntax error).
    """
    tokens = _FTS_TOKEN_RE.findall(query or "")
    return f" {operator} ".join(f'"{t}"' for t in tokens)


def search(db_path: Path, query: str, domain: str | None = None, top: int = 5) -> list[dict]:
    """Search the SAG-Lite index.

    Tries an AND over the query's word tokens first (precise), then falls back to
    OR (recall) when AND finds nothing — an error message is usually a sentence,
    and requiring every token of it to appear would return nothing at all.
    """
    if not db_path.exists():
        print(f"Error: {db_path} not found. Run build first.")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    if domain:
        sql = """
            SELECT l.*, rank
            FROM lessons_fts fts
            JOIN lessons l ON l.id = fts.rowid
            WHERE lessons_fts MATCH ? AND l.domain = ?
            ORDER BY rank
            LIMIT ?
        """
    else:
        sql = """
            SELECT l.*, rank
            FROM lessons_fts fts
            JOIN lessons l ON l.id = fts.rowid
            WHERE lessons_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """

    rows = []
    for operator in ("AND", "OR"):
        expression = _fts_expression(query, operator)
        if not expression:
            break
        params = (expression, domain, top) if domain else (expression, top)
        rows = conn.execute(sql, params).fetchall()
        if rows:
            break

    conn.close()

    results = []
    for r in rows:
        # Clean description: remove any remaining frontmatter patterns
        desc = r["description"] or ""
        if desc.startswith("---") or desc.startswith("{"):
            desc = ""

        results.append({
            "title": r["title"],
            "description": desc,
            "domain": r["domain"],
            "tags": r["tags"],
            "source": r["source"],
            "path": r["path"],
            "status": r["status"] or "",
            "score": round(abs(r["rank"]), 4) if r["rank"] else 0,
        })

    return results


def main():
    parser = argparse.ArgumentParser(description="SAG-Lite: SQLite FTS5 search for MisakaNet")
    parser.add_argument("--okf", type=str, default=str(DEFAULT_OKF), help="OKF bundle directory")
    parser.add_argument("--output", type=str, default=str(DEFAULT_DB), help="SQLite database path")
    parser.add_argument("--query", type=str, default=None, help="Search query")
    parser.add_argument("--domain", type=str, default=None, help="Filter by domain")
    parser.add_argument("--top", type=int, default=5, help="Number of results")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    db_path = Path(args.output)

    if args.query:
        # Search mode
        results = search(db_path, args.query, domain=args.domain, top=args.top)
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            if not results:
                print("No results found.")
                return
            for i, r in enumerate(results, 1):
                print(f"[{i}] {r['title']} (score: {r['score']})")
                print(f"    Domain: {r['domain']} | Source: {r['source']}")
                if r['description']:
                    print(f"    {r['description'][:100]}")
                print()
    else:
        # Build mode
        okf_path = Path(args.okf)
        count = build_index(okf_path, db_path)
        print(f"SAG-Lite index built: {count} lessons -> {db_path}")
        print("Query: python3 scripts/build_sag_index.py --query \"your search\"")


if __name__ == "__main__":
    main()
