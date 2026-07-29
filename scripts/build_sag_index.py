#!/usr/bin/env python3
"""Build SAG-Lite SQLite search index from OKF bundle.

SAG-Lite: SQLite-backed Agent Knowledge search.
No vector DB needed — uses FTS5 for full-text search.

Usage:
    python3 scripts/build_sag_index.py [--db data/sag/search.db]

Requires: python3 scripts/export_okf.py to be run first (generates data/okf/lessons.jsonl)
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OKF_FILE = REPO_ROOT / "data" / "okf" / "lessons.jsonl"


def build_index(db_path: Path, okf_file: Path) -> int:
    """Build SQLite FTS5 index from OKF JSONL."""
    if not okf_file.exists():
        print(f"Error: OKF file not found: {okf_file}", file=sys.stderr)
        print("Run: python3 scripts/export_okf.py first", file=sys.stderr)
        sys.exit(1)

    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # Create tables
    cur.executescript("""
        DROP TABLE IF EXISTS lessons;
        DROP TABLE IF EXISTS lessons_fts;

        CREATE TABLE lessons (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            domain TEXT,
            tags TEXT,
            timestamp TEXT,
            source_path TEXT,
            confidence TEXT,
            status TEXT
        );

        CREATE VIRTUAL TABLE lessons_fts USING fts5(
            title, description, tags, domain,
            content='lessons',
            content_rowid='rowid'
        );

        CREATE TRIGGER lessons_ai AFTER INSERT ON lessons BEGIN
            INSERT INTO lessons_fts(rowid, title, description, tags, domain)
            VALUES (new.rowid, new.title, new.description, new.tags, new.domain);
        END;

        CREATE TRIGGER lessons_ad AFTER DELETE ON lessons BEGIN
            INSERT INTO lessons_fts(lessons_fts, rowid, title, description, tags, domain)
            VALUES ('delete', old.rowid, old.title, old.description, old.tags, old.domain);
        END;
    """)

    # Load OKF records
    count = 0
    with open(okf_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            tags_str = ",".join(record.get("tags", []))
            cur.execute(
                "INSERT OR REPLACE INTO lessons (id, title, description, domain, tags, timestamp, source_path, confidence, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.get("id", ""),
                    record.get("title", ""),
                    record.get("description", ""),
                    record.get("domain", ""),
                    tags_str,
                    record.get("timestamp", ""),
                    record.get("source_path", ""),
                    record.get("confidence", ""),
                    record.get("status", ""),
                ),
            )
            count += 1

    conn.commit()
    conn.close()
    return count


def main():
    parser = argparse.ArgumentParser(description="Build SAG-Lite SQLite search index")
    parser.add_argument("--db", default="data/sag/search.db", help="SQLite database path")
    parser.add_argument("--okf", default=None, help="OKF JSONL file (default: data/okf/lessons.jsonl)")
    args = parser.parse_args()

    db_path = REPO_ROOT / args.db
    okf_file = Path(args.okf) if args.okf else OKF_FILE

    count = build_index(db_path, okf_file)
    print(f"Built SAG-Lite index: {count} lessons -> {db_path}")


if __name__ == "__main__":
    main()
