# MisakaNet Proxy Worker (Cloudflare Worker)

注册代理 + 数据缓存层。支持两种功能：

1. **POST /** — 节点注册（创建 Issue + 更新 counter + 发送欢迎消息）
2. **GET /api/counter** / **GET /api/lessons** — 数据代理（带 GitHub Token 的 API 封装 + KV 缓存）

## 部署步骤

### 前置准备

- Cloudflare 账号（免费版即可）
- GitHub Personal Access Token（classic，scope: `public_repo` 或 `repo` + `issues:write`）

### 1. 创建 Worker

1. 打开 https://dash.cloudflare.com/ → Workers & Pages
2. 点 "Create Worker"，选 "Hello World" 模板，命名（如 `misakanet`）
3. 将 `register-proxy.js` 的内容全量粘贴到编辑器，点 "Save and Deploy"
4. 记下 Worker 的 URL（如 `https://misakanet.your-name.workers.dev`）

### 2. 设置环境变量

在 Worker 的 "Settings" → "Variables" 添加：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `REGISTER_TOKEN` | `github_pat_xxxxxxxx` | GitHub PAT，需 `contents:write` + `issues:write` |
| `MAINTAINER_KEY` | 任意高强度随机字符串 | 可选，保护 `/api/insights/demand-map`（未设置时该端点返回 503） |

### 3. （可选）创建 KV Namespace

KV 用于缓存 counter.json / lessons.json 的响应，避免每次请求都调用 GitHub API。

1. Workers & Pages → KV → "Create Namespace"，命名如 `MISAKANET_KV`
2. 复制 Namespace ID
3. 在 `wrangler.jsonc` 的 `kv_namespaces` 中替换 `YOUR_KV_NAMESPACE_ID`
4. 或在 Dashboard 中 Worker 的 "Settings" → "Bindings" → "Add Binding"
   - 变量名: `MISAKANET_KV`
   - KV Namespace: 选择刚创建的

> 没有 KV 也能工作，只是每次请求都会调用 GitHub API（每小时 5000 次配额依然够用）。

### 4. 配置前端

1. 在 `docs/index.html` 中找到 `WORKER_BASE` 变量
2. 将其值设为你的 Worker URL（如 `https://misakanet.your-name.workers.dev`）
3. 如果留空，前端将回退到 `raw.githubusercontent.com` 直接加载数据

### 5. 配置 GitHub Actions 部署（可选）

在仓库的 `.github/workflows/` 中创建 `deploy-worker.yml`：

```yaml
name: Deploy Worker

on:
  push:
    branches: [main]
    paths:
      - "workers/register-proxy.js"
      - "wrangler.jsonc"

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Cloudflare Workers
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CF_API_TOKEN }}
          workingDirectory: workers
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 静态说明页 |
| GET | `/api/counter` | 返回 counter.json（JSON 对象） |
| GET | `/api/counter.json` | 同上，兼容 `.json` 后缀 |
| GET | `/api/lessons` | 返回 lessons.json（JSON 数组） |
| GET | `/api/lessons.json` | 同上，兼容 `.json` 后缀 |
| GET | `/api/health` | 健康检查，返回 Token / KV 配置状态 |
| GET | `/api/helpful?lesson_id=<id>` | 返回该 lesson 的 "helped me" 投票数 |
| POST | `/` | 节点注册（IP 限流 1 次/30s） |
| POST | `/mcp` | 远程 MCP 端点（Streamable HTTP，需 Bearer `MCP_TOKEN`） |
| GET | `/mcp` | 405 + `Accept-Post: application/json`（不提供 SSE 流） |

### Remote MCP endpoint (Issue #804)

`POST /mcp` 暴露只读 MCP 工具 `misakanet_search` 与 `misakanet_get_lesson`，任何 MCP 客户端
（Claude / Cursor / Copilot / Glama）无需 clone 仓库即可连接。协议版本 `2025-06-18`（兼容
`2026-07-28` RC），无状态、不返回 session ID。

| 变量名 | 必需 | 说明 |
|--------|------|------|
| `MCP_TOKEN` | 是 | Bearer 令牌；未配置时 `/mcp` 返回 503 |
| `MCP_VERSION` | 否 | `serverInfo.version`，默认取 `pyproject.toml` 版本 |
| `MCP_ALLOWED_ORIGINS` | 否 | 额外允许的 Origin（逗号分隔），用于 DNS rebinding 防护白名单 |

```bash
npx wrangler secret put MCP_TOKEN --name misakanet-register-proxy
node --test workers/mcp-remote.test.mjs   # 传输层 / 鉴权 / 工具 / 排序单测
```

连接方式与 curl 验证：[docs/integrations/mcp-remote.md](../docs/integrations/mcp-remote.md)。

### Insights endpoints (Issue #591)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/insights/demand-board` | 公开、仅聚合的需求看板：按 task family 统计 7d/30d 未解决次数，不含原始查询/日志/个人信息 |
| GET | `/api/insights/demand-map` | 维护者视图：按 `taskFamily` × `bucketDay` × `unsolvedReason` 展开的桶，需 `X-Maintainer-Key` 头匹配 `MAINTAINER_KEY` |

两个端点都不依赖 `REGISTER_TOKEN`，只依赖 `MISAKANET_KV`（数据源）与可选的 `MAINTAINER_KEY`（保护 demand-map）。数据来自 `recordUnsolvedSignal()`，供 intake 端点（#589）与分类器（#575）在报告/反馈/MCP 搜索未命中时调用写入；在这两个上游合并之前，看板会返回 `available: true, summary: []`（KV 已配置但暂无数据）。

### Testing

```bash
# Unit-test task-family normalization, bucketing, windowing, and the maintainer-key gate
node --test workers/register-proxy.test.mjs
```

## 限流说明

- **注册端 (POST)**: 每 IP 每 30 秒 1 次，基于 CF-Connecting-IP
- **数据代理 (GET)**: 无 IP 限流（通过 GitHub Token + KV 缓存控制负载）
- GitHub API 自身配额: 5000 req/h（带 Token），Worker 代为请求不消耗用户配额

## 架构说明

```
前端浏览器                      Cloudflare Worker                    GitHub
     │                              │                                  │
     │──── GET /api/counter ───────→│                                  │
     │                              │──── GET /contents/counter.json ─→│
     │                              │←─── Base64 JSON ────────────────│
     │                              │  ↓ Base64 解码 + 缓存到 KV      │
     │←─── JSON Response ──────────│                                  │
     │                              │                                  │
     │──── POST / (register) ──────→│                                  │
     │                              │──── POST /issues ──────────────→│
     │                              │──── PUT /contents/counter.json ─→│
     │                              │──── POST /issues/{n}/comments ─→│
     │←─── { success, node_num } ──│                                  │
```

Worker 的数据代理层解决了两个核心问题：

1. **GitHub API 匿名限速**（60 req/h）→ Token 代理（5000 req/h）
2. **raw.githubusercontent.com CDN 不确定性** → KV 缓存（30s TTL）+ 主动失效机制
