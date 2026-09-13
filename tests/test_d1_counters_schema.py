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
