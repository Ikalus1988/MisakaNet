"""No JOIN may carry an OR in its ON clause — no SQLite can index one.

This is the ratchet for the class of bug fixed twice, most recently on 2026-11-24:

    SELECT la.node_id … FROM search_signals ss JOIN lesson_authors la
      ON la.path = ss.top_id OR la.lesson_id = ss.top_id OR la.slug = ss.top_id
     GROUP BY la.node_id

Cloudflare's per-query D1 analytics put that one statement at **19,561,754,663 rows read in a month**
over 1,873 calls — ≈10.4M rows per call, 90% of every row the account read — because an `OR` across
three columns cannot be answered by an index, so the plan degenerates to
`lesson_authors × search_signals`. It returned correct answers, quickly, so nothing in the repository
could see it; the only witness was the bill.

Why a shape rule and not a plan test: measured the same day, the *same* rewritten SQL produced two
different plans on two SQLite versions (this machine drives from `search_signals`, CI drives from
`lesson_authors`) and both are linear. A gate keyed on `EXPLAIN QUERY PLAN` would flap between them,
while `ON … OR …` is quadratic on every version there is. The per-query replica tests
(`tests/test_d1_read_hotspots.py`, `workers/ladder-join-is-indexed.test.mjs`) stay the place where a
specific query's plan is proven.

What this does *not* catch: a join on an unindexed column with no OR in it. That needs the runtime
meter (`D1Meta.rows_read` at one seam) plus the nightly per-query report — see
`docs/maintainer/d1-cost.md`.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKER = REPO / "workers" / "register-proxy-sw.js"
OTHER_SQL_SOURCES = (
    REPO / "workers" / "register-proxy-entry.js",
    REPO / "scripts" / "sync_lessons_to_d1.py",
)

#: `JOIN x ON … OR …` up to the next clause keyword. Deliberately narrow: an `OR` in a `WHERE` is
#: normal and often the right answer; an `OR` inside `ON` is the shape that cannot be indexed.
JOIN_ON_OR = re.compile(r"\bJOIN\b[^;]{0,400}?\bON\b[^;]{0,400}?(?:\bOR\b|\bOR\s)", re.IGNORECASE)
CLAUSE_END = re.compile(r"\b(WHERE|GROUP\s+BY|ORDER\s+BY|LIMIT|HAVING)\b", re.IGNORECASE)


def _sql_strings(source: str) -> list[str]:
    """Every backtick- or double-quoted string in the file that looks like SQL."""
    candidates = re.findall(r"`([^`]{8,2000})`", source) + re.findall(r'"([^"]{8,2000})"', source)
    return [text for text in candidates
            if re.search(r"\b(SELECT|INSERT|UPDATE|DELETE|WITH)\b", text, re.IGNORECASE)]


def or_joins(source: str) -> list[str]:
    """The SQL strings whose JOIN … ON clause contains an OR."""
    found = []
    for text in _sql_strings(source):
        for match in re.finditer(r"\bJOIN\b", text, re.IGNORECASE):
            tail = text[match.end():]
            on = re.search(r"\bON\b", tail, re.IGNORECASE)
            if not on:
                continue
            condition = tail[on.end():]
            end = CLAUSE_END.search(condition)
            if end:
                condition = condition[:end.start()]
            if re.search(r"\bOR\b", condition, re.IGNORECASE):
                found.append(" ".join(text.split())[:180])
                break
    return found


def test_no_join_carries_an_or_in_its_on_clause():
    offenders = []
    for path in (WORKER,) + OTHER_SQL_SOURCES:
        if path.exists():
            offenders += [f"{path.name}: {sql}" for sql in or_joins(path.read_text(encoding="utf-8"))]
    assert not offenders, (
        "a JOIN's ON clause carries an OR — no index can serve it, and the plan becomes a cross "
        "product (19.56B rows in a month the last time this shipped; see the module docstring). "
        "Rewrite it as one join per column, unioned:\n  " + "\n  ".join(offenders))


def test_the_rule_bites_on_the_shape_that_shipped():
    """A gate nobody has seen fail is decoration: this is the text that read 19.56B rows."""
    shipped = (
        "SELECT la.node_id AS node_id, COUNT(*) AS n FROM search_signals ss "
        "JOIN lesson_authors la "
        "ON la.path = ss.top_id OR la.lesson_id = ss.top_id OR la.slug = ss.top_id "
        "GROUP BY la.node_id"
    )
    flagged = or_joins("`" + shipped + "`")
    assert flagged, "the detector must flag the join shape that actually shipped"
    assert "lesson_authors la" in flagged[0]


def test_an_or_in_a_where_clause_is_not_flagged():
    fine = ("`SELECT node_id FROM contributions WHERE created_at >= ?1 OR kind = 'question' "
            "ORDER BY id LIMIT 5`")
    assert or_joins(fine) == []


def test_the_rewritten_ladder_query_is_clean():
    """The fix that shipped: three joins, no OR in any ON clause, and it must stay that way."""
    source = WORKER.read_text(encoding="utf-8")
    start = source.find("function ladderUsedSql(")
    assert start != -1, "ladderUsedSql disappeared — did the ladder query move?"
    body = source[start:start + 1600]
    assert or_joins(body) == []
