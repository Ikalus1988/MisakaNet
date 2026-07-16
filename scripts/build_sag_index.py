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
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OKF = REPO_ROOT / "data" / "okf"
DEFAULT_DB = REPO_ROOT / "data" / "sag.db"


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
            "INSERT INTO lessons (title, description, domain, tags, source, status, path, timestamp, verified_date, domain_expert) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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


def search(db_path: Path, query: str, domain: str | None = None, top: int = 5) -> list[dict]:
    """Search the SAG-Lite index."""
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
        rows = conn.execute(sql, (query, domain, top)).fetchall()
    else:
        sql = """
            SELECT l.*, rank
            FROM lessons_fts fts
            JOIN lessons l ON l.id = fts.rowid
            WHERE lessons_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """
        rows = conn.execute(sql, (query, top)).fetchall()

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
        print(f"Query: python3 scripts/build_sag_index.py --query \"your search\"")


if __name__ == "__main__":
    main()
