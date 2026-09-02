# PRD ① MCP Intake Question —— 查询无答案后的补传闭环

- **状态**: ✅ **已实施**（2026-08-28，commit c14e9aeb）· 优先级: 🔴 高 · 工作量: 小（0.5-1 天）
- **创建**: 2026-08-28 · 维护: MisakaNet

> **实施记录**：方案 A 已落地 —— `misakanet_search` 零结果时返回 `no_match: true` +
> `suggestion`（引导调 `misakanet_submit_intake`，kind=missing_lesson）+ 结构化
> `intake` 模板（tool/args，便于 tool-calling agent 直接续调）。测试：
> `workers/mcp-no-match.test.mjs`（4 用例，已接入 mcp-stress CI）。方案 B
> （独立 `misakanet_ask_question` 工具）暂缓 —— 现有 submit_intake 已覆盖语义。

## 1. 背景与问题

当前 `misakanet_search` 无结果时，agent 需要**手动**再调 `misakanet_submit_intake`（kind=missing_lesson）补传问题。实际使用中多数 agent 搜不到就直接放弃 → 反馈闭环断裂，维护者无法感知"用户真实遇到但知识库缺失"的问题。

## 2. 目标

- Agent 在 search 无答案时，能在**同一请求链内**便捷补传问题
- 补传的问题自动进入 intake 流程（可追踪、可审核）
- 不增加 agent 的认知负担（零额外学习成本）

## 3. 需求细节

### 3.1 功能需求

**方案 A（推荐，最小改动）**：`misakanet_search` 无结果时响应内嵌引导
- 返回结构增加字段：`no_match: true` + `suggestion`（引导提交 intake 的提示文本 + 调用方式）
- agent 读到 suggestion 即可续调 `misakanet_submit_intake`

**方案 B（可选）**：新增工具 `misakanet_ask_question`
- `tools/call {name: misakanet_ask_question, args: {question, error?, context?, source?}}`
- 创建 question 类型 issue（labels: `question,pending-review,needs-human-review`）
- 与 submit_intake 并存，语义更明确（question = 知识缺口，intake = 失败案例）

### 3.2 非功能需求

- 无认证可用（与 submit_intake 一致，限流保护）
- 脱敏：question 内容复用现有 redactIntake 逻辑
- 防 spam：沿用 SPAM_KEYWORDS + 速率限制
- 去重：相同 question 提示已存在（可选增强）

## 4. 技术方案

- 修改 `workers/register-proxy-sw.js`：
  - search 处理：无结果分支追加 `no_match` + `suggestion` 字段（~20 行）
  - 可选：新增 `misakanet_ask_question` 工具 + issue 创建（~40 行）
- 部署：现有 worker 部署流程（KV 中转 / CI）

## 5. 验收标准

- [ ] search 无结果时响应含 `no_match: true` + `suggestion`（HTTP 实测）
- [ ] agent 按 suggestion 调用 submit_intake 成功创建 issue（label 正确）
- [ ] question 内容脱敏（含敏感模式时替换为 [REDACTED:xxx]）
- [ ] 全量回归：search 有结果时行为不变

## 6. 依赖与风险

- 依赖：现有 MCP 基础设施（已就绪）
- 风险：低（增量改动）

## 7. 后续增强

- 补传问题自动聚类（相同/相似问题合并）
- search 无结果时返回"相关主题"建议（引导更准确的 query）
