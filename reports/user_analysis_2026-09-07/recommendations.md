# 行动建议清单

_报告生成于 2026-09-07T17:13:57.877681+00:00_

## 🔥 紧急（24 小时内）


### 1. 回复 Henrik 的 MCPVault 邮件
- 3 封跟进仍未回（`rate:email:hello@trymcpvault.com` 限频没生效）
- **建议**: 回复一封简短的 unsubscribe / claim 决定，避免更多跟进
- 或在 MisakaNet 邮件路由层加硬限频（drop 邮件而不是限速）

### 2. 评估 `gap:gemini safety refusal bypass roleplay`
- 这是敏感主题：用户在搜索绕过 Gemini 安全机制
- **建议**: 确认这是研究目的（红队/合规）还是绕过用途
- 如是合规研究：补一篇 lesson；如不需要：从 gap 中清理

### 3. 清理 OAuth 本地凭据
- `~/.cf_oauth_token.json` 包含 access + refresh token
- **建议**: 任务结束后 `rm ~/.cf_oauth_token.json`
- 或至少在 `~/.bashrc` 加 alias 提醒清理

## ⚡ 重要（本周内）


### 4. 补全知识库盲区（按 ROI 排序）

**ROI 最高**（多个 gap 相关，建议综合 1 篇 lesson）:
- **Vertex AI + BigQuery + Cost** (3 个相关 gap):
  - `vertex ai cost analysis bigquery billing`
  - `bigquery billing traces monthly aggregated costs`
  - `vertex cost gemma`
  → 写一篇《Vertex AI 成本归因：BigQuery + traces + Gemma 混合计费实践》

- **Embedding 迁移** (2 个 gap):
  - `embedding vertex ai qwen`
  - `vertex ai embedding migration go`
  → 写一篇《Vertex AI Embedding 迁移实战（Python + Go）》

**单一 gap**（每篇独立 lesson）:
- `rag performance latency optimization` — RAG 延迟优化
- `vertex ai routing provider openrouter maas` — Vertex → OpenRouter 路由
- `iap tcp forwarding numpy upload bandwidth` — IAP + numpy 上传
- `thought tags stripping` — thought tag 剥离
- `roleplay time consistency hallucination` — 角色扮演时间一致性
- `sdk client centralization architecture` — SDK 集中化架构
- `case sensitive strings.contains lowercase` — 大小写敏感 Contains
- `vertex ai gemini safety settings pass` — Gemini 安全 pass-through
- `vertex streaming` — Vertex 流式
- `evals vertex gemini gemma` — Vertex/Gemini/Gemma 评测
- `docker compose` — Docker compose 实战
- `dco sign-off` — DCO 签名
- `preset` — preset 模板

### 5. 修复 email intake `intakeType`
- 5/5 全部是 `unknown`
- **建议**: 检查 intake 分类逻辑（可能是关键词匹配/ML 分类未启用）
- 启用后 `intakeType` 可用于自动路由到对应节点

### 6. Henrik 限频修复
- `rate:email:hello@trymcpvault.com` 存在但 Henrik 仍发了 3 封
- **建议**: 检查 rate-limit 实际逻辑（KV key + email 路由系统）
- 可能限频阈值太高 / 检查的是发送间隔不是次数

## 📅 计划（下个 sprint）


### 7. 启用用户反馈闭环
- `helpful` 只有 3 条 / `feedback` 只有 2 条 — 闭环几乎没数据
- **建议**:
  - search_knowledge.py 返回结果时加 👍 / 👎 按钮
  - 反馈数据写 KV (`feedback:<uuid>`)
  - 高 helpful 率的 lesson 自动在搜索结果加权

### 8. 流量历史保留
- `traffic:*` 只保留3 天 — 缺长期趋势
- **建议**: 写一个 daily cron，把 traffic 按月聚合存 `traffic-month:<type>:<YYYY-MM>`

### 9. mcp_token 自动清理
- 已有部分 token 过期（exp_buckets 里"已过期: 0"）
- **建议**: daily cron 检查 `expires < now` 的 token → 删除

### 10. Gap 数据补 lesson 后清理
- 补 lesson 后，对应的 `gap:query` key 应该删除（避免 gap list 永久积累）
- **建议**: lesson 入库时自动删除对应 gap key

## 🔮 长期（季度）


### 11. 节点健康监控
- 60 个节点中，活跃 token 引用 41 个
- **建议**: 对每个 node 加心跳 / 健康检查 endpoint
- 不活跃 30 天的 node 自动归档

### 12. MisakaNet Dashboard
- 当前数据散落在 KV，没统一视图
- **建议**: 写一个 admin page（Cloudflare Worker + KV 读取）：
  - 节点地图
  - 邮件流量时间线
  - gap 知识债看板
  - feedback / helpful 趋势

## 🛡 安全 / 资源清理


- [ ] 删除 `~/.cf_oauth_token.json`（OAuth 任务结束后）
- [ ] 评估是否需要在 CF Dashboard revoke 当前 OAuth grant
- [ ] 不需要时也清掉 `~/.local/share/agently-cli/` 和 `~/.agently-cli/`（本次任务用的）
- [ ] MisakaNet repo 里的 intake_dedup 13 条 issue 状态检查