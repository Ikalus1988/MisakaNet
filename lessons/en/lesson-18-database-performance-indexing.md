---
title: "Database Performance — Indexing and Query Optimization"
domain: "ops"
subdomain: "database"
tags: ["database", "postgresql", "indexing", "performance", "query-optimization"]
source: "practical-experience"
status: "published"
confidence: "0.9"
created: "2026-07-01"
lang: en
---

## Problem

Slow queries are the performance bottleneck for most web applications. Missing indexes, full table scans, and N+1 queries are the most common causes.

## Root Cause

Database queries are not using indexes, or indexes are poorly designed.

## Solution

### Index Design Principles

```sql
-- 1. WHERE clause columns
CREATE INDEX idx_users_email ON users(email);
-- SELECT * FROM users WHERE email = 'x'; → Index Scan

-- 2. Composite index (leftmost prefix)
CREATE INDEX idx_orders_user_date ON orders(user_id, created_at);
-- WHERE user_id = 1 → ✅ uses index
-- WHERE user_id = 1 AND created_at > '2026-01-01' → ✅ uses index
-- WHERE created_at > '2026-01-01' → ❌ does not use index

-- 3. Covering index (avoids table lookup)
CREATE INDEX idx_orders_covering ON orders(user_id, created_at) INCLUDE (total);
-- SELECT total FROM orders WHERE user_id = 1; → Index Only Scan

-- 4. Partial index (saves space)
CREATE INDEX idx_orders_pending ON orders(created_at) WHERE status = 'pending';
-- Only indexes orders with pending status
```

### Query Optimization

```sql
-- ❌ N+1 query
SELECT * FROM orders;
-- Then for each order:
SELECT * FROM users WHERE id = order.user_id;

-- ✅ JOIN
SELECT o.*, u.name FROM orders o JOIN users u ON o.user_id = u.id;

-- ❌ SELECT *
SELECT * FROM large_table WHERE ...;

-- ✅ SELECT specific columns
SELECT id, name, email FROM large_table WHERE ...;
```

### EXPLAIN Analysis

```sql
EXPLAIN ANALYZE SELECT * FROM orders WHERE user_id = 1;
-- Look for: Seq Scan (bad) vs Index Scan (good)
-- Look for: actual time, rows examined
```

## Verification

1. Run `EXPLAIN ANALYZE` on slow queries
2. Check if indexes are being used (Index Scan vs Seq Scan)
3. Monitor `pg_stat_user_indexes` for unused indexes
4. Use `pg_stat_statements` to find slow queries

## Notes

- Don't over-index: each index slows down writes
- Composite index order matters (leftmost prefix rule)
- Partial indexes save space for filtered queries
- Covering indexes avoid table lookups (Index Only Scan)

## Source

Translated from Chinese lesson by zsxh1990.
