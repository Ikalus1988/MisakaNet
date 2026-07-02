{"title": "Redis → PostgreSQL 替换 — 缓存/PubSub/队列统一", "domain": "ops", "subdomain": "database", "tags": ["redis", "postgresql", "caching", "pubsub", "database", "performance"], "source": "dev.to", "status": "published", "confidence": "0.9", "created": "2026-07-01", "verified_date": "", "domain_expert": ""}


## Problem

典型 Web 应用同时用 PostgreSQL（持久化）+ Redis（缓存/PubSub/队列），两个数据库 = 两个备份点、两个监控、两个故障点。Redis 用 RAM（贵），持久化复杂。

## Root Cause

PostgreSQL 可以做 Redis 的所有事情，但很多人不知道或不信任。

## Solution

### 替换方案

| Redis 功能 | PostgreSQL 替代 | 性能 |
|-----------|----------------|------|
| 缓存 (70%) | `UNLOGGED TABLE` + `pg_cron` 过期 | 更快（无 WAL 开销） |
| PubSub (20%) | `LISTEN/NOTIFY` | 相当 |
| 队列 (10%) | `SKIP LOCKED` + 行级锁 | 更可靠 |

### 缓存实现

```sql
-- 创建非日志表（无 WAL，更快）
CREATE UNLOGGED TABLE cache (
    key TEXT PRIMARY KEY,
    value JSONB,
    expires_at TIMESTAMPTZ
);

-- 写入缓存
INSERT INTO cache (key, value, expires_at)
VALUES ('user:123', '{"name":"Alice"}', NOW() + INTERVAL '1 hour')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, expires_at = EXCLUDED.expires_at;

-- 读取缓存
SELECT value FROM cache WHERE key = 'user:123' AND expires_at > NOW();

-- 清理过期（pg_cron 定时执行）
DELETE FROM cache WHERE expires_at < NOW();
```

### PubSub 实现

```sql
-- 发布
NOTIFY notifications, '{"userId":123,"message":"hello"}';

-- 订阅（应用层）
LISTEN notifications;
```

### 队列实现

```sql
-- 创建任务表
CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    payload JSONB,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 消费任务（SKIP LOCKED 避免竞争）
BEGIN;
SELECT * FROM jobs WHERE status = 'pending'
ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED;
-- 处理任务...
UPDATE jobs SET status = 'done' WHERE id = :id;
COMMIT;
```

### 成本对比

| 项目 | Redis (ElastiCache) | PostgreSQL (RDS) |
|------|-------------------|-----------------|
| 2GB | $45/月 | 已含 |
| 5GB | $110/月 | $0.50/月 |
| 备份 | 需单独配置 | 已含 |
| 监控 | 需单独配置 | 已含 |

## Verification

1. 将 Redis 缓存迁移到 UNLOGGED TABLE
2. 将 PubSub 迁移到 LISTEN/NOTIFY
3. 将队列迁移到 SKIP LOCKED
4. 对比延迟和吞吐量

## Notes

- UNLOGGED TABLE 不写 WAL，崩溃后数据丢失（适合缓存场景）
- LISTEN/NOTIFY 不持久化消息（与 Redis PubSub 行为一致）
- SKIP LOCKED 是 PostgreSQL 9.5+ 特性
- Source: dev.to (2026-01-09, 335↑)
