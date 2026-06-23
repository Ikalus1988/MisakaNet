---
domain: "contrib"
title: "static page github api 403 rate limit"
verification: "metadata-normalized"
{"title": "静态页面调用外部 API 的容错设计原则", "domain": "frontend", "tags": ["api", "rate-limit", "static-site", "error-handling", "fault-tolerance"], "domain_expert": "unknown"}
---

## 背景

纯静态页面（无后端代理，HTML + JS 直接部署在 CDN/GitHub Pages 上）需要通过浏览器端 JavaScript 直接调用第三方 API。这种架构面临几个固有风险：

- **限流硬限制**：未认证请求通常有严格的速率限制（如 GitHub REST API 60 req/hour）
- **请求永久挂起**：没有超时控制的 fetch 在网络故障时永远不会 resolve
- **错误扩散**：一个接口的失败通过 try/catch 或 Promise 链传播，连带阻断其他无关功能
- **无中间层缓冲**：不能使用 API key、缓存代理或请求合并等后端手段

## 核心设计原则

### 1. 每个外部请求都必须有超时

浏览器 fetch 默认没有超时。一个慢请求可以永久挂起页面功能。

```js
async function fetchWithTimeout(url, timeoutMs = 8000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { signal: ctrl.signal });
    clearTimeout(timer);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  } catch (e) {
    clearTimeout(timer);
    throw e;
  }
}
```

### 2. 并行请求各自独立容错

使用 `Promise.all` 时，任何一个 promise reject 会导致整体失败。改为每个请求独立 catch：

```js
const [dataA, dataB] = await Promise.all([
  fetchWithTimeout(urlA).catch(() => null),
  fetchWithTimeout(urlB).catch(() => null),
]);
// dataA 失败不影响 dataB 的结果
```

### 3. 子功能永远独立执行

不要用一个大的 try/catch 包裹多个功能模块：

```js
// ❌ 错误：loadA 抛异常则 loadB、loadC 都不执行
try {
  await loadA();
  await loadB();
  await loadC();
} catch (e) { /* 只捕获一个，丢失两个 */ }

// ✅ 正确：各自独立执行
loadA().catch(() => {});
loadB().catch(() => {});
loadC().catch(() => {});
```

### 4. 用户友好的错误降级

不要把原始错误信息（`TypeError: Failed to fetch`、`HTTP 403`）直接展示给用户：

```js
// 区分常见的错误类型
if (e instanceof TypeError && e.message.includes('aborted')) {
  return '请求超时，请检查网络后重试';
}
if (e.message?.includes('403')) {
  return 'API 频率限制，请稍后刷新重试';
}
return '数据加载失败，已使用缓存显示';
```

## 验证标准

- 单个接口超时不影响其他接口的展示
- 触发限流时显示友好提示而非白屏或裸错误
- 所有功能模块各自独立加载、独立容错
- 网络恢复后刷新页面即可正常使用

## 反思

静态页面直接消费第三方 API 时，容错不是可选项而是**架构必选项**。因为没有后端中间层兜底，每个接口调用都直接暴露在浏览器环境下：

1. **任何外部请求都可能失败**——网络断开、限流、服务端故障，不是 if 而是 when
2. **不要用 try/catch 包裹多个逻辑块**——一个失败不应该连带其他功能一起失效
3. **非关键数据失败不应阻断关键数据展示**——统计数字和主要内容应该互不影响
4. **没有超时的 fetch 是永久挂起的隐患**——即使请求本地 JSON 文件也应有超时保护
5. **如果项目频繁遇到限流**，考虑引入 GitHub Actions 定时缓存 + 静态 JSON 的 hybrid 架构，或使用代理后端
