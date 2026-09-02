# Aider 代码评审报告

**日期**: 2026-08-28
**工具**: aider v0.86.2 (claude-sonnet-4-6)
**评审文件**: `workers/register-proxy-sw.js`

---

## P0 - 严重安全问题

### 1. Origin 验证绕过风险 (~230行)

```javascript
return MCP_ALLOWED_ORIGINS.some(allowed => 
  origin === allowed || origin.startsWith(allowed + ":"));
```

**问题**: `http://localhost` 前缀匹配可能被绕过（如 `http://localhost.evil.com:8080`）
**修复**: 使用精确匹配或 URL 解析

### 2. misakanet_write_lesson Token 验证绕过 (~570行)

```javascript
if (!tokenData || new Date(tokenData.expires) < new Date()) {
```

**问题**: 当 `env.MISAKANET_KV` 为 falsy 时，`nodeId` 为 null，但仍可执行写入
**修复**: 添加 KV 配置检查

---

## P1 - 高优先级问题

### 3. Request Clone 内存问题 (~475行)

```javascript
request.clone().json()
```

**问题**: 高并发下多次 clone 会消耗大量内存（超过 MAX_MCP_REQUEST_BYTES）
**修复**: 只 clone 一次，或使用流式解析

### 4. GitHub Issue 去重缺失 (~530行)

`misakanet_submit_intake` 生成的 `dedupHash` 未存储到 KV，同一内容可重复提交
**修复**: 添加 KV 去重检查

### 5. Protocol Version 检查顺序错误 (~510行)

协议版本在 body 解析之前验证，但 `protocolVersion` 来自 header，应在 body 之前
**修复**: 调整验证顺序

---

## P2 - 中等问题

### 6. BM25 缓存失效问题 (~290行)

```javascript
let _bm25Index = null;
let _bm25IndexExpiry = 0;
```

**问题**: 模块级缓存在不同 isolate 间不共享，可能失效
**修复**: 使用 KV 缓存或接受此限制

### 7. 空 catch 块 (~370行)

```javascript
} catch {}
```

**问题**: 吞掉错误，无法调试
**修复**: 添加日志记录

### 8. SSE Keepalive Interval 泄漏 (~900行)

```javascript
const interval = setInterval(() => { ... }, 30000);
```

**问题**: stream 关闭时 interval 未清理
**修复**: 添加 cleanup 逻辑

### 9. KV Key 污染风险 (~820行)

```javascript
const reasonKey = String(message).slice(0, 64);
```

**问题**: 用户消息直接作为 KV key，可能导致 `__proto__` 等污染
**修复**: 添加 key 清理函数

---

## 建议修复优先级

| 优先级 | 问题 | 修复复杂度 |
|--------|------|------------|
| P0 | Origin 验证绕过 | 低 |
| P0 | Token 验证绕过 | 低 |
| P1 | Request Clone 内存 | 中 |
| P1 | Issue 去重 | 中 |
| P1 | Protocol Version 顺序 | 低 |
| P2 | BM25 缓存 | 低 |
| P2 | 空 catch 块 | 低 |
| P2 | SSE Interval 泄漏 | 中 |
| P2 | KV Key 污染 | 低 |

---

## Aider 建议的修复代码

### KV Key 清理函数

```javascript
const SAFE_REASON_KEY_RE = /[^a-zA-Z0-9_\-一-龥 ]/g;
function sanitizeReasonKey(text, maxLen = 64) {
  return String(text).replace(SAFE_REASON_KEY_RE, '_').slice(0, maxLen);
}
```

### 使用位置

```javascript
// 原代码
const reasonKey = String(message).slice(0, 64);

// 修复后
const reasonKey = sanitizeReasonKey(message);
```

---

*评审工具: aider v0.86.2*
*模型: claude-sonnet-4-6*
