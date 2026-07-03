---
title: "API 设计原则 — 无抽象、一致性、幂等性"
domain: "ops"
subdomain: "api"
tags: ["api", "design", "principles", "rest", "consistency"]
source: "increase.com/articles"
status: "published"
confidence: "0.85"
created: "2026-07-01"
verified_date: ""
domain_expert: ""
---


## Problem

API 设计不一致导致开发者困惑：有些端点用 POST 创建，有些用 PUT；有些返回 201，有些返回 200；有些用 camelCase，有些用 snake_case。

## Root Cause

没有统一的 API 设计原则。每个开发者按自己的习惯设计。

## Solution

### 核心原则

#### 1. 无抽象（No Abstractions）

```json
// ❌ 抽象层
POST /api/v1/actions
{
  "type": "create_user",
  "payload": { "name": "Alice" }
}

// ✅ 直接
POST /api/v1/users
{
  "name": "Alice"
}
```

#### 2. 一致性

```
所有资源使用相同模式：
  GET    /api/v1/{resource}       → 列表
  POST   /api/v1/{resource}       → 创建
  GET    /api/v1/{resource}/{id}  → 获取
  PATCH  /api/v1/{resource}/{id}  → 更新
  DELETE /api/v1/{resource}/{id}  → 删除
```

#### 3. 幂等性

```http
// POST 不幂等（每次调用创建新资源）
POST /api/v1/orders → 创建订单 #1
POST /api/v1/orders → 创建订单 #2

// PUT 幂等（多次调用结果相同）
PUT /api/v1/orders/1 → 更新订单 #1
PUT /api/v1/orders/1 → 更新订单 #1（不变）

// DELETE 幂等
DELETE /api/v1/orders/1 → 删除
DELETE /api/v1/orders/1 → 无操作（不报错）
```

#### 4. 错误格式

```json
// 统一错误格式
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Email is required",
    "details": [
      {
        "field": "email",
        "issue": "required"
      }
    ]
  }
}
```

#### 5. 分页

```json
// 统一分页格式
{
  "data": [...],
  "pagination": {
    "next_cursor": "abc123",
    "has_more": true
  }
}
```

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| URL 路径 | kebab-case | `/api/v1/user-profiles` |
| JSON 字段 | camelCase | `{"firstName": "Alice"}` |
| 查询参数 | snake_case | `?page_size=20` |
| HTTP 方法 | 大写 | `GET`, `POST`, `PATCH` |
| 状态码 | 标准 | `200`, `201`, `400`, `404` |

## Verification

1. 审查现有 API 是否一致
2. 检查所有 POST/PUT/DELETE 是否幂等
3. 检查错误格式是否统一
4. 检查命名是否符合规范

## Notes

- "No Abstractions" 原则来自 Increase（金融科技公司）
- 一致性比"正确性"更重要
- Source: increase.com/articles (2024-04-25, 345↑)
