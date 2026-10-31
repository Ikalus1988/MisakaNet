#!/usr/bin/env python3
"""The L2 search cache must survive concurrent readers.

`misakanet/search/engine.py` shares one `sqlite3.Connection` across threads (`check_same_thread=False`)
and serialises it with `_CACHE_LOCK`. The 2026-10-31 audit drove eight threads against the loader and
**seven died** with `DatabaseError: duplicate column name: language` — the schema migration racing
itself, with `except sqlite3.OperationalError` walking past the parent-class exception.

Two properties, both cheap to break and expensive to notice:
  * the loader is safe to call from several threads at once;
  * the migration asks the schema instead of provoking the exception.
"""
from __future__ import annotations

import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from misakanet.search import engine  # noqa: E402


def test_eight_threads_loading_at_once_all_succeed(monkeypatch, tmp_path):
    cache = tmp_path / "search_cache.db"
    monkeypatch.setattr(engine, "_CACHE_DB", cache)
    monkeypatch.setattr(engine, "_L2_CONN", None)

    def load(_):
        return len(engine._load_docs_cached(REPO / "lessons", is_lesson=True))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(load, range(8)))

    assert len(results) == 8
    assert all(isinstance(n, int) and n > 0 for n in results), results


def test_the_migration_does_not_raise_on_a_current_schema(monkeypatch, tmp_path):
    cache = tmp_path / "search_cache.db"
    monkeypatch.setattr(engine, "_CACHE_DB", cache)
    monkeypatch.setattr(engine, "_L2_CONN", None)
    engine._l2()  # creates the table with `language`
    assert isinstance(engine._l2(), sqlite3.Connection)  # second call re-runs the migration path


def test_the_migration_adds_the_column_to_an_old_schema(monkeypatch, tmp_path):
    cache = tmp_path / "old_cache.db"
    conn = sqlite3.connect(cache)
    conn.execute(
        "CREATE TABLE file_cache (path TEXT PRIMARY KEY, mtime REAL, size INT, title TEXT, "
        "domain TEXT, status TEXT, reference TEXT, scope TEXT, source TEXT, tags TEXT)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(engine, "_CACHE_DB", cache)
    monkeypatch.setattr(engine, "_L2_CONN", None)

    engine._l2()
    columns = {row[1] for row in engine._L2_CONN.execute("PRAGMA table_info(file_cache)")}
    assert "language" in columns
