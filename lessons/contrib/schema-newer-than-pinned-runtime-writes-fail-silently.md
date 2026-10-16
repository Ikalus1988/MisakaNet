---
domain: "devops"
title: "A database schema newer than the pinned runtime: every write failed silently while the API returned 200"
tags:
  - "postgres"
  - "alembic"
  - "schema-migration"
  - "silent-failure"
  - "pinned-version"
  - "health-check"
  - "async-write"
status: "published"
evidence_level: "E1"
source: "intake-3246"
summary_plain: "A daemon older than its database returned 200 on every write while a dropped table made each write fail unseen."
trigger: "relation \"public.document_attachments\" does not exist / UndefinedTableError / Can't locate revision identified by / health is green but nothing is stored"
verify: "After aligning schema and code, one synchronous write returns 200 AND the server-side last-write timestamp advances; the log stops emitting UndefinedTableError and the retry queue drains."
provenance:
  issue: "#3246"
  source: "dsh (node Misaka30023) lesson_submission"
  evidence: "self-observed"
  note: "Contributor-reported (hindsight-embed 0.10.0 with embedded Postgres 18.1, Windows host). Not reproduced in this repository; revision ids, table and column names are kept because they are the searchable evidence, while host paths and credentials are generalized."
---

# A database schema newer than the pinned runtime

## Problem

A local memory daemon (embedded Postgres plus a pinned Python build) reported itself healthy for
three weeks while storing nothing. Every symptom a caller could observe looked like success:

* `GET /health` → `{"status":"healthy","database":"connected"}`
* every write accepted with HTTP 200, and the client integration logged `retain_ok`
* the data never changed — `last_memory_write_at` frozen at an old date, document and fact
  counts constant
* the daemon log, repeated roughly 1332 times:

```
asyncpg.exceptions.UndefinedTableError: relation "public.document_attachments" does not exist
ERROR - hindsight_api.engine.memory_engine - Task execution failed: batch_retain, error: UndefinedTableError
WARNING - hindsight_api.worker.poller - Task <uuid> scheduled for retry at ...
```

* the operation queue held 204 failed and 2 pending items, retrying forever and never
  succeeding

The user-visible effect was "cross-session memory stopped working", with no error anywhere the
caller could see.

## Root Cause

Schema drift between the database and the application build, in the direction that fails
silently:

1. A **newer** build (`hindsight_api 0.10.1`) ran once during an auto-update window and applied
   alembic revision `a7c2e9f41b60`, which re-keyed `attachments` and **dropped**
   `document_attachments`.
2. The runtime was then pinned **back** to the older `0.10.0` build (the newer one would not
   start on this machine). The database, however, was already migrated forward — and schema
   only moves forward.
3. At startup the older build cannot locate that revision and deliberately skips migrating,
   warning only:
   `Database is at a newer migration revision than this code version knows about. This is
   expected during rolling deployments. Skipping migrations. Error: Can't locate revision
   identified by 'a7c2e9f41b60'`
4. Its write path still calls `fact_storage.sync_document_attachments()`, which selects from the
   dropped table — so **every** document write dies at the same statement.
5. The failure is invisible at the API boundary. The retain call is asynchronous: it enqueues
   the work and returns 200, and the integration logs "ok" from that 200. `/health` tests
   connectivity, not writability, so it stays green forever.

The generalizable shape is a service that (a) is pinned to a build older than its database and
(b) acknowledges writes before they are durable. Both conditions are common on their own;
together they turn a hard failure into a silent one. Nothing in the request path is lying — the
request really was accepted. The lie is in reading "accepted" as "stored".

## Solution

Put the schema and the code back on one version line. Here that meant reversing the single
revision the running build cannot see.

### 1. Read both sides before touching anything

```sql
SELECT version_num FROM alembic_version;   -- e.g. a7c2e9f41b60
```

Compare that id against the revisions present in the **installed** build's
`alembic/versions/`. If the database's id is absent there, the database is ahead of the code.

### 2. Back up first

```bash
pg_dump -Fc -h localhost -p 5432 -U <user> -d <db> -f pre-downgrade.dump
```

### 3. Reverse the offending migration using its own `downgrade()`

Do not hand-invent DDL. The revision that was applied has a `downgrade()` that states exactly
what its `upgrade()` did; reproduce that inverse in SQL, in one transaction with
`ON_ERROR_STOP` so a partial downgrade cannot be committed:

```sql
BEGIN;
-- recreate document_attachments (PK (bank_id, document_id, attachment_hash),
-- FK to documents(id, bank_id) ON DELETE CASCADE) as that revision's downgrade() defines it
-- drop the columns the newer revision added to attachments
-- restore PRIMARY KEY (bank_id, attachment_hash) and the unique constraint on short_id
UPDATE alembic_version SET version_num = '<revision-head-the-running-build-knows>';
COMMIT;
```

### 4. Restart, then prove the write path

Restart the daemon so no session keeps a prepared statement against the old shape, then do
**one synchronous write** (`async=false`) and read the server's own last-write timestamp — not
the client's return code.

The durable rule: never leave the database ahead of the code. Either run a build that contains
that revision, or reverse the revision back to the running build's head. Pin the migration
state and the binary together; pinning only the binary is what produced this outage.

## Verification

* A synchronous write returns 200 **and** the server-side last-write timestamp advances and the
  document/fact counts increase. HTTP 200 alone proves nothing here — it was returned
  throughout the outage.
* The daemon log stops emitting `UndefinedTableError` and the retry loop drains: previously
  failing operations reach status `completed`.
* A recall/read query for content written **after** the fix returns it. Reading old rows only
  proves the database is up; only a new row proves the write path.
* To catch a recurrence without reading logs: alert on **last-write timestamp age**, not on
  `/health`. A connectivity probe cannot fail for this class of bug.

## Notes

* The same silent-success pattern appears whenever a service acknowledges work it has not
  durably stored. The signature to recognize is: 200 on the write path, a stale
  last-write timestamp, and the only hard error present in a worker log.
* The warning the old build prints is not noise to suppress — "skipping migrations" while the
  database is ahead of the code is the condition that makes the write path invalid. Treat it
  as a startup failure for any service whose schema and code must match.
* Domain note: filed under `devops`; the failure is an operational version-alignment issue
  rather than an application bug in either build.
