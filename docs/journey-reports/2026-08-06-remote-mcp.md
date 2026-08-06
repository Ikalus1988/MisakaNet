# Remote MCP Journey Report — 2026-08-06

## 测试环境
- 客户端: curl (HTTP client)
- 系统: Windows 10, git-bash
- Agent: Hermes Agent (hermes-agent)
- 时间: 2026-08-06 10:44 UTC+8

## 步骤与结果

### 1. 发现端点 ✅

- 入口: GitHub README → `https://misakanet.org/mcp`
- 结果: ✅ 端点可达，返回了清晰的错误信息
- 卡点: 无
- 备注: 文档中多处引用该 URL（README、mcp-remote.md），入口清晰

```
HTTP/1.1 405 Method Not Allowed
Content-Type: application/json
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, OPTIONS

{"error":"Method Not Allowed. Use POST for MCP Streamable HTTP transport."}
```

### 2. 理解认证 ❌ **阻塞级**

- 结果: ❌
- 卡点: **Token 获取方式完全没有文档化**
  - `docs/integrations/mcp-remote.md` 说需要 `Bearer YOUR_TOKEN`
  - 但没有说明 `YOUR_TOKEN` 从哪来
  - 没有 token 生成页面（`/token` 返回 404）
  - 没有注册/登录流程
  - Glama 页面也没有 token 获取入口
  - README 和 quickstart 文档都只展示本地 stdio 用法（不需要 token），remote 用法缺乏关键步骤

**严重性: 阻塞** — 用户无法完成远程 MCP 连接

### 3. 配置客户端 ⚠️

- 配置方式: curl / JSON config
- 结果: ⚠️ 配置格式文档正确，但无法实际使用
- 卡点:
  - Claude/Cursor/Glama 的 JSON 配置格式文档清晰
  - 但因为缺少 token，无法完成实际配置
  - 文档中给出的配置模板里 `YOUR_TOKEN` 占位符没有替换指引

**严重性: 阻塞（由步骤2引起）**

### 4. initialize ❌

- 请求:
```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"hermes-agent","version":"1.0"}}}
```
- 响应:
```json
{"jsonrpc":"2.0","error":{"code":-32000,"message":"Unauthorized"}}
```
- 结果: ❌ 需要有效的 Bearer token
- 卡点: 无有效 token
- 备注: 错误信息清晰，服务端正常运行，协议栈无问题

### 5. tools/list ❌

- 结果: ❌ 未测试（被认证阻塞）
- 预期: 返回 `misakanet_search` 和 `misakanet_get_lesson` 两个工具

### 6. tools/call (search) ❌

- 结果: ❌ 未测试（被认证阻塞）
- 预期: 搜索 failure lessons 并返回结果

## 卡点汇总

| 严重性 | 步骤 | 描述 | 建议修复 |
|--------|------|------|---------|
| **阻塞** | 2. 认证 | Token 获取方式完全缺失 — 文档说需要 Bearer token，但没有任何地方说明如何获取 | ① 在 `docs/integrations/mcp-remote.md` 中添加 Token 获取章节；② 提供 token 生成端点（如 `POST /mcp/token`）或注册页面；③ 在 Glama 页面上添加 "Get API Token" 按钮 |
| **体验差** | 3. 配置 | 配置模板中的 `YOUR_TOKEN` 占位符没有获取指引的链接 | 在配置示例旁添加 token 获取链接 |
| **建议改进** | 1. 发现 | Glama 页面是 Next.js SPA，纯 curl 无法获取有效内容 | 考虑在 README 中同时提供纯文本的 endpoint 信息 |

## 额外发现

### 正面
- ✅ CORS 已正确配置 (`Access-Control-Allow-Origin: *`)
- ✅ 错误信息友好且信息量足够（"Method Not Allowed. Use POST..."）
- ✅ Cloudflare 保护运行正常
- ✅ 本地 stdio 文档非常完善，本地使用体验良好
- ✅ 协议支持清晰（MCP 2025-06-18 + Streamable HTTP）

### 需要注意
- ⚠️ Remote endpoint 文档与 local stdio 文档混在一起，容易让用户混淆
- ⚠️ 文档中 remote 用法像是「附加功能」，而本地 stdio 是主要推荐方式 — 如果 remote 是正式功能，应该有独立的 onboarding 流程

## 总体评价

**Remote MCP endpoint 的核心功能（服务端）已就绪，但用户转化链路在「认证」这一步完全断裂。**

本地 stdio 体验优秀，文档详尽。Remote 体验在第一步认证就卡住了 — 用户看到 `YOUR_TOKEN` 但不知道去哪拿。这是一个"最后一公里"问题：服务做好了，文档写了，但没有给用户发钥匙。

### 建议优先修复
1. **P0**: Token 获取流程（生成端点 / 文档说明）
2. **P1**: 配置示例添加 token 获取链接
3. **P2**: 独立的 remote quickstart 文档，与 local stdio 分开

---

*此报告由 Hermes Agent 自动生成，作为 ClawHunt agent bounty hunter 的一部分。*
*相关: [#804](https://github.com/Ikalus1988/MisakaNet/issues/804) (MCP endpoint), [#818](https://github.com/Ikalus1988/MisakaNet/issues/818) (社媒引流)*
