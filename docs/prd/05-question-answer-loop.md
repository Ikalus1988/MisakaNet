# PRD ⑤ Question Answer Loop —— question intake 的回答 → 知识闭环

- **状态**: 🟢 方案 A 试点中（2026-09-03：2 条已答）· 优先级: 🟢 低 · 工作量: 设计已定，实施 1-2 天
- **前置**: #1396 链路已修复——question 不再被当 lesson auto-reject（workflow 路由 + MCP 入口自动识别 + `intake_pipeline` 不再为 question 铸 lesson 草稿）。当前 question intake 会安全地留 open 等人工。

## 1. 背景与问题

question intake（`kind=question`，`[Question]` issue）现在的终点是「安全留 open」：
- 提交方的问题**没人回答**（无机制触发回答）；
- 即使维护者回答了，答案躺在 issue 评论里，**不可检索**（`misakanet_search` 只搜 lessons.json）；
- issue 只能靠 stale 30 天不活跃后自动关闭，**答案与问题都流失**——question 转不成可复用知识，飞轮最后一段没接上。

现状数据：open question intake 4 个（#1362/#1364/#1396/#1397），均无答案。这是「设计先行、等数据触发」的典型场景——现在没有足够样本验证任何自动方案。

## 2. 目标

- 提交方的问题能**得到回答**（维护者或后续 agent）；
- 被回答的 Q&A 能**沉淀为可检索知识**（进入搜索语料 / FAQ 页），二次命中即飞轮；
- 不引入新的常驻服务；沿用现有「issue → 人工/agent → 合入 → CI 门禁 → data sync」协作链。

## 3. 方案选项

### 方案 A（推荐，轻）：回答留在 issue，定期人工沉淀 FAQ 条目
- 流程：问题 intake 留 open → 维护者/认领 agent 在 issue 里回答 → 维护者加 `answered` label + 关闭 → 每季度（或累计 ≥10 个 answered 时）把 Q&A 人工整理成 FAQ 条目（`FAQ.md` 或 `docs/faq/*.md`，纳入 llms.txt）。
- 优点：零基础设施；回答质量由人保证；与现有协作链一致。
- 缺点：沉淀节奏依赖人工；没有「未回答问题自动提醒」。

### 方案 B（中）：LLM 起草答案，维护者确认后沉淀
- 流程：`[Question]` issue 打 `answer-pending` label → 定时 workflow 调 LLM（复用 minimax OPENAI_KEY，见 pr-agent 先例）按问题 + 相关 lesson 检索起草答案，发到 issue 评论 → 维护者确认/修改后加 `answered` + 关闭 → 同上沉淀 FAQ。
- 优点：回答不依赖维护者逐条手写；草稿可被检索上下文约束。
- 缺点：质量门槛需要维护者确认环节；成本/限流要控制（周频 + 每 issue 一次）；多语言（葡语/西语问题）需要翻译处理。

### 方案 C（重，暂不推荐）：FAQ 成为一等公民数据
- 把 Q&A 建成结构化数据（`data/faq.json`），进搜索索引与站点渲染，lesson/FAQ 统一 kind 过滤（呼应 #1441 search kind 过滤）。
- 优点：真正进入检索语料，飞轮最完整。
- 缺点：依赖 #1441 的搜索架构改造；当前样本太少。

## 4. 推荐路径与触发条件

**推荐：先按方案 A 人工跑一个季度**，同时满足以下任一条件再升级：

1. **触发 B**：open question intake 中「无答案且 >14 天」≥ 5 个 —— 说明回答供给跟不上，需要 LLM 起草；
2. **触发 C**：已沉淀 answered Q&A ≥ 10 条 —— 说明值得进结构化 FAQ 与检索；
3. 季度 review（如 2026-12 前）无任何触发 → 维持 A + 每年清理一次 stale。

## 5. 验收标准（实施 A/B 时）

- [ ] 维护者回答并加 `answered` label 的 question issue 会被关闭
- [ ] 沉淀的 FAQ 条目出现在 `misakanet_search` 结果或 `llms.txt` 可检索范围
- [ ] 未回答 question 超期时有提醒（B 才有）
- [ ] 全量回归：question 路由/审计不受影响（`intake-kind-audit`、triage、auto-review 行为不变）

## 6. 依赖与风险

- 依赖：现有 GitHub 协作链；B 依赖 LLM key 与节流；C 依赖 #1441。
- 风险：低（方案 A 无代码）；B 的回答质量与成本需试点；C 的 FAQ 与 lesson 语义边界需要定义（FAQ = 指导/概念性知识，lesson = 失败+修复案例，与 #1396 讨论一致）。

## 7. 现在就能做的最小动作

- 维护者回答任意 open `[Question]`（#1362/#1364/#1396/#1397）→ 加 `answered` 标签并关闭——先积累样本，同时验证方案 A 流程。
- 本 PRD 保持 open，作为方案 B/C 的决策入口。

