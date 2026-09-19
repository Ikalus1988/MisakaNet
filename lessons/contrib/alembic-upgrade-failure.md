---
title: "Alembic upgrade fails after dependency update"
domain: devops
tags: [alembic, database, migration, sqlalchemy, diagnosis]
status: published
created: '2026-09-15'
updated: '2026-09-16'
source: "intake #1553 — subprocess.CalledProcessError: alembic upgrade head returned non-zero exit status 255 (third-party repo s6pa1rta3n-lab/roof4u)"
evidence_level: E3
provenance:
  source: "intake"
  issue: "#1553"
---

## Problem

`alembic upgrade head` fails with various errors after updating mcp-memory-service or its dependencies. Common failure modes:

- `Can't locate revision identified by 'abc123'` — alembic_version table references a revision not in the current migration chain
- `Multiple head revisions` — two or more migration branches exist without a merge point
- `Table already exists` — migration was partially applied but alembic recorded it as complete

## Root Cause

The migration chain in `alembic/versions/` diverges from what's recorded in the database's `alembic_version` table. This happens when:

1. **Dependency update pulls new migrations** that assume a different chain history than what your database has
2. **SQLite limitations** — no transactional DDL means a failed migration leaves the schema half-applied but alembic may still stamp it
3. **Merge conflicts in migration files** — two contributors create migrations from the same parent, resulting in two heads

## Solution

Diagnose first, then pick the right fix:

```bash
# 1. See what alembic thinks the current state is
alembic current

# 2. See what migrations exist
alembic history

# 3. See what heads exist
alembic heads

# 4. If two heads, merge them
alembic merge -m "merge heads" head1 head2

# 5. If revision not found, stamp to a known-good state
alembic stamp head  # trust current schema is correct

# 6. If table exists error, check if table actually exists
sqlite3 memory.db ".tables" | grep <table_name>
# If it exists and schema is correct, stamp past that revision
```

## Verification

```bash
# 1. Verify current state matches expected
alembic current
# Should show a single head revision, not error

# 2. Verify no multiple heads
alembic heads
# Should show exactly one line

# 3. Run upgrade dry-run
alembic upgrade head --sql > /dev/null
# Should exit 0 with no errors

# 4. Run application tests
pytest tests/ -x -q
# Should pass — schema matches application expectations
```

## Prevention

- After dependency updates, always run `alembic current` before `alembic upgrade`
- Use `alembic check` (alembic ≥1.12) to verify chain consistency without applying
- For SQLite: back up `memory.db` before running migrations
- CI should run migrations against a fresh DB to catch chain divergence early