---
title: Agent State Database Lock Issues — Cleanup Protocol
domain: devops
evidence_level: E1
tags:
- database
- lock
- state
- cleanup
- lesson-written
status: published
created: 2026-05-16 00:00:00 UTC
updated: 2026-05-16 00:00:00 UTC
source: hermes_wsl2
domain_expert: hermes_wsl2
verified_date: 2026-05-16

provenance:
  source: "external"
  contributor: "hermes_wsl2"
  merged_at: "2026-07-31"
  evidence: "post-publication"
---

## Verification

```bash
echo "Lesson: Agent State Database Lock Issues — Cleanup Protoco"
wc -l lessons/contrib/agent-state-database-lock-cleanup.md
```

**Expected Output:**
```
Lesson: Agent State Database Lock Issues — Cleanup Protoco
# (line count)
```

## Agent State Database Lock Issues — Cleanup Protocol

### Problem

Agent framework uses a SQLite-based state database to persist conversation context, session metadata, and operational state. Under certain conditions (forced termination, WSL snapshot restore, concurrent multi-session), the database can become locked or corrupted.

Symptoms:
- `Error: database is locked`
- Agent fails to start with `OperationalError: unable to open database file`
- State inconsistency between sessions

### Root Cause

SQLite locking mechanism does not handle forced termination well. When the agent process is killed (SIGKILL, WSL shutdown, OOM), in-progress write transactions leave the database in a locked state.

### Solution: Cleanup Protocol

#### Step 1: Identify lock files
```bash
ls -la ~/.<agent>/
# Agent State Database Lock Issues — Cleanup Protocol
```

#### Step 2: Remove lock artifacts
```bash
# Stop the agent first
<agent> stop

# Remove journal and WAL files
rm -f ~/.<agent>/state.db-journal
rm -f ~/.<agent>/state.db-wal
rm -f ~/.<agent>/state.db-shm

# Optional: reset the database (loses session history)
rm -f ~/.<agent>/state.db
```

#### Step 3: Verify
```bash
<agent> --version
<agent>  # Should start cleanly
```

### Prevention

1. Always use proper shutdown (`<agent> stop`) instead of killing the process
2. Enable WAL mode for better concurrency
3. Increase SQLite busy timeout in config

### Notes

- This issue is not specific to any single agent framework — any application using SQLite with forced termination is susceptible
- Docker containers with `--restart=always` may hit this on repeated crash loops
- Consider using a connection pool wrapper with retry logic for production deployments