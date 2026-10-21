#!/usr/bin/env python3
"""The counters table the worker writes to must exist in the schema file (#1647).

The worker and `workers/d1/schema.sql` are edited in different files by different means
(one is deployed, the other is applied by a workflow), so nothing stops a column from
being used in code that the schema never declares — the failure would be a runtime SQL
error on the request path, discovered in production. This parses the schema and asserts
the columns the worker's SQL names are declared, so the two cannot drift silently.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCHEMA = REPO / "workers" / "d1" / "schema.sql"
WORKER = REPO / "workers" / "register-proxy-sw.js"

COUNTERS_COLUMNS = ("scope", "bucket", "period", "count", "updated_at")


def _counters_table_sql() -> str:
    sql = SCHEMA.read_text(encoding="utf-8")
    match = re.search(r"CREATE TABLE IF NOT EXISTS counters\s*\((.*?)\n\);", sql, re.DOTALL)
    assert match, "workers/d1/schema.sql must declare the counters table"
    return match.group(1)


def test_counters_table_is_declared_with_the_columns_the_worker_uses():
    body = _counters_table_sql()
    for column in COUNTERS_COLUMNS:
        assert re.search(rf"^\s*{column}\s", body, re.MULTILINE), (
            f"counters.{column} is used by the worker but not declared in the schema")


def test_counters_table_has_a_composite_primary_key():
    """Without (scope, bucket, period) as the key, the atomic upsert cannot work."""
    body = _counters_table_sql()
    assert re.search(r"PRIMARY KEY\s*\(\s*scope\s*,\s*bucket\s*,\s*period\s*\)", body), (
        "the counters upsert relies on PRIMARY KEY (scope, bucket, period)")


def test_the_query_index_exists_for_aggregation():
    sql = SCHEMA.read_text(encoding="utf-8")
    assert "idx_counters_scope_period" in sql, (
        "aggregations filter by scope+period; keep the index that serves them")


def test_the_worker_counter_sql_only_names_declared_columns():
    """Every column the worker's counter SQL mentions must be one the schema declares."""
    worker = WORKER.read_text(encoding="utf-8")
    counter_sql = "\n".join(re.findall(r'`[^`]*counters[^`]*`', worker))
    if not counter_sql.strip():
        return  # the migration is not wired into the worker yet (issue #1648)
    body = _counters_table_sql()
    for column in re.findall(r"\b(scope|bucket|period|count|updated_at)\b", counter_sql):
        assert re.search(rf"^\s*{column}\s", body, re.MULTILINE), (
            f"worker SQL names counters.{column}, which the schema does not declare")


