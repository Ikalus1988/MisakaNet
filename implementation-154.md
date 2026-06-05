# Implementation for #154

See issue #154 for details.

## 🎯 Objective

Add proper `asyncio.Lock` gating and a single persistent SQLite connection to `TelemetryPipeline`, replacing the per-batch open/close pattern that causes sporadic lock contentions under multi-node load.

## Background

Post-merge review of PR #147 (see #138) identified concurrency issues: `_sync_write()` and `_run_sliding_window_audit()` both open separate SQLite connections per call, causing `sqlite3` lock contentions under multi-node streaming emulation.

Discussion #152 explor