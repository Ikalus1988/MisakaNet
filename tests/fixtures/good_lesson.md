---
{
  "title": "Fix database locked error on concurrent writes",
  "domain": "devops",
  "tags": ["sqlite", "database", "locking", "concurrency"],
  "status": "published",
  "confidence": "0.85",
  "created": "2026-07-01",
  "updated": "2026-07-10",
  "source": "https://github.com/example/repo/issues/42",
  "language": "en"
}
---

## Problem

When multiple processes write to the same SQLite database simultaneously,
you get `database is locked` errors. This happens in CI pipelines where
parallel jobs share a state file.

Specific error message:

```text
sqlite3.OperationalError: database is locked
```

## Root Cause

SQLite uses file-level locking. When one writer holds a lock, all other
writers must wait. If they exceed the timeout (default 5s), they fail.

The issue is that WAL mode was not enabled, and busy_timeout was too low.

## Solution

1. Enable WAL mode for concurrent reads:

```sql
PRAGMA journal_mode=WAL;
```

2. Set busy timeout to 30 seconds:

```sql
PRAGMA busy_timeout=30000;
```

3. Add retry logic in application code:

```python
import time

def db_write_with_retry(conn, query, max_retries=3):
    for attempt in range(max_retries):
        try:
            conn.execute(query)
            conn.commit()
            return True
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise
    return False
```

## Verification

After applying WAL + busy_timeout:

```bash
# Run parallel writes
for i in $(seq 1 10); do
  python3 write_to_db.py &
done
wait
# Expected: no "database is locked" errors
```

Confirm WAL mode is active:

```sql
PRAGMA journal_mode;
-- Expected: wal
```

## Notes

- WAL mode only works on local filesystems, not NFS
- For distributed locking, consider PostgreSQL or a dedicated lock service
- See also: [SQLite WAL documentation](https://www.sqlite.org/wal.html)
