{"title": "API 分页设计 — Cursor vs Offset vs Keyset", "domain": "ops", "subdomain": "api", "tags": ["api", "pagination", "cursor", "offset", "keyset", "design"], "source": "solovyov.net", "status": "published", "confidence": "0.9", "created": "2026-07-01", "verified_date": "", "domain_expert": ""}


## Problem

API 分页设计选择不当会导致性能问题（OFFSET 大偏移量慢）、数据重复/遗漏（并发写入时）、用户体验差。

## Root Cause

OFFSET 基于位置，数据变化时位置不稳定。CURSOR 基于标识符，数据变化时仍稳定。

## Solution

### 三种分页方式对比

| 方式 | 实现 | 性能 | 稳定性 | 适用场景 |
|------|------|------|--------|---------|
| OFFSET | `LIMIT n OFFSET m` | 大偏移量慢 | 差（并发写入时） | 简单列表 |
| CURSOR | 加密的标识符 | 恒定 | 好 | 通用 |
| KEYSET | 基于排序键 | 最快 | 最好 | 大数据量 |

### OFFSET（不推荐）

```sql
-- 问题：OFFSET 100000 需要扫描 100000 行
SELECT * FROM posts ORDER BY created_at DESC LIMIT 20 OFFSET 100000;
```

### CURSOR（推荐）

```python
# API 设计
GET /api/posts?cursor=eyJpZCI6MTIzLCJjcmVhdGVkX2F0IjoiMjAyNi0wMS0wMSJ9

# 实现
def get_posts(cursor=None, limit=20):
    if cursor:
        data = decode_cursor(cursor)  # {"id": 123, "created_at": "2026-01-01"}
        query = """
            SELECT * FROM posts 
            WHERE (created_at, id) < (%s, %s)
            ORDER BY created_at DESC, id DESC
            LIMIT %s
        """
        results = db.execute(query, [data['created_at'], data['id'], limit])
    else:
        query = "SELECT * FROM posts ORDER BY created_at DESC, id DESC LIMIT %s"
        results = db.execute(query, [limit])
    
    next_cursor = encode_cursor({
        'id': results[-1]['id'],
        'created_at': results[-1]['created_at']
    }) if len(results) == limit else None
    
    return {'data': results, 'next_cursor': next_cursor}
```

### KEYSET（最高效）

```sql
-- 不用 OFFSET，用排序键定位
SELECT * FROM posts 
WHERE created_at < '2026-01-01' AND id < 123
ORDER BY created_at DESC, id DESC
LIMIT 20;

-- 索引：(created_at DESC, id DESC)
-- 性能：恒定时间，与偏移量无关
```

### 响应格式

```json
{
  "data": [...],
  "pagination": {
    "next_cursor": "eyJpZCI6MTIz...",
    "has_more": true
  }
}
```

## Verification

1. 创建 1M 行表
2. 测试 OFFSET 100000 vs CURSOR 性能
3. CURSOR 应该快 100x+
4. 测试并发写入时的数据一致性

## Notes

- GitHub API 使用 CURSOR 分页
- Stripe API 使用 CURSOR 分页
- Source: solovyov.net (2020-12-27, 353↑)
