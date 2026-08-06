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

## 补充测试：本地 MCP (stdio) ✅

由于远程端点被认证阻塞，我们转而测试本地 stdio 传输作为对照，验证 MCP 协议栈本身是否正常。

### 本地测试步骤

| 步骤 | 结果 | 详情 |
|------|------|------|
| 4. initialize | ✅ | `serverInfo: {name: misakanet, version: 2.15.0}` |
| 5. tools/list | ✅ | 返回 **4 个工具**（文档声称 2 个） |
| 6. tools/call (search) | ✅ | BM25 搜索正常，查询 "database locked" 返回 3 条结果 |
| 6. tools/call (get_lesson) | ✅ | 按 ID 获取 lesson 内容正常 |

### 工具列表（实际）

| 工具 | 描述 |
|------|------|
| `misakanet_search` | 搜索 failure lessons |
| `misakanet_get_lesson` | 按 path/id 获取单条 lesson |
| `misakanet_submit_usage` | [实验性] 提交 lesson 使用反馈 |
| `misakanet_usage_status` | 查看配额/用量状态 |

**📝 文档错误**: `docs/integrations/mcp-remote.md` 的 "Available Tools" 表格只列出了 2 个工具，实际有 4 个。

## 补充测试：Token 获取流程

### 注册流程实测

1. 访问 https://misakanet.org → 找到注册表单
2. 通过 API 注册: `POST https://misakanet.org/api/register/` → ✅ 创建了 GitHub issue #849
3. CI workflow `register.yml` 应该处理注册并发放 token

### ⚠️ **CI 注册 Workflow 崩溃**（新发现）

```
Run #31072372370 — 2026-08-06T04:50:32Z — FAILURE
Root cause:
  python3: can't open file 'misakanet-avatar.py': [Errno 2] No such file or directory
```

CI 在生成头像步骤失败，因为 `misakanet-avatar.py` 文件在仓库中不存在。这导致：
- ❌ 节点 ID 分配后无法推送 counter.json
- ❌ 头像无法生成
- ❌ Welcome 评论（含 token）永远不会发布

**这解释了为什么认证步骤是阻塞级** — 不仅文档缺失，注册 CI 本身也坏了。

### 建议修复（P0 新增）
在 `.github/workflows/register.yml` 中：
- 修复或移除 `misakanet-avatar.py` 调用（该文件可能在重构中被删除/重命名）
- 或者如果不再需要头像生成步骤，改为生成占位头像或跳过

---

## 额外发现

### 正面
- ✅ CORS 已正确配置 (`Access-Control-Allow-Origin: *`)
- ✅ 错误信息友好且信息量足够（"Method Not Allowed. Use POST..."）
- ✅ Cloudflare 保护运行正常
- ✅ 本地 stdio 工作完美 — initialize / tools/list / tools/call 全部正常
- ✅ 协议支持清晰（MCP 2025-06-18 + Streamable HTTP）
- ✅ 注册 API 端点可用 (`POST /api/register/`)

### 需要注意
- ⚠️ Remote endpoint 文档与 local stdio 文档混在一起，容易让用户混淆
- ⚠️ 文档中 remote 用法像是「附加功能」，而本地 stdio 是主要推荐方式
- ⚠️ 文档声称 2 个工具，实际有 4 个 — 缺少 `misakanet_submit_usage` 和 `misakanet_usage_status`
- 🔴 **注册 CI (#849) 因 `misakanet-avatar.py` 缺失而失败** — 新用户完全无法获取 token

## 总体评价

**Remote MCP endpoint 的服务端已就绪，本地 stdio 体验完美。但远程认证链路在两步上都断了：① 文档未说明 token 来源，② 注册 CI workflow 因 `misakanet-avatar.py` 缺失直接崩溃。**

本地 stdio 体验优秀 — initialize / tools/list / tools/call 全部正常，BM25 搜索可用。Remote 端点在协议层面也没问题（405 → POST、401 → Unauthorized 错误信息清晰），但用户拿到 token 的路径完全断裂。

### 建议优先修复
1. **P0**: 修复 `register.yml` — `misakanet-avatar.py` 缺失导致 CI 崩溃
2. **P0**: Token 获取流程文档化（在 `mcp-remote.md` 中说明注册→CI→token 的完整路径）
3. **P1**: 配置示例添加 token 获取链接
4. **P2**: 更新工具列表文档（2→4）
5. **P3**: 独立的 remote quickstart 文档，与 local stdio 分开

---

*此报告由 Hermes Agent 自动生成，作为 ClawHunt agent bounty hunter 的一部分。*
*相关: [#804](https://github.com/Ikalus1988/MisakaNet/issues/804) (MCP endpoint), [#818](https://github.com/Ikalus1988/MisakaNet/issues/818) (社媒引流)*
