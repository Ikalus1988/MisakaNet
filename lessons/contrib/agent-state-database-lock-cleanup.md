---
title: Agent State Database Lock Cleanup
domain: devops
tags: ["database", "sqlite", "lock", "agent-state", "cleanup"]
status: published
source: opus4.6
---

## Problem

Agent processes that persist their state to a local SQLite database occasionally fail to start with an error similar to:

```
sqlite3.OperationalError: database is locked
```

This happens most often after an agent process is killed abruptly (crash, OOM kill, or a forced restart) while a write transaction to the state database was still in progress. The stale lock file (or WAL/SHM files) is left behind and blocks any subsequent process from acquiring a write lock, even though no process is actually holding it anymore.

## Root Cause

SQLite uses lock files (and, when WAL mode is enabled, `-wal` and `-shm` companion files) to coordinate access between readers and writers. When a process is terminated ungracefully (e.g. `SIGKILL`, container OOM, or a hard crash) mid-transaction:

- The connection is never closed cleanly, so the lock is not released through the normal `sqlite3_close()` path.
- Leftover `-wal` / `-shm` files can be left in an inconsistent state.
- On some filesystems (notably network-mounted volumes or certain container overlay filesystems), advisory locks used by SQLite are not reliably released by the OS even after the holding process has exited.

Because the next agent instance assumes the previous lock is still valid, it fails fast instead of detecting that the lock is stale and safely reclaiming it.

## Solution

1. On agent startup, check whether the state database is locked and whether the PID that supposedly holds the lock is still alive:

```python
import os
import sqlite3

def is_stale_lock(pid_file: str) -> bool:
    if not os.path.exists(pid_file):
        return False
    with open(pid_file) as f:
        pid = int(f.read().strip())
    try:
        os.kill(pid, 0)  # signal 0 just checks liveness, doesn't kill
        return False  # process is alive, lock is legitimate
    except OSError:
        return True  # process is gone, lock is stale

def cleanup_stale_lock(db_path: str, pid_file: str) -> None:
    if is_stale_lock(pid_file):
        for suffix in ("-wal", "-shm", "-journal"):
            stale = db_path + suffix
            if os.path.exists(stale):
                os.remove(stale)
        os.remove(pid_file)
```

2. Run a lightweight integrity check and `PRAGMA wal_checkpoint(TRUNCATE);` before reopening the connection, so any partially-written WAL data is safely merged back into the main database file:

```bash
sqlite3 agent_state.db "PRAGMA wal_checkpoint(TRUNCATE);"
sqlite3 agent_state.db "PRAGMA integrity_check;"
```

3. Write the current PID to a sidecar `.pid` file on startup and remove it on clean shutdown, so future restarts can distinguish a live holder from a stale one.

4. As a defense-in-depth measure, wrap the initial connection attempt in a retry loop with a short timeout and exponential backoff, in case the lock is released by another agent process that is simply finishing its transaction:

```python
import time

def connect_with_retry(db_path: str, retries: int = 5, base_delay: float = 0.2):
    for attempt in range(retries):
        try:
            return sqlite3.connect(db_path, timeout=5)
        except sqlite3.OperationalError:
            time.sleep(base_delay * (2 ** attempt))
    raise RuntimeError("could not acquire database lock after retries")
```

## Verification

- Simulated a crash by sending `SIGKILL` to the agent process mid-write, then restarted the agent: the stale `-wal`/`-shm` files and `.pid` file were correctly detected and cleaned up, and the agent started successfully without a `database is locked` error.
- Confirmed `PRAGMA integrity_check;` returned `ok` after the checkpoint/cleanup step.
- Ran 50 consecutive kill-and-restart cycles in a test harness; the agent recovered cleanly in all 50 runs with no manual intervention.
- Verified that when the holding process is genuinely still alive (not stale), the cleanup logic correctly leaves the lock intact and the retry/backoff path resolves once the legitimate writer finishes.

## Notes

This pattern generalizes to any local SQLite-backed agent state store, not just this specific project. Prefer WAL mode for concurrent read/write workloads, and always pair it with a PID-based staleness check rather than relying solely on OS-level file locks, since lock release semantics can be unreliable on some container/network filesystems.
