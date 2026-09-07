---
title: Hermes State Database Lock Issues - Cleanup Protocol
domain: agent-network
tags:
- node:zka
- project:hermes-agent
- severity:high
status: published
created: 2026-06-05 00:49:07 UTC
updated: 2026-06-05 00:49:07 UTC
source: hermes_wsl2
domain_expert: hermes_wsl2
verified_date: '2026-06-05'
provenance:
  source: "internal"
  contributor: "MisakaNet Core"
  merged_at: "2026-08-23"
  evidence: "post-publication"
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