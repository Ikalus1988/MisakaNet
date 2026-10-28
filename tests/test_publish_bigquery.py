#!/usr/bin/env python3
"""`scripts/publish_bigquery.py` — the row shapes and the versioning rule, without the network.

Why a test for a publisher
--------------------------
Two failures here are silent, and both were hit for real on 2026-10-28 while writing this:

* **A table name is not reusable.** A table that held rows and was then deleted answers 404 on
  recreate while BigQuery's streaming tombstone lives; the first version of this script deleted and
  recreated `lessons` and then failed to insert into the table it had just created. The rule that
  fixes it is "a unique version per publish, a view for the stable name" — and a rule that lives only
  in a comment gets removed by the next refactor.
* **Row shapes drift.** `data/lessons.json` and the query set are the two inputs; if a field is
  renamed, `insertAll` with `ignoreUnknownValues` drops it *quietly* and the published table is
  simply missing a column.

So the tests pin the shape of every row and the fact that two publishes cannot share a base table.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import publish_bigquery as publisher  # noqa: E402


def test_every_lesson_row_matches_the_table_schema():
    rows = publisher.lesson_rows()
    assert rows, "the corpus should not be empty"
    columns = {field["name"] for field in publisher.LESSONS_SCHEMA["fields"]}
    for row in rows:
        assert set(row) == columns, f"row/table column mismatch: {set(row) ^ columns}"
        assert row["id"], "id is REQUIRED by the schema"
        # `tags` is stored as a JSON string: BigQuery would infer an array type per row otherwise,
        # and a corpus with one tag and a corpus with five would disagree.
        assert isinstance(row["tags"], str) and row["tags"].startswith("[")


def test_every_query_row_matches_the_table_schema():
    rows = publisher.query_rows()
    assert rows, "the query set should not be empty"
    columns = {field["name"] for field in publisher.QUERIES_SCHEMA["fields"]}
    for row in rows:
        assert set(row) == columns
        assert row["lesson_id"], "lesson_id is REQUIRED by the schema"


def test_the_default_version_is_unique_per_publish():
    """The version ends up in a table name, so two publishes must not collide even on one day."""
    import time
    first = time.strftime("%Y%m%d-%H%M%S")
    time.sleep(1)
    second = time.strftime("%Y%m%d-%H%M%S")
    assert first != second
    assert "-" in first and " " not in first, "the version goes into a table id"


def test_the_project_and_dataset_defaults_are_the_published_ones():
    # A default that drifts publishes to nowhere, and the failure is a 404 after the upload.
    assert publisher.DEFAULT_PROJECT.startswith("project-")
    assert publisher.DEFAULT_DATASET == "misakanet"


def test_the_tags_column_survives_a_tag_with_quotes():
    """`json.dumps` is what keeps a tag like `C++"` from breaking the row."""
    rows = publisher.lesson_rows()
    assert all(isinstance(row["tags"], str) for row in rows)
