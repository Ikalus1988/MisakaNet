---
{
  "title": "WSL NTFS SQLite UPDATE 100x slower than ext4",
  "domain": "data-engineering",
  "tags": [
    "wsl",
    "sqlite",
    "performance",
    "ntfs",
    "windows"
  ],
  "status": "published",
  "evidence_level": "E2",
  "created": "2026-08-06",
  "updated": "2026-08-06",
  "source": "b2-robot-utilization project",
  "verified_date": "2026-08-06",
  "triggers": {
    "intents": [
      "sqlite_batch_update",
      "wal_checkpoint",
      "large_database_migration"
    ],
    "commands": [
      "sqlite3",
      "drvfs",
      "mount /mnt/d",
      "python sqlite3"
    ],
    "environments": [
      "wsl",
      "wsl2",
      "ntfs",
      "windows"
    ],
    "risks": [
      "severe_i_o_bottleneck",
      "lock_timeout",
      "fsync_latency"
    ],
    "severity": "high"
  }
}
---

# WSL NTFS SQLite UPDATE 100x slower than ext4

## Problem

Running `UPDATE` on a 1.2GB SQLite database via WSL2's NTFS mount (`/mnt/d/`) takes 5+ minutes for a single statement updating ~9000 rows. The same operation on a Linux ext4 filesystem completes in ~3 seconds.

## Root Cause

WSL2 accesses Windows NTFS through the `drvfs` filesystem driver, which translates POSIX I/O calls to Windows NTFS operations. SQLite's WAL (Write-Ahead Log) mode requires frequent random writes to both the WAL file and the main database file. NTFS's random I/O performance through the WSL2 translation layer is extremely poor compared to native ext4, especially for workloads that mix small random writes with large sequential reads.

Key factors:
- SQLite WAL mode = heavy random write pattern
- WSL2 `drvfs` adds translation overhead per I/O syscall
- NTFS metadata updates (timestamps, allocation) add latency
- 1GB+ database = large page pool = more random I/O surface

## Solution

Copy the database to a Linux-native filesystem, perform the UPDATE there, then copy back.

### Step 1: Copy to Linux filesystem

```bash
cp /mnt/d/project/data.db /tmp/data.db
```

### Step 2: Run UPDATE on the local copy

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('/tmp/data.db')
conn.execute('UPDATE table SET col = ... WHERE ...')
conn.commit()
conn.close()
"
```

### Step 3: Copy back to NTFS

```bash
cp /tmp/data.db /mnt/d/project/data.db
```

## Verification

Time the operation before and after:

```bash
# Before (NTFS): ~300 seconds
time python3 -c "import sqlite3; c=sqlite3.connect('/mnt/d/data.db'); c.execute('UPDATE ...'); c.commit()"

# After (ext4): ~3 seconds
time python3 -c "import sqlite3; c=sqlite3.connect('/tmp/data.db'); c.execute('UPDATE ...'); c.commit()"
```

## Notes

- SELECT queries are not significantly affected — the read path has less random I/O overhead.
- For repeated UPDATE operations, consider keeping the working copy on `/tmp` and syncing back periodically.
- The `PRAGMA journal_mode=WAL` does not help on NTFS — the bottleneck is the filesystem layer, not SQLite's journaling.
- This also applies to `VACUUM`, `REINDEX`, and other write-heavy SQLite operations.
- Related: WSL2 with `wsl2.mountDisk` or custom `/etc/fstab` with `metadata` option does NOT fix this — the issue is fundamental to the drvfs translation layer.
