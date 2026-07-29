#!/usr/bin/env python3
"""SAG-Lite search: query the SQLite FTS5 index.

Usage:
    python3 scripts/sag_search.py "pip timeout" [--top 5] [--json] [--domain python]

Can also be imported as a module for the /api/sag endpoint.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO_ROOT / "data" / "sag" / "search.db"


def search(query: str, db_path: Path = DEFAULT_DB, top_k: int = 5, domain: str = "") -> list[dict]:
    """Search the SAG-Lite index. Returns ranked results."""
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # FTS5 match query
    fts_query = query.replace('"', '""')
    sql = """
        SELECT l.id, l.title, l.description, l.domain, l.tags, l.source_path, l.timestamp,
               rank
        FROM lessons_fts
        JOIN lessons l ON lessons_fts.rowid = l.rowid
        WHERE lessons_fts MATCH ?
    """
    params: list = [fts_query]

    if domain:
        sql += " AND l.domain = ?"
        params.append(domain)

    sql += " ORDER BY rank LIMIT ?"
    params.append(top_k)

    try:
        cur.execute(sql, params)
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        # Fallback: LIKE search if FTS query syntax fails
        sql = "SELECT id, title, description, domain, tags, source_path, timestamp, 0 as rank FROM lessons WHERE title LIKE ? OR description LIKE ?"
        params = [f"%{query}%", f"%{query}%"]
        if domain:
            sql += " AND domain = ?"
            params.append(domain)
        sql += " LIMIT ?"
        params.append(top_k)
        cur.execute(sql, params)
        rows = cur.fetchall()

    conn.close()

    results = []
    for row in rows:
        results.append({
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "domain": row["domain"],
            "tags": row["tags"].split(",") if row["tags"] else [],
            "source_path": row["source_path"],
            "timestamp": row["timestamp"],
            "score": abs(row["rank"]) if row["rank"] else 0,
        })
    return results


def main():
    parser = argparse.ArgumentParser(description="SAG-Lite knowledge search")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--top", type=int, default=5, help="Number of results")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--domain", default="", help="Filter by domain")
    parser.add_argument("--db", default=None, help="Database path")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else DEFAULT_DB
    results = search(args.query, db_path=db_path, top_k=args.top, domain=args.domain)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        if not results:
            print(f"No results for: {args.query}")
            return
        for i, r in enumerate(results, 1):
            print(f"  {i}. [{r['domain']}] {r['title']}")
            if r["description"]:
                print(f"     {r['description'][:100]}")
            print(f"     path: {r['source_path']}")
            print()


if __name__ == "__main__":
    main()
