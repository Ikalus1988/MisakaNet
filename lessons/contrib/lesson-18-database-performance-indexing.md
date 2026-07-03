---
title: "数据库性能 — 索引与查询优化实践"
domain: "ops"
subdomain: "database"
tags: ["database", "postgresql", "indexing", "performance", "query-optimization"]
source: "practical-experience"
status: "published"
confidence: "0.9"
created: "2026-07-01"
verified_date: ""
domain_expert: ""
---


## Problem

慢查询是大多数 Web 应用的性能瓶颈。缺少索引、全表扫描、N+1 查询是最常见的原因。

## Root Cause

数据库查询没有使用索引，或索引设计不当。

## Solution

### 索引设计原则

```sql
-- 1. WHERE 条件列
CREATE INDEX idx_users_email ON users(email);
-- SELECT * FROM users WHERE email = 'x'; → Index Scan

-- 2. 复合索引（最左前缀）
CREATE INDEX idx_orders_user_date ON orders(user_id, created_at);
-- WHERE user_id = 1 → ✅ 使用索引
-- WHERE user_id = 1 AND created_at > '2026-01-01' → ✅ 使用索引
-- WHERE created_at > '2026-01-01' → ❌ 不使用索引

-- 3. 覆盖索引（避免回表）
CREATE INDEX idx_orders_covering ON orders(user_id, created_at) INCLUDE (total);
-- SELECT total FROM orders WHERE user_id = 1; → Index Only Scan

-- 4. 部分索引（节省空间）
CREATE INDEX idx_orders_pending ON orders(created_at) WHERE status = 'pending';
-- 只索引 pending 状态的订单
```

### 查询优化

```sql
-- ❌ N+1 查询
SELECT * FROM users;
-- 然后每个用户查询订单
SELECT * FROM orders WHERE user_id = ?;

-- ✅ JOIN 查询
SELECT u.*, o.* 
FROM users u 
LEFT JOIN orders o ON u.id = o.user_id;

-- ❌ SELECT *
SELECT * FROM users WHERE active = true;

-- ✅ 只选需要的列
SELECT id, name, email FROM users WHERE active = true;
```

### EXPLAIN ANALYZE

```sql
-- 分析查询计划
EXPLAIN ANALYZE 
SELECT * FROM orders WHERE user_id = 123 AND created_at > '2026-01-01';

-- 关注：
-- Seq Scan vs Index Scan
-- Rows Removed by Filter
-- Execution Time
```

### 常见反模式

| 反模式 | 问题 | 解决 |
|--------|------|------|
| `SELECT *` | 传输不需要的数据 | 只选需要的列 |
| `WHERE YEAR(date) = 2026` | 函数导致索引失效 | `WHERE date >= '2026-01-01'` |
| `OR` 条件 | 可能不走索引 | 改用 `UNION` |
| `LIKE '%keyword'` | 前缀通配符不走索引 | 全文搜索 |

## Verification

1. 运行 `EXPLAIN ANALYZE` 在慢查询上
2. 检查是否使用索引
3. 添加缺失的索引
4. 重新测量查询时间

## Notes

- 80% 的性能问题可以通过加索引解决
- 过度索引会降低写入性能
- Source: practical-experience + HN (353↑)
