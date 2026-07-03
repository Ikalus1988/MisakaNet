{"title": "<Database Domain Lesson Title>", "domain": "database", "subdomain": "<subdomain>", "tags": ["database", "postgresql", "mysql", "indexing", "query", "migration", "backup", "performance", "replication", "connection-pool"], "status": "draft", "confidence": "0.8", "created": "<YYYY-MM-DD>", "updated": "<YYYY-MM-DD>", "source": "<your-source>", "verified_date": "", "domain_expert": ""}

# <Database Domain Lesson Title>

## Problem

<!-- What database issue occurred? Symptoms: slow queries, connection errors, data corruption, replication lag, migration failures. -->

## Root Cause

<!-- Why did it happen? Common causes: missing index, N+1 queries, lock contention, connection pool exhaustion, schema drift, WAL bloat. -->

## Solution

### Diagnosis

```sql
-- Example: Find slow queries
SELECT query, calls, mean_exec_time, total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Example: Check index usage
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC;
```

### Fix

```sql
-- Example: Add missing index
CREATE INDEX CONCURRENTLY idx_<table>_<column> ON <table>(<column>);

-- Example: Fix N+1 query
-- Before: N queries
SELECT * FROM orders WHERE user_id = ?;
-- Then for each order:
SELECT * FROM items WHERE order_id = ?;

-- After: 1 query with JOIN
SELECT o.*, i.* FROM orders o
JOIN items i ON o.id = i.order_id
WHERE o.user_id = ?;
```

### Monitoring

```sql
-- Example: Check connection pool
SELECT count(*) as active, state
FROM pg_stat_activity
GROUP BY state;

-- Example: Check replication lag
SELECT client_addr, state, sent_lsn, replay_lsn,
       sent_lsn - replay_lsn AS lag_bytes
FROM pg_stat_replication;
```

## Verification

1. Run the diagnostic query before and after the fix
2. Measure query execution time (should be < 100ms for OLTP)
3. Check index hit ratio (should be > 99%)
4. Verify no new slow queries in pg_stat_statements

## Notes

<!-- Common pitfalls, related lessons, database-specific considerations (PostgreSQL vs MySQL vs SQLite). -->

---

### Database Domain Patterns

| Pattern | When to Use |
|---------|-------------|
| **Indexing** | Slow sequential scans, high `seq_scan` count |
| **Connection pooling** | Too many connections, `max_connections` errors |
| **Query optimization** | High `mean_exec_time`, N+1 queries |
| **Migration** | Schema changes, data transformations |
| **Backup/Restore** | Disaster recovery, point-in-time recovery |
| **Replication** | Read scaling, high availability |
| **Partitioning** | Large tables (>100GB), time-series data |

### Common Tools

| Tool | Purpose |
|------|---------|
| `EXPLAIN ANALYZE` | Query execution plan |
| `pg_stat_statements` | Query performance tracking |
| `pg_stat_user_indexes` | Index usage analysis |
| `pg_stat_activity` | Connection monitoring |
| `pgBadger` | Log analysis |
| `pgbench` | Benchmarking |
