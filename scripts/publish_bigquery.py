#!/usr/bin/env python3
"""Publish the corpus and the benchmark query set to BigQuery, as a public dataset.

Why this exists (2026-10-28)
----------------------------
`data.misakanet.org` (R2) answers "give me the files". It does not answer "how many lessons are
about `fanuc`", or "join the query set to the corpus and show me the cross-lingual pairs" — for that
someone has to download 2.6 MB and write code. BigQuery is the other half of a published dataset:
**queryable without a download**, and discoverable by people who look in BigQuery rather than in
GitHub.

It is also the one Google recommendation from this round that costs nothing to keep: 10 GiB of
storage and 1 TiB of queries per month are free, and the corpus is 2.6 MB.

The dataset's access list gets `allAuthenticatedUsers: READER`, which is what "public dataset" means
in BigQuery — any Google account can query it, nobody can write to it.

Idempotent: re-running upserts the dataset and re-inserts rows (streaming inserts, so a second run
duplicates rows — the script clears the tables first by recreating them).

Usage
-----
    python3 scripts/publish_bigquery.py                    # publish
    python3 scripts/publish_bigquery.py --check            # print what would be loaded, call nothing
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_PROJECT = "project-2d6795e4-704d-4a4e-841"
DEFAULT_DATASET = "misakanet"
BASE = "https://bigquery.googleapis.com/bigquery/v2"

LESSONS_SCHEMA = {"fields": [
    {"name": "id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "title", "type": "STRING"},
    {"name": "domain", "type": "STRING"},
    {"name": "evidence_level", "type": "STRING"},
    {"name": "tags", "type": "STRING"},
    {"name": "url", "type": "STRING"},
    {"name": "summary", "type": "STRING"},
]}
QUERIES_SCHEMA = {"fields": [
    {"name": "lesson_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "target_url", "type": "STRING"},
    {"name": "query", "type": "STRING"},
    {"name": "lang", "type": "STRING"},
    {"name": "domain", "type": "STRING"},
    {"name": "overlap_bucket", "type": "STRING"},
]}


def access_token(gcloud: str) -> str:
    out = subprocess.run([gcloud, "auth", "print-access-token"], capture_output=True, text=True)
    token = (out.stdout or "").strip().splitlines()[-1] if out.stdout.strip() else ""
    if not token:
        raise SystemExit(f"error: no access token from {gcloud}: {out.stderr[:200]}")
    return token


def call(token: str, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(f"{BASE}{path}", data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                raw = response.read()
                return response.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return exc.code, json.loads(raw)
            except ValueError:
                return exc.code, {"raw": raw[:300].decode("utf-8", "replace")}
        except (urllib.error.URLError, OSError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    return 0, {}


def lesson_rows() -> list[dict]:
    lessons = json.loads((REPO / "data/lessons.json").read_text(encoding="utf-8"))
    return [{
        "id": lesson["id"], "title": lesson.get("title", ""), "domain": lesson.get("domain", ""),
        "evidence_level": lesson.get("evidence_level", ""),
        "tags": json.dumps(lesson.get("tags", []), ensure_ascii=False),
        "url": lesson.get("url", ""), "summary": (lesson.get("summary") or "")[:4000],
    } for lesson in lessons]


def query_rows() -> list[dict]:
    path = REPO / "docs/benchmarks/retrieval-l1-267-queries.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    keys = ("lesson_id", "target_url", "query", "lang", "domain", "overlap_bucket")
    return [{k: r.get(k, "") for k in keys} for r in rows]


def publish(token: str, project: str, dataset: str, version: str, batch: int = 200) -> dict:
    summary: dict[str, object] = {}
    status, body = call(token, "POST", f"/projects/{project}/datasets", {
        "datasetReference": {"projectId": project, "datasetId": dataset},
        "location": "US",
        "description": "MisakaNet failure-lesson corpus and retrieval benchmarks "
                       "(corpus Apache-2.0, benchmark artifacts CC0-1.0)",
    })
    if status not in (200, 409):
        raise SystemExit(f"error: dataset create failed ({status}): {json.dumps(body)[:300]}")

    for table, schema, rows in (("lessons", LESSONS_SCHEMA, lesson_rows()),
                                ("benchmark_queries", QUERIES_SCHEMA, query_rows())):
        base = f"{table}_v{version}"
        # Versioned base table + a view under the stable name. Three reasons, all measured:
        #   * a table name that has ever held rows and was then deleted cannot be recreated
        #     immediately — BigQuery answers 404 "table not found" on the recreate for as long as the
        #     streaming buffer's tombstone lives (~90 min). So the version is unique per publish and
        #     no name is ever reused;
        #   * re-inserting into a table that was just deleted answers 404 "table not found" for a
        #     while — BigQuery keeps the streaming buffer tied to the old incarnation, so
        #     delete-and-recreate under the same name is a trap;
        #   * a view can be repointed in one statement, so a publish is atomic for readers instead
        #     of a window where the table is empty.
        # This is the same shape as the R2 bundle: an immutable version, a mutable pointer.
        call(token, "DELETE", f"/projects/{project}/datasets/{dataset}/tables/{base}")
        status, body = call(token, "POST", f"/projects/{project}/datasets/{dataset}/tables", {
            "tableReference": {"projectId": project, "datasetId": dataset, "tableId": base},
            "schema": schema})
        if status != 200:
            raise SystemExit(f"error: table {base} create failed ({status}): {json.dumps(body)[:300]}")
        for _ in range(10):
            status, _ = call(token, "GET", f"/projects/{project}/datasets/{dataset}/tables/{base}")
            if status == 200:
                break
            time.sleep(1)
        sent = 0
        for i in range(0, len(rows), batch):
            chunk = rows[i:i + batch]
            status, body = call(
                token, "POST",
                f"/projects/{project}/datasets/{dataset}/tables/{base}/insertAll",
                {"rows": [{"json": r} for r in chunk], "ignoreUnknownValues": True})
            if status != 200 or body.get("insertErrors"):
                raise SystemExit(f"error: insert into {base} failed ({status}): {json.dumps(body)[:300]}")
            sent += len(chunk)
        # Point the stable name at the new version. A TABLE with the stable name would block the
        # view, so it is dropped first; readers see either the old view or the new one.
        call(token, "DELETE", f"/projects/{project}/datasets/{dataset}/tables/{table}")
        status, body = call(token, "POST", f"/projects/{project}/queries", {
            "query": f"CREATE OR REPLACE VIEW `{project}.{dataset}.{table}` AS "
                     f"SELECT * FROM `{project}.{dataset}.{base}`",
            "useLegacySql": False})
        if status != 200:
            raise SystemExit(f"error: view {table} create failed ({status}): {json.dumps(body)[:300]}")
        for _ in range(20):
            status, body = call(token, "POST", f"/projects/{project}/queries", {
                "query": f"SELECT COUNT(*) AS c FROM `{project}.{dataset}.{table}`", "useLegacySql": False})
            if status == 200 and body.get("rows"):
                break
            time.sleep(1)
        summary[table] = sent
        summary[f"{table}_view_rows"] = int(body["rows"][0]["f"][0]["v"]) if body.get("rows") else None

    status, current = call(token, "GET", f"/projects/{project}/datasets/{dataset}")
    access = current.get("access", [])
    if not any(a.get("specialGroup") == "allAuthenticatedUsers" for a in access):
        access.append({"specialGroup": "allAuthenticatedUsers", "role": "READER"})
        status, body = call(token, "PATCH",
                            f"/projects/{project}/datasets/{dataset}?updateMask=access", {"access": access})
        if status != 200:
            raise SystemExit(f"error: making the dataset public failed ({status}): {json.dumps(body)[:300]}")
        summary["made_public"] = True
    else:
        summary["made_public"] = False
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", default=DEFAULT_PROJECT)
    ap.add_argument("--dataset", default=DEFAULT_DATASET)
    ap.add_argument("--gcloud", default=str(REPO / ".cache/google-cloud-sdk/bin/gcloud"))
    ap.add_argument("--batch", type=int, default=200)
    ap.add_argument("--version", default=time.strftime("%Y%m%d-%H%M%S"))
    ap.add_argument("--check", action="store_true", help="print the row counts, call nothing")
    args = ap.parse_args(argv)

    if args.check:
        print(f"lessons: {len(lesson_rows())}  benchmark_queries: {len(query_rows())}")
        return 0

    summary = publish(access_token(args.gcloud), args.project, args.dataset, args.version, args.batch)
    print(json.dumps(summary, indent=1))
    print(f"query it: bq query --use_legacy_sql=false "
          f"'SELECT domain, COUNT(*) c FROM `{args.project}.{args.dataset}.lessons` GROUP BY domain "
          f"ORDER BY c DESC LIMIT 5'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
