#!/usr/bin/env python3
"""Search gap logger — records zero-result queries for demand analysis.

Writes to data/search_gaps.jsonl. Privacy: no user identity, only
query text + timestamp + source tag.

Usage:
    from scripts.search_gap_logger import log_zero_result, get_gap_stats
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
GAPS_FILE = REPO_ROOT / "data" / "search_gaps.jsonl"

# Opt-out env var
_GAP_LOGGING_DISABLED = os.environ.get("MISAKA_DISABLE_GAP_LOGGING", "").lower() in ("1", "true", "yes")


def log_zero_result(query: str, source: str = "mcp") -> bool:
    """Log a zero-result search query.

    Returns True if logged, False if disabled or invalid.
    """
    if _GAP_LOGGING_DISABLED:
        return False

    query = (query or "").strip()
    if not query or len(query) > 500:
        return False

    entry = {
        "query": query,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
    }

    try:
        GAPS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(GAPS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def load_gaps() -> list[dict]:
    """Load all logged gap entries."""
    if not GAPS_FILE.exists():
        return []
    entries = []
    for line in GAPS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def get_gap_stats() -> dict:
    """Return summary stats for gap logging."""
    entries = load_gaps()
    if not entries:
        return {"total": 0, "unique_queries": 0, "sources": {}}

    sources: dict[str, int] = {}
    for e in entries:
        src = e.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1

    unique = len({normalize_query(e["query"]) for e in entries if e.get("query")})

    return {
        "total": len(entries),
        "unique_queries": unique,
        "sources": sources,
    }


def normalize_query(query: str) -> str:
    """Normalize query for clustering: lowercase, collapse whitespace, strip punctuation."""
    q = query.lower().strip()
    q = re.sub(r"[^\w\s]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Search gap logger")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("stats", help="Show gap logging stats")
    sub.add_parser("list", help="List recent gaps")

    args = parser.parse_args()

    if args.cmd == "stats":
        stats = get_gap_stats()
        print(f"Total gaps: {stats['total']}")
        print(f"Unique queries: {stats['unique_queries']}")
        print(f"Sources: {stats['sources']}")
    elif args.cmd == "list":
        for e in load_gaps()[-20:]:
            print(f"  [{e.get('source', '?')}] {e.get('query', '')}")
    else:
        parser.print_help()
