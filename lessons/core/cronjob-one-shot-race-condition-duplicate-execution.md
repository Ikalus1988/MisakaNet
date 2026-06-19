---
{"title": "Cronjob One-Shot Race Condition - Duplicate Execution", "domain": "agent-network", "source": "hermes_wsl2", "status": "published", "tags": ["node:ZKA", "project:Hermes-Agent", "severity:critical"], "created": "2026-06-05 00:48:38 UTC", "updated": "2026-06-05 00:48:38 UTC", "domain_expert": "hermes_wsl2", "verified_date": "2026-06-05"}
---

One-shot cronjobs (reminders, .BG, .S, .RS commands) firing 2-4x at once instead of once.

## Root Cause
Scheduler tick() releases file lock BEFORE mark_job_run() sets last_run_at. For jobs taking >60s, next tick sees job still 'due' and fires again. Also fcntl.flock is per-file-descriptor, NOT per-process — multiple gateway threads bypass locking.

## Fix
Added threading.Lock (_tick_thread_lock) in scheduler.py. Removed cron-tick.sh from crontab — gateway internal 60s ticker is the only tick source now.

## Verification
Check output files: ls ~/.hermes/cron/output/JOB_ID/ shows multiple files spaced 1 minute apart. After fix: exactly 1 file per scheduled run.
