#!/usr/bin/env python3
"""The E4 count must be answered by an index, not by a scan of the whole signal table (2026-10-21).

The last round cut the account's row reads by fixing the *shape* of a query (§118.5: a prefix
enumeration that scanned 68,892 rows). This one is an index rather than a query rewrite — which is
exactly the kind of change a string assertion cannot prove. A test that greps for an index name
only proves the name is there; it does not prove the planner uses it.

So this test runs the worker's **own DDL** and the worker's **own query** against a replica of the
production shape, in a real SQLite engine, and asserts the plan. A shape that stops being
indexable goes red here rather than on the bill.

Why the shape is *partial* and *covering*:

* A plain ``ON search_signals(client_hint)`` is planner-dependent — on SQLite 3.45 (the version
  the system Python here ships) the plan stays ``SCAN search_signals``, because
  ``client_hint <> ''`` is not an index-usable constraint; on 3.50+ the planner does use it. A
  shape that works on one SQLite and not on another is not a shape to ship.
* A **partial** index is not planner-dependent, and it is *covering* besides: with
  ``(client_hint, top_id)`` the ``top_id`` filter is answered from the index and the table is
  never touched. The partial predicate also keeps the index small — the table grows by one row per
  completed search, and only the rows that carry a hint belong in this index.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKER = REPO / "workers" / "register-proxy-sw.js"

# The E4 producer's binds: two exact candidates and the path form.
E4_BINDS = ("lesson-slug-0", "lessons/lesson-slug-0.md", "%/lesson-slug-0.md")


def _backtick_statement(source: str, marker: str) -> str:
    """The backtick-quoted SQL that starts at ``marker`` — the worker's own text, not a copy."""
    start = source.find(marker)
    assert start != -1, f"the worker no longer contains {marker!r}"
    end = source.find("`", start + len(marker))
    assert end != -1, f"the statement starting at {marker!r} is not backtick-quoted"
    return source[start:end].strip()


def _plan(db: sqlite3.Connection, sql: str, binds: tuple = ()) -> str:
    rows = db.execute("EXPLAIN QUERY PLAN " + sql, binds).fetchall()
    return "\n".join(str(row[-1]) for row in rows)


def _search_signals_db() -> sqlite3.Connection:
    """A replica of the production shape, built from the worker's own DDL.

    Measured on production 2026-10-21: 5,976 rows, 1,142 of them with a NULL ``top_id`` (the
    miss path), 365 distinct bare-slug ids, and **17** rows carrying a non-empty ``client_hint``
    (4 distinct hints). The 5,959 rows without a hint cannot contribute to
    ``COUNT(DISTINCT client_hint)`` — they are the rows the query rejects, and they were the rows
    the scan paid for: 5,842 rows read per call, 2,039,019 rows in 24 hours.
    """
    worker = WORKER.read_text(encoding="utf-8")
    db = sqlite3.connect(":memory:")
    db.executescript(_backtick_statement(worker, "CREATE TABLE IF NOT EXISTS search_signals"))
    for ddl in re.findall(r'"(ALTER TABLE search_signals ADD COLUMN [^"]+)"', worker):
        db.execute(ddl)

    hints = ["edf93b5f", "eeaba900", "abea0c8d", "8103f7bb"]
    slugs = [f"lesson-slug-{i}" for i in range(365)]
    rows = [(1, "q", None, None) for _ in range(1142)]
    rows += [(1, "q", slugs[i % 365], None) for i in range(4659)]
    rows += [(1, "q", slugs[i % 5], hints[i % 4]) for i in range(17)]
    db.executemany(
        "INSERT INTO search_signals (solved, query, top_id, client_hint) VALUES (?,?,?,?)", rows)
    return db