def test_the_apply_workflow_is_dispatchable_and_does_not_deploy():
    workflow = (REPO / ".github" / "workflows" / "apply-d1-schema.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow, "the schema must be appliable on demand"
    assert "wrangler deploy" not in workflow, "applying a table must not redeploy the worker"
    assert "d1 execute" in workflow


# ── the gap cleanup's read (2026-10-21) ──────────────────────────────────────────────────────────
#
# The cleanup enumerates the `gap` scope **ordered by `updated_at`**, and the index above cannot
# serve that order: it is (scope, period), so the read visited every row of the scope and sorted
# it — measured on production 2,505 rows read and 41ms for a `LIMIT 500` that only needs the 500
# most recent. The index below is (scope, updated_at DESC) and covers the two columns the query
# selects, so the read stops at the LIMIT: **500 rows, 2.3ms** on the same database.
#
# The plan is asserted in a real SQLite engine rather than by reading the DDL, because the whole
# point of the index is what the *planner* does with it — a name in the file proves nothing.
def _statement_after(source: str, marker: str) -> str:
    """The SQL statement that starts at ``marker`` and ends at the next semicolon."""
    start = source.find(marker)
    assert start != -1, f"the file no longer contains {marker!r}"
    end = source.find(";", start)
    assert end != -1, f"the statement starting at {marker!r} has no semicolon"
    return source[start:end + 1].strip()


def _counters_db():
    """The counters table from the schema file, with the production gap scope filled in.

    Measured on production 2026-10-21: the `gap` scope held 2,410 rows.
    """
    import sqlite3

    schema = SCHEMA.read_text(encoding="utf-8")
    match = re.search(r"CREATE TABLE IF NOT EXISTS counters\s*\((.*?)\n\);", schema, re.DOTALL)
    assert match, "workers/d1/schema.sql must declare the counters table"
    db = sqlite3.connect(":memory:")
    db.executescript("CREATE TABLE IF NOT EXISTS counters (" + match.group(1) + "\n);")
    db.executemany(
        "INSERT INTO counters (scope, bucket, period, count, updated_at) VALUES (?,?,?,?,?)",
        [("gap", f"bucket-{i}", "2026-10-21", i, "2026-10-21 09:00:00") for i in range(2410)],
    )
    return db


def test_the_gap_cleanup_read_is_served_by_the_updated_at_index():
    schema = SCHEMA.read_text(encoding="utf-8")
    worker = WORKER.read_text(encoding="utf-8")
    db = _counters_db()
    db.executescript(_statement_after(
        schema, "CREATE INDEX IF NOT EXISTS idx_counters_scope_updated"))
    db.executescript(_statement_after(
        schema, "CREATE INDEX IF NOT EXISTS idx_counters_scope_period"))

    query = re.search(
        r"`SELECT bucket, period FROM counters WHERE scope = 'gap'[^`]+`", worker)
    assert query, "the worker no longer reads the gap scope the way this test expects"
    plan = "\n".join(
        str(row[-1]) for row in db.execute("EXPLAIN QUERY PLAN " + query.group(0).strip("`")))
    assert "idx_counters_scope_updated" in plan, (
        f"the gap cleanup must read the scope through the updated_at index:\n{plan}")
    assert "TEMP B-TREE" not in plan, (
        f"the read still sorts the whole scope instead of stopping at the LIMIT:\n{plan}")


def test_the_updated_at_index_is_declared_and_idempotent():
    """``counters`` is not created by the worker — the schema file is the only way it gets there.

    The file is applied to the live database by a workflow, so a statement that is not idempotent
    fails that run.
    """
    schema = SCHEMA.read_text(encoding="utf-8")
    ddl = _statement_after(schema, "CREATE INDEX IF NOT EXISTS idx_counters_scope_updated")
    assert re.search(r"ON\s+counters\s*\(\s*scope\s*,\s*updated_at\s+DESC", ddl), (
        f"the index must be ordered by updated_at, or the LIMIT cannot stop the read early: {ddl}")
    assert "IF NOT EXISTS" in ddl.upper(), (
        "the schema file is applied to the live database by a workflow; a statement that is not "
        "idempotent fails that run")


def test_every_schema_statement_stays_re_appliable():
    """The apply workflow runs the whole file against the live database, a second time included."""
    schema = SCHEMA.read_text(encoding="utf-8")
    offenders = [
        line for line in schema.splitlines()
        if re.search(r"^\s*CREATE\s+(TABLE|INDEX)\b", line, re.IGNORECASE)
        and "IF NOT EXISTS" not in line.upper()
    ]
    assert not offenders, f"these statements would fail on a second apply: {offenders}"


# ── kv_store: the registration keys that used to be KV-only (2026-09-17) ──────────────
#
# Same drift risk as `counters`, and the same reason to pin it: the worker is deployed by
# pushing it, the schema is applied by a workflow that is run by hand. A column the worker
# names but the schema never declares surfaces as a runtime SQL error on the *registration*
# path — which is precisely the path that was broken all day on 2026-09-17.
KV_STORE_COLUMNS = ("key", "value", "expires_at", "updated_at")


def _kv_store_table_sql() -> str:
    sql = SCHEMA.read_text(encoding="utf-8")
    match = re.search(r"CREATE TABLE IF NOT EXISTS kv_store\s*\((.*?)\n\);", sql, re.DOTALL)
    assert match, "workers/d1/schema.sql must declare the kv_store table"
    return match.group(1)


def test_kv_store_is_declared_with_the_columns_the_worker_uses():
    body = _kv_store_table_sql()
    for column in KV_STORE_COLUMNS:
        assert re.search(rf"^\s*{column}\s", body, re.MULTILINE), (
            f"kv_store.{column} is used by the worker but not declared in the schema")


def test_kv_store_primary_key_is_the_kv_key():
    """The upsert is ON CONFLICT(key): without that key D1 rejects the statement at runtime."""
    body = _kv_store_table_sql()
    assert re.search(r"\bkey\s+TEXT PRIMARY KEY", body, re.IGNORECASE), (
        "the kv_store upsert requires `key` to be the primary key")


def test_the_worker_kv_store_sql_only_names_declared_columns():
    worker = WORKER.read_text(encoding="utf-8")
    sql = "\n".join(re.findall(r"`[^`]*kv_store[^`]*`", worker))
    assert sql.strip(), "the worker must use kv_store (see storePut/storeGet)"
    body = _kv_store_table_sql()
    for column in re.findall(r"(?<![_\w])(key|value|expires_at|updated_at)(?![_\w])", sql):
        assert re.search(rf"^\s*{column}\s", body, re.MULTILINE), (
            f"worker SQL names kv_store.{column}, which the schema does not declare")


def test_the_worker_creates_kv_store_itself_so_a_deploy_alone_is_enough():
    """The schema workflow is manual; registration must not depend on someone running it."""
    worker = WORKER.read_text(encoding="utf-8")
    assert "ensureKvStoreTable" in worker, (
        "the worker must create kv_store on first use (ensureKvStoreTable), or a deployment "
        "whose schema was not re-applied would fail every registration")
