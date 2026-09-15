---
title: "Alembic upgrade head fails: migration version mismatch and resolution"
domain: database
tags:
  - alembic
  - migration
  - sqlalchemy
  - postgresql
  - ci-cd
status: published
created: 2026-08-21
language: en
confidence: 0.9
verified_date: 2026-08-21
provenance:
  source: "intake"
  issue: "#1553"
  contributor: "Community"
  merged_at: "2026-08-21"
  evidence: "reproduction"
---

## Problem

Running `alembic upgrade head` fails with `subprocess.CalledProcessError`:

```
subprocess.CalledProcessError: Command '['alembic', 'upgrade', 'head']' returned non-zero exit status 1.
```

Common error variants:
- `sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) FATAL: database "xxx" does not exist`
- `alembic.util.exc.CommandError: Can't locate revision identified by 'abc123'`
- `sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedTable) relation "alembic_version" does not exist`

**Minimal reproduction:**
1. Pull latest `main` with new migrations
2. Run `alembic upgrade head`
3. Fails because local DB state diverges from migration chain

## Root Cause

Alembic tracks applied migrations in the `alembic_version` table. Divergence happens when:

1. **Local model drift**: Developer modifies models without generating migration, or manually edits migration files
2. **Branch migration conflict**: Two branches create migrations with same revision ID
3. **Partial apply**: Previous migration failed mid-execution, leaving `alembic_version` pointing to a non-existent revision
4. **Connection mismatch**: `alembic.ini` points to different DB than expected

The core issue: `alembic upgrade head` expects a linear chain from `current` → `head`. Any gap or orphan breaks the chain.

## Solution

**Diagnose first:**
```bash
# Check current state
alembic current
# Expected: revision ID matching latest migration

# Check history
alembic history --verbose
# Look for gaps or missing revisions

# Check head
alembic heads
# Should show single head (not multiple)
```

**Fix by scenario:**

**Scenario A: Missing revision**
```bash
# If alembic_current shows a revision not in history
alembic stamp head  # Mark current DB as up-to-date without running migrations
```

**Scenario B: Diverged branches**
```bash
# Merge migration branches
alembic merge -m "merge branch migrations" <rev1> <rev2>
alembic upgrade head
```

**Scenario C: Corrupted alembic_version**
```sql
-- Nuclear option: reset version tracking
DELETE FROM alembic_version;
-- Then stamp with known good revision
```

```bash
alembic stamp head
```

**Scenario D: Fresh start (dev only)**
```bash
dropdb mydb && createdb mydb
alembic upgrade head
```

## Prevention

1. **Always generate migration after model change:**
   ```bash
   alembic revision --autogenerate -m "description"
   alembic upgrade head  # Test immediately
   ```

2. **CI gate**: Add to CI pipeline:
   ```yaml
   - name: Check migrations
     run: |
       alembic upgrade head
       alembic downgrade base
       alembic upgrade head
   ```

3. **Never edit applied migrations**: Create new migration to fix, not modify existing

4. **Single head policy**: Check `alembic heads` returns exactly one head before merging PR

## Verification

```bash
# Should succeed cleanly
alembic upgrade head
# Expected: "Running upgrade abc123 -> def456"

# Verify state
alembic current
# Expected: (head) def456

# Verify schema matches models
alembic check
# Expected: "No new upgrade operations detected"
```

## References

- [Alembic Documentation: Working with Migrations](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [SQLAlchemy Migrations Best Practices](https://alembic.sqlalchemy.org/en/latest/bestpractices.html)
