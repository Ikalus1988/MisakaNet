{"title": "gRPC vs OpenAPI vs REST — API 协议选择指南", "domain": "ops", "subdomain": "api", "tags": ["grpc", "openapi", "rest", "api", "protocol", "architecture"], "source": "cloud.google.com/blog", "status": "published", "confidence": "0.9", "created": "2026-07-01", "verified_date": "", "domain_expert": ""}


## Problem

选择 API 协议时，REST、OpenAPI、gRPC 各有优劣，没有清晰的选择指南。

## Root Cause

三种协议解决不同问题，但文档往往只讲自己，不讲适用场景。

## Solution

### 协议对比

| 特性 | REST | OpenAPI | gRPC |
|------|------|---------|------|
| 协议 | HTTP/1.1 | HTTP/1.1+ | HTTP/2 |
| 格式 | JSON | JSON | Protobuf |
| 类型安全 | 无 | Schema | 强类型 |
| 性能 | 中 | 中 | 高（二进制） |
| 浏览器支持 | ✅ | ✅ | 需要 gRPC-Web |
| 代码生成 | 无 | 可选 | 自动生成 |
| 流式传输 | 不支持 | 不支持 | 支持 |

### 选择指南

```
需要浏览器直接调用？
  ├─ Yes → REST 或 OpenAPI
  └─ No → 需要高性能？
              ├─ Yes → gRPC
              └─ No → 需要强类型？
                        ├─ Yes → OpenAPI
                        └─ No → REST
```

### REST（最通用）

```http
GET /api/users/123 HTTP/1.1
Accept: application/json

{
  "id": 123,
  "name": "Alice",
  "email": "alice@example.com"
}
```

### OpenAPI（带 Schema）

```yaml
openapi: 3.0.0
paths:
  /users/{id}:
    get:
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: integer
      responses:
        200:
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/User'
```

### gRPC（高性能）

```protobuf
syntax = "proto3";

service UserService {
  rpc GetUser(GetUserRequest) returns (User);
  rpc ListUsers(ListUsersRequest) returns (stream User);
}

message User {
  int32 id = 1;
  string name = 2;
  string email = 3;
}
```

### 实际建议

| 场景 | 推荐 |
|------|------|
| 公共 API | REST + OpenAPI |
| 内部微服务 | gRPC |
| 实时流式 | gRPC |
| 浏览器应用 | REST |
| 移动应用 | gRPC |

## Verification

1. 对同一 API 分别用 REST、OpenAPI、gRPC 实现
2. 测量延迟和吞吐量
3. gRPC 应该快 2-5x
4. 测量开发效率（代码生成 vs 手写）

## Notes

- REST 最通用但性能最低
- gRPC 最快但浏览器支持需要额外层
- OpenAPI 是 REST 的 Schema 增强版
- Source: cloud.google.com/blog (2025-01-23, 323↑)