def _e4_query() -> str:
    """The worker's E4 query, with its one template interpolation resolved.

    The worker builds the ``top_id`` clause list at runtime (``${clauses.join(" OR ")}``); the
    resolved form is the one the production call actually sends — two exact candidates and the
    path form. If that interpolation changes, the substitution below stops matching and this
    test fails rather than silently planning a different query.
    """
    worker = WORKER.read_text(encoding="utf-8")
    query = _backtick_statement(worker, "SELECT COUNT(DISTINCT client_hint) AS clients")
    placeholder = '${clauses.join(" OR ")}'
    assert placeholder in query, (
        "the E4 query no longer interpolates its top_id clauses; update this test to the new shape")
    return query.replace(placeholder, "top_id = ? OR top_id = ? OR top_id LIKE ? ESCAPE '\\'")


def test_the_e4_count_is_answered_by_the_partial_covering_index():
    worker = WORKER.read_text(encoding="utf-8")
    index_ddl = _backtick_statement(worker, "CREATE INDEX IF NOT EXISTS idx_search_signals_hint_top")
    db = _search_signals_db()
    db.executescript(index_ddl)

    plan = _plan(db, _e4_query(), E4_BINDS)
    assert "SCAN search_signals" not in plan, (
        f"the E4 count scans the whole table again — the index is not being used:\n{plan}")
    assert "COVERING INDEX" in plan, (
        f"the E4 count must be answered from the index alone:\n{plan}")


def test_the_index_is_partial_so_it_only_holds_the_rows_that_can_carry_a_hint():
    """The ``WHERE`` clause is load-bearing: it is what makes the index *usable* for this query.

    A partial index is only chosen when the query's own WHERE implies the index's. Here the two
    are the same predicate, which is why the query is left exactly as it is — the clause that no
    index can serve (``top_id LIKE '%/<id>.md'``) stops mattering once the scan itself is bounded.
    """
    worker = WORKER.read_text(encoding="utf-8")
    index_ddl = _backtick_statement(worker, "CREATE INDEX IF NOT EXISTS idx_search_signals_hint_top")
    assert re.search(r"ON\s+search_signals\s*\(\s*client_hint\s*,\s*top_id\s*\)", index_ddl), (
        f"the index must cover (client_hint, top_id) so the table is never touched: {index_ddl}")
    assert re.search(
        r"WHERE\s+client_hint\s+IS\s+NOT\s+NULL\s+AND\s+client_hint\s*<>\s*''", index_ddl), (
        f"the index must be partial — a plain index is planner-dependent: {index_ddl}")


def test_a_non_covering_index_would_touch_the_table_for_every_matched_row():
    """Why the index covers ``top_id`` and not just ``client_hint``.

    An index over ``client_hint`` alone answers the query but leaves ``top_id`` to be fetched from
    the table, row by row. This assertion holds on every SQLite version — unlike "the planner
    picks this index at all", which changed between 3.45 (it did not) and 3.50+ (it does).
    """
    db = _search_signals_db()
    db.executescript(
        "CREATE INDEX idx_search_signals_client_hint ON search_signals(client_hint)")
    plan = _plan(db, _e4_query(), E4_BINDS)
    assert "COVERING INDEX" not in plan, (
        f"an index over client_hint alone now covers the query — the top_id column can be "
        f"dropped from the index, and this test should be updated rather than left to rot:\n{plan}")


def test_the_worker_creates_the_index_itself_so_a_deploy_alone_is_enough():
    """The schema workflow is run by hand; the search_signals table is not in it at all.

    The table reaches production through the worker's own runtime DDL
    (``ensureSearchSignalsTable``), so the index has to live there too — otherwise the fix would
    depend on somebody remembering to run a manual workflow.
    """
    worker = WORKER.read_text(encoding="utf-8")
    function_start = worker.find("async function ensureSearchSignalsTable(")
    assert function_start != -1, "the worker no longer creates search_signals at runtime"
    function_end = worker.find("\n}", function_start)
    function = worker[function_start:function_end]
    assert "idx_search_signals_hint_top" in function, (
        "the index must be created by ensureSearchSignalsTable, or a deploy alone will not create it")
