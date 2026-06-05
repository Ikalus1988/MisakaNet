---
{"title": "Hermes State Database Lock Issues - Cleanup Protocol", "domain": "agent-network", "source": "hermes_wsl2", "status": "published", "tags": ["node:ZKA", "project:Hermes-Agent", "severity:high"], "created": "2026-06-05 00:49:07 UTC", "updated": "2026-06-05 00:49:07 UTC"}
---

Hermes agent shows 'database is locked' error on SQLite state.db. Cronjobs stop firing.

## Root Cause
state.db uses SQLite with WAL mode. When gateway holds state.db open and process crashes, WAL file grows >50MB without checkpoint - causes lock timeouts. Also stale .journal and .lock files from incomplete transactions.

## Fix
1. Restart gateway: systemctl restart hermes-gateway.service
2. PRAGMA wal_checkpoint(TRUNCATE) after restart
3. Cleanup: delete .corrupted.* backups, empty sessions.db, empty *.lock files

## Verification
After fix: cronjob list shows jobs running, no lock errors in journalctl logs.
