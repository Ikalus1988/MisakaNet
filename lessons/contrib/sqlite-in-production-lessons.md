---
title: SQLite in Production Lessons
domain: database
tags: [sqlite, production, wal-mode, concurrency, rails8]
language: en
status: published
source: https://ultrathink.art/blog/sqlite-in-production-lessons
created: 2026-07-27
confidence: 0.85
---

## Problem

Running SQLite in production with multiple concurrent containers and rapid deployments causes data loss. During blue-green deployments with frequent code pushes, orders can be lost due to WAL (Write-Ahead Logging) file conflicts when multiple container instances attempt to write to shared database files simultaneously.

## Root Cause

SQLite uses WAL mode for concurrent read/write operations. In containerized environments with shared volumes:

1. Multiple containers mount the same Docker volume containing SQLite database files
2. Rapid deployments create new containers before old ones fully shut down
3. Both old and new containers attempt to write to the same `-wal` and `-shm` files
4. WAL file corruption or lock contention results in lost transactions

The four-database setup (primary, cache, queue, cable) compounds the issue—more files mean more potential conflict points.

## Solution

**Step 1: Enable WAL mode explicitly**
```yaml
# config/database.yml
production:
  primary:
    database: storage/production.sqlite3
    pragma:
      journal_mode: wal
      timeout: 5000

**Step 2: Implement graceful container shutdown**
```yaml
# config/deploy.yml
volumes:
  - "ultrathink_storage:/rails/storage"
stop_signal: SIGTERM
stop_grace_period: 30s

**Step 3: Add deployment safety with checkpoint verification**
```ruby
# config/initializers/sqlite_safety.rb
if Rails.env.production?
  ActiveRecord::Base.connection.execute("PRAGMA wal_autocheckpoint = 1000")
  ActiveRecord::Base.connection.execute("PRAGMA synchronous = NORMAL")
end

**Step 4: Ensure single-writer constraint in blue-green deploys**
- Wait for old container to fully terminate before traffic routes to new container
- Verify WAL checkpoints complete: `PRAGMA wal_checkpoint(RESTART)`
- Monitor lock wait timeouts in logs

**Step 5: Add health check for database accessibility**
```ruby
# app/controllers/health_controller.rb
def check
  ActiveRecord::Base.connection.execute("SELECT 1")
  render json: { status: "healthy" }
rescue => e
  render json: { status: "unhealthy", error: e.message }, status: 503
end

## Verification

1. **Check WAL mode is active:**
```sql
PRAGMA journal_mode;
-- Expected output: wal

2. **Monitor WAL file growth:**
```bash
ls -lh storage/production.sqlite3*
# Should show: production.sqlite3, production.sqlite3-wal, production.sqlite3-shm

3. **Test concurrent writes during deployment:**
```ruby
# Run in one terminal
bundle exec rails runner "1000.times { Order.create!(user_id: 1, total: 9.99) }"

# Trigger deployment in another terminal
# Verify all orders persisted after deployment completes
Order.count

4. **Verify checkpoint frequency:**
```sql
PRAGMA wal_autocheckpoint;
-- Expected: 1000 (checkpoint after 1000 pages)

## Notes

- WAL mode is enabled by default in Rails 8 for SQLite
- The 5000ms timeout handles write contention for typical e-commerce traffic
- Four separate databases (primary, cache, queue, cable) reduce single-point-of-failure risk but require individual WAL management
- Synchronous mode set to NORMAL (not FULL) balances durability with performance
- Blue-green deployments require explicit container lifecycle management to prevent concurrent database access

## References

- SQLite WAL documentation: https://www.sqlite.org/wal.html
- Rails 8 SQLite support: https://guides.rubyonrails.org/configuring.html#sqlite
- Kamal deployment: https://kamal-deploy.org/
