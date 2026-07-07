---
title: Lobsters JSON API — Structured Tech Forum Scraping
domain: ops
subdomain: scraping
tags:
- lobsters
- api
- scraping
- json
- forum
- security
source: practical-experience
status: published
confidence: 0.9
created: '2026-07-02'
verified_date: ''
domain_expert: ''
---

## Problem

Lobste.rs 是高质量技术论坛（安全/Rust/系统），但没有搜索 API。需要通过 JSON 端点获取内容。

## Root Cause

Lobsters 提供 JSON 端点但没有搜索功能。只能获取热门/最新帖子，不能按关键词搜索。

## Solution

### JSON 端点

```python
import json, urllib.request

# 热门帖子
req = urllib.request.Request("https://lobste.rs/hottest.json", headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read())

# 最新帖子
req = urllib.request.Request("https://lobste.rs/newest.json", headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read())
```

### 数据结构

```json
{
  "score": 64,
  "title": "Building a passive Ethernet tap",
  "url": "https://blog.lvmbdv.dev/posts/building-a-passive-ethernet-tap/",
  "comment_count": 18,
  "tags": ["hardware", "networking", "security"],
  "created_at": "2026-07-01T10:00:00Z"
}
```

### 关键词过滤

```python
keywords = ["agent", "mcp", "claude", "memory", "devops", "automation", 
            "docker", "kubernetes", "ci", "security", "rust", "python"]

relevant = []
for p in data:
    title_lower = p["title"].lower()
    tags = [t.lower() for t in p.get("tags", [])]
    if any(kw in title_lower or kw in tags for kw in keywords):
        relevant.append(p)

for p in relevant[:10]:
    print(f"[{p['score']}↑ {p['comment_count']}💬] {p['title']}")
    print(f"  {p['url']}")
    print(f"  tags: {', '.join(p.get('tags', []))}")
```

### 端点对比

| 端点 | 内容 | 数量 |
|------|------|------|
| `/hottest.json` | 热门帖子 | ~25 |
| `/newest.json` | 最新帖子 | ~25 |
| `/recent.json` | 最近评论的帖子 | ~25 |

## Verification

1. `curl https://lobste.rs/hottest.json` 返回 JSON
2. 过滤关键词后有相关结果
3. 每条结果包含 score、title、url、tags

## Notes

- Lobsters 没有搜索 API，只能通过 JSON 端点获取列表
- 高质量内容集中在 security、rust、systems 标签
- Source: practical-experience
