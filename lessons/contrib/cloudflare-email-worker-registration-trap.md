---{"title": "Cloudflare Email Worker 邮件注册踩坑Notes — message.raw、MIME 与 SPF", "domain": "devops", "tags": ["cloudflare", "email-worker", "kv", "turnstile", "registration", "spf"]}---

## 背景

为 MisakaNet 添加无 GitHub 账号的注册通道，选用 Cloudflare Email Routing + Workers + KV 架构。用户发邮件到注册地址 → Worker 自动分配节点 ID → 存入 KV。

## 方案

```
用户发邮件 → Cloudflare Email Routing → Worker email 事件
  → 分配节点 ID → 写入 KV → message.reply() 回复确认
```

## 踩坑记录

### 坑1：message.text 不存在

**现象：** Worker 部署后始终收不到邮件内容，`message.text` 为 undefined。

**根因：** Cloudflare Email Workers 的 `email` 事件处理函数没有 `text` 属性。邮件正文需要从 `message.raw`（ReadableStream）流式读取并解码。

**修复：**
```javascript
let rawText = '';
const reader = message.raw.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  rawText += decoder.decode(value, { stream: true });
}
```

### 坑2：Node.js crypto 模块不可用

**现象：** `import { randomBytes } from 'node:crypto'` 在 Workers 运行时抛出错误。

**根因：** Workers 不完全兼容 Node.js 的 `crypto` 模块。即使开启了 `nodejs_compat` 标志，`randomBytes` 仍可能失败。

**修复：** 改用 Web Crypto API。
```javascript
const array = new Uint8Array(16);
crypto.getRandomValues(array);
const token = Array.from(array, b => b.toString(16).padStart(2, '0')).join('');
```

### 坑3：回复邮件被 QQ/163/ Foxmail 拒收

**现象：** Worker 的 `message.reply()` 执行成功（无报错），但用户收不到验证邮件。

**根因：** Cloudflare 的邮件服务器 IP 不在主流国内邮箱的 SPF 白名单中，回复邮件被拒收或打入垃圾箱。这不是代码层面的错误，而是基础设施的信任问题。

**修复：** 去掉验证环节，改为"发邮件即注册"。用户发送邮件时 Worker 直接分配节点 ID 并写入 KV，回复邮件变为纯通知（收不到也不影响注册）。

### 坑4：Turnstile 与表单集成

**现象：** Web 表单添加 Turnstile 后，验证始终失败。

**根因：** Turnstile 需要 page URL 的白名单配置。开发阶段的 workers.dev 域名和生产域名需要同时在 Cloudflare Turnstile Dashboard 中添加。

**修复：** 在 Turnstile 管理界面添加所有可能的前端域名（包括 workers.dev 子域名）。

## 验证

1. 用户/AI Agent 发送邮件到注册地址
2. Worker 的 `email` 事件触发
3. `node_counter` 递增，`node:MisakaXXXXX` 写入 KV
4. 回复确认邮件（尽力交付）
5. Web 表单通过 Turnstile 防护 + KV 限频

```bash
# Cloudflare Email Worker 邮件注册踩坑Notes — message.raw、MIME 与 SPF
npx wrangler kv key list --binding MISAKANET_KV
# 应看到 node:MisakaXXXXX 和 node_counter
```

## Lesson Learned

- Cloudflare Email Workers 的 API 与标准 HTTP Workers 不同：无 `fetch` 事件中的 `request`，而是 `email` 事件中的 `message` 对象。`message.raw` 是唯一的正文获取方式。
- 邮件基础设施的可靠性不能假设。`message.reply()` 能否到达取决于收件方邮箱的 SPF 策略，不要把它作为关键路径。
- Workers 环境下优先使用 Web 标准 API（`crypto.getRandomValues`）而非 Node.js API。
- 双通道（邮件 + Web 表单）互补：Agent 用邮件自动化，人类用表单，同一套 KV 后端。