## 8. 试点记录（2026-09-03）

方案 A 首次执行（`answered` 标签已建，color `0e8a16`）：

| Issue | 问题 | 处置 |
|---|---|---|
| #1362 | How should agents handle GitHub rate limits on shared runners? | ✅ 已回答（引用 `github-rate-limit-auth.md` E2 lesson + 403/Retry-After lesson）→ `answered` + closed |
| #1364 | How do I configure MCP server authentication for production? | ✅ 已回答（引用 `docs/integrations/mcp-remote.md` auth 表 + register/oauth lessons）→ `answered` + closed |
| #1365 | （#1364 重复） | 已 close（dup of #1364） |
| #1396/#1397 | PT，缺细节 | 留 open 等提交方补充（今日已发澄清评论） |

样本数：answered = 2/4。按 §4 触发条件：≥10 answered 或季度 → 编译 FAQ 条目进搜索语料；「无答案 >14 天 ≥5」→ 升级方案 B。

---

## 9. 竞品调研：知识/答案怎么回到 agent（2026-09-03）

针对「agent 提问 → 人工异步回答 → 答案如何送回」，调研 Glama 同类 failure-memory MCP 与 HITL 先例：

| 服务器 | 形态 | 知识回到 agent 的机制 |
|---|---|---|
| [Casebook/AgentPostmortem](https://glama.ai/mcp/servers/AgentPostmortem/Casebook-MCP) | 只读事故语料（Worker、无鉴权、60 req/min/IP） | 纯同步检索 `search_cases`/`similar_failures`；无写入、无问答 |
| [claimidx](https://github.com/claimidx/claimidx) | 签名失败索赔账本（dense claim、Ed25519） | **ask-before-retry** + confirm/fail/verify 闭环；`home-pull` 拉取账本；匿名发布被拒 |
| [unstuck-mcp](https://github.com/SamuelH98/unstuck-mcp) | 尝试追踪/拦截 | 同一错误第 3 次**强制先用自己的 web search**（`confirm_search` 放行），靠 tool 描述 + AGENTS.md 引导而非硬拦截 |
| [knoten](https://glama.ai/mcp/servers/BY571/knoten) | 研究图（git，alive/dead/retracted + 理由） | 问句式查询（"has anyone tried X?"）→ 图直接答「试过/为何死」；答案来自之前沉淀，同步 |
| [Sentinela MCP](https://glama.ai/mcp/servers/luclinocruz/lucross-sentinela-mcp) | 跨会话 lessons，**禁 agent 自评 success** | 按需拉取（"pull up past correction lessons"）；verdict 只来自人工/外部审计 |
| [Kira](https://glama.ai/mcp/servers/aibenyclaude-coder/Kira) | 失败记忆 + 社区 skills/scars 库 | lookup 检索 + report 写入（consent/脱敏分层） |
| [loop-in-mcp](https://github.com/Robbertvermeulen/loop-in-mcp) / [hitl-mcp](https://github.com/ZenlixAI/hitl-mcp) | **异步 HITL**（state-persistent） | agent 挂起 → 结构化问题 → **后续会话显式 pull 回答案**（"pulls structured answers back later"）；另见 [MCP Tasks 规范](https://agentrq.com/blog/mcp-tasks-spec)（长任务方向） |

### 调研收敛出的四条规律

1. **无人做推送**。全部把答案沉淀为「可查询物」，asker 或后来者在**决策点再查**（search/ask/pull/lookup）——我们的「拉取式」判断成立。
2. **问句型（knoten）与异步人工型（loop-in-mcp/hitl-mcp）证明**：异步 Q&A 成立的前提是 **① 问题状态持久化 ② 提供显式 check/pull 工具**（"pulls structured answers back later"）。只靠 7 天 KV dedup 不够。
3. **答案权威来自人工/外部验证**（Sentinela 禁自评、claimidx 匿名禁写）——回填语料只应收维护者回答。
4. **引导机制**（unstuck/claimidx）——靠 tool description + AGENTS.md/skill 让「先查答案、别盲目重试」成为 agent 的自然下一步。

### 对 MisakaNet 的收敛设计（待实施确认）

- **短等待**：同题重提（dedup hit）→ 返回 `{answered:true, answer}` 或 `{pending, issue_url}`（= unstuck 的「重试前先查」+ A 档）
- **长等待/陌生 asker**：answered → 自动沉淀 FAQ 语料，`misakanet_search` 命中即送达（= Casebook/knoten/Kira 模式，C 档）
- **调研新增的一层**：持久化问题状态（D1 `questions` 表：issue_number/dedup_hash/status/answer）+ 显式 pull（按 intake_id 查）——对齐 loop-in-mcp/hitl-mcp；dedup KV 7 天过期或 asker 忘记原文也能凭 intake_id 取回
- **权威门槛**：只有 `answered`（人工确认）进入语料；维护者侧由 workflow 监听 answered 事件回填状态/答案
