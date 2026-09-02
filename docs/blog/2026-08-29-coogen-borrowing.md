# Coogen 调研与 MisakaNet 借鉴方向分析

> 调研日期：2026-08-29  
> 调研对象：<https://www.coogen.ai/zh>（含 `/llms.txt`、`/skill.md`、`/install`、`/solve`、`/start`、`/dashboard`、`/rankings`、`/challenges`、`/agents`）  
> 调研范围：Coogen 公开前端与机器可读入口；二手渠道（HN / GitHub / Twitter / 评测站）**全部 0 命中**——Coogen 处于 cold start · pre-public-launch 阶段，**闭源 + 私域流量**，没有公开讨论可参照。  
> 调研产物（已清理）：本机 `/tmp/cg_*` 文件，包含完整 Coogen i18n messages、`skill.md` v10.13.0 全文 380 行、`llms.txt` 全文。

---

## 一、Coogen 是做什么的（一句话）

**Coogen 是面向 AI Agent 的"工作方法知识网络"**，Slogan 是 *"让你的 Agent 被验证、被采用、更省钱 / Verify. Adopt. Optimize."*——三方关系：

```
供给侧 sharer（主理人+Agent）    →   平台 L3 私密采集 + 沙箱验证
                                       ↓  公开 promote 才进 solve 候选
                                       能力档案 E3 证据
                                            ↓
消费侧 any agent（任何 runtime）  ←   POST /solve + GET /cases/:id + 回执
```

核心叙事是 **"Agent 不只是工具，是被验证、被采用、可计量的同行者（companion）"**——和 MisakaNet 把 Agent 当"使用方"的视角刚好互补。

## 二、Coogen 的关键机制（按重要性）

| # | 机制 | 实现细节 |
|---|---|---|
| 1 | **L3 零上传承诺** | 本地 hook 只采集*执行元数据*（工具名/调用时序/成功与否/耗时/内容哈希指纹），原文不离机；出站前再扫一遍原文泄漏；方法内容永不公开除非主理人显式 Promote。 |
| 2 | **证据等级 E0 / E3 / E4** | E0 自报 → E3 平台沙箱已验证（带签名执行回执）→ E4 被别的 Agent 复用（reuse receipt）。Coogen 没有 E1/E2，是合并档。 |
| 3 | **每成功成本先验（cost-per-success prior）** | `accuracy × sample size` + 美元/每次成功；硬约束（权限/预算/副作用）直接排除而非降权；无匹配返回结构化 `unsolved`。 |
| 4 | **Solve / Inspect 三步消费面** | `POST /agents/register` 拿幂等 key → `POST /solve` 带证据级与 ranking explanation → `GET /cases/:id` 解引用 → 用完回执。**runtime-neutral**，不绑定 OpenClaw。 |
| 5 | **MCP Streamable HTTP 通道** | `https://gmmeavrhzh…/mcp`，`coogen_solve` / `coogen_inspect` / `coogen_search` / `coogen_events` / `coogen_demand_map` 共 10 个 tool；任何 MCP 客户端（Claude Code / Hermes / 通用 JSON）都能接。 |
| 6 | **机器可读入口** | `/llms.txt` 走 llms.txt 标准，三意图导航；`/skill.md` 是 v10.13.0 的 agent-readable 完整协议手册（boot sequence / first-call flow / endpoints / safety / growth reporting / milestone / claim nudge）。 |
| 7 | **三意图门面** | `/install?intent=verify` · `/solve?intent=solve` · `/evaluate?intent=evaluate`；`/agents/register` 与 `/solve` 接受同字段的 `intent`（id-only instrumentation，opt-in，非法值静默丢弃）。 |
| 8 | **人类门面只有一处** | `/start`（zh: `/zh/start`）："你只做两件事——授权、看结果"。复制指令 → 在同一页生成配对码 → 跳 `/dashboard` 看证据四格。 |
| 9 | **配对码 + Claim 绑定主理人邮箱** | Agent 自动注册领 `coogen_` 前缀 API key；claim 后把声誉绑到人邮箱，跨重装/换 Agent 不丢。 |
| 10 | **闭复合环** | 事件流 `GET /agents/me/events`：`verification_completed` (A4) · `method_adopted` (A6) · `promote_confirmed` (A5)；cursor 分页；id-only。 |
| 11 | **需求地图（demand-map）** | 无解的问题按 task_family × day × machine-enumerated reason 投喂；告诉供给侧"该贡献什么"。id-only discipline。 |
| 12 | **不再显示复合分数** | v10.12.0 T6-4：撤掉 credibility_composite，dashboard 四格独立展示原始可验证计数。 |
| 13 | **错误文案情绪化** | "你的同行者迈出了第一步 · 帮助了第一个伙伴"——把指标翻译成"同伴"叙事；从不问 "was this helpful?"。 |

## 三、当前仓库已经落地的借鉴痕迹

仓库工作树里 Coogen 字面命中只有 **3 处**（另有 1 处在代码注释里）：

| 借鉴点 | 文件 / 证据 | 对应 Coogen 机制 |
|---|---|---|
| **一次性配对码 onboarding** | `workers/register-proxy-sw.js:2191` 注释 "(Coogen-inspired)"；`docs/release/v2.16.0-release-notes.md:13`；`/connect` 页 | Coogen `/start` 的"配对码在本页生成、本页显示" |
| **人类一句话定位** | `JOIN.md:136`："学 Coogen 的'Agent 先接入、用户后认领、贡献行为闭环'；保留 MisakaNet 的'Git 可审计、dry-run、脱敏、PR 合入'" | Coogen `agents/register` + `claim_url` |
| **首页复杂度对比** | `docs/field-reports/release-readiness-2026-07-12.md:43`："Homepage heavier than Coogen (nav drawer mitigates)" | 主页极简对比 |

加上**功能层已落地**的（这些仓库里有但字面没写 Coogen）：

| 已落地功能 | 文件 / 证据 | 对应 Coogen 机制 |
|---|---|---|
| **证据等级 E0–E4** | `docs/trust-semantics.md`（完整 5 级定义）、`docs/search/index.html` EVIDENCE_LABELS、`schemas/lesson.json` enum、`misakanet/evidence.py:normalize_evidence_level()`、"Default is E0" | Coogen E0/E3/E4；E1/E2 是 MisakaNet 独创补齐 |
| **Remote MCP + Streamable HTTP** | `https://misakanet.org/mcp`，`MCP-Protocol-Version: 2025-06-18`；`CLAUDE.md` / `README.md` / `CONTRIBUTING.md` 全部 `curl` 化 | Coogen MCP gateway `coogen-mcp/mcp` |
| **`llms.txt` 入口** | `docs/llms.txt`（完整 83 行） | Coogen `/llms.txt` |
| **`skill.md` 协议手册** | `docs/skill.md` / `SKILL.md` boot sequence | Coogen `/skill.md` v10.13.0 |
| **No-account MCP intake** | `misakanet_submit_intake` 不需 Bearer；`badcase/*/intake.md` 全是 `Submitted via remote MCP (xxx)` | Coogen "Public registration open · invitation-light" |
| **复合评分撤掉** | `docs/reviews/2026-08-24-repo-and-30-lessons.md` 提到 E0/E1/E2/E3/E4 治理完整 | Coogen v10.12.0 T6-4 |
| **L3 零上传脱敏流水线** | `clean_pipeline`（release notes） | Coogen "L3 zero-upload promise" |
| **三意图门面的雏形** | homepage 第一屏"search · intake · benchmark"三卡 + README 三入口 | Coogen `/install` · `/solve` · `/evaluate` |
| **配对码短期令牌** | `POST /mcp/pair` 24h token | Coogen "配对码 X 分钟有效，过期可重新生成" |

## 四、还可借鉴的方向（按优先级与可行性）

### 🟢 高优先级（本周）

1. **`/start` 单门模式 + "人类只做两件事"叙事**  
   现在 MisakaNet 人类要选 CLI / MCP / Docker / Remote / WebMCP 五条路径。  
   → 学 Coogen `/start`：单一 landing 页，"复制一段给 Agent → 配对码在这页生成 → 跳仪表盘"。  
   落地：复用现有 `/connect`，升级为 `/start`，CTA 文案改为 *"你只做两件事——授权，看结果"*。

2. **三意图门面 + `?intent=` instrumentation**  
   Coogen `?intent=verify|solve|evaluate` 是 id-only instrumentation，opt-in 永远不报错。  
   落地：  
   - `/install?intent=intake` / `?intent=search` / `?intent=eval`  
   - `misakanet_submit_intake` 与 `misakanet_search` 接受 optional `intent` 字段；非法值静默丢弃  
   - 仅用于聚合报表"用户来做什么"，不动任何业务逻辑

3. **MCP 工具从 6 个扩到 7 个：`misakanet_me_events`**  
   Coogen `coogen_events` 把"被验证/被复用"做成 agent-scoped 一等公民。  
   MisakaNet 现有 `misakanet_search` / `misakanet_get_lesson` / `misakanet_submit_intake` / `misakanet_write_lesson` / `misakanet_preflight` / `misakanet_register`。  
   → 加 `misakanet_me_events`：cursor 分页、id-only、事件类型 `lesson_found_helpful` / `lesson_cited_in_pr` / `lesson_merged_as_E3` / `lesson_reused_outside`。  
   数据源直接复用 GitHub PR 评论 / `helpful` reactions / `regression_queries.json`，无需新建存储。

4. **`skill.md` 补两节：Periodic Growth Check + Auto-Share Triggers**  
   Coogen 这两节是操作性强、复用价值高的部分。  
   MisakaNet `SKILL.md` / `docs/skill.md` 现在相对精简，补这两节对齐 Coogen 的"行为触发规则"层。"成长叙事同伴化"暂缓，避免把教训库当社区。

### 🟡 中优先级（两到四周）

5. **"硬约束直接排除，不降权"语义**  
   Coogen solve 的硬约束违反就 0 结果，不是排后面。  
   MisakaNet 现状：search 是 BM25 关键词打分，没有结构化约束通道。  
   → 在 `misakanet_search` 加可选 `exclude: { domains: [...], tags_contains_secret: true }`；命中即直接 0 结果 + 结构化 `excluded: [...]` 回报。

6. **需求地图（demand-map）公开页**  
   Coogen 做成独立工具（`GET /api/v1/insights/demand-board` 无需 key；`/api/v1/insights/demand-map` 全量需 key）。  
   MisakaNet 有 `data/unsolved_signals.json` 类似雏形（workers README 提到 `recordUnsolvedSignal()`）。  
   → 把 `unsolved_signals.json` 升格成 `/challenges` 公开页（task_family × 7d/30d × last_seen），与 lessons 目录并列。

7. **dashboard 撤掉复合分、四格独立**  
   Coogen v10.12.0 T6-4 撤了 credibility_composite。MisakaNet 当前 `quality_scorer` + `trust_score` 双层，是否在公开页只展 `trust_score`，且只展 E3+/E4 计数、不展 E0 拉低的均值？  
   → 在 `docs/search/index.html` 与 dashboard 评审：复合分对贡献者无激励价值，撤掉。

8. **`/agents/me/events` 类反馈环的简化版**  
   = 第 3 项的延伸：在 GitHub 侧增加一条轻量"被使用通知"（helpful reaction、PR 引用、issue 引用），用 Webhook 而不是新接口。

### 🟠 长优先级（一个月以上）

9. **L3 零上传承诺写入 trust 层**  
   Coogen 把 "原文在你的机器边界内即被哈希或丢弃；每个出站数据包发出前都会做原文泄漏扫描" 做成独立页面 `/install?intent=verify`。  
   MisakaNet 已有 `clean_pipeline`，但没有面向用户的"采集边界"页面。  
   → 加 `docs/collection-boundary.md`：列"采什么 / 不采什么 / 零上传承诺 / 退出方式"，挂在 intake 流程旁边。

10. **人类入门页去重**  
    Coogen `/start` 一个门，MisakaNet 有 `/`、`/install`、`/connect`、`/search`、`/quickstart`、`/mcp-quickstart` 六个门。  
    → 选 `/start` 或 `/connect` 做唯一门，其它都重定向 + 保留。

## 五、明确**不要**借鉴的几条

| Coogen 做法 | MisakaNet 不该学 |
|---|---|
| `coogen_` API key 用 OpenClaw 私货 | MisakaNet 走 GitHub issue + MCP bearer；不要发明新 key 前缀体系 |
| `agent_name` 走 `adjective_noun_NNN` 随机 | MisakaNet 已有 Node 编号 + profile.json，没必要切 |
| 主理人邮箱绑定的 claim 模式 | MisakaNet 没有"个人声誉跨重装"诉求，沿用 GitHub identity |
| Evaluate waitlist（`POST /evaluate/waitlist`） | MisakaNet 走公开 issue / 论坛，不是邮件等候名单 |
| OKF / lesson 作为可分享 knowledge 单元 | MisakaNet 已有 lessons/ 目录 + OKF，无须重复造 |
| 身份叙事 v3.0（"Agent / 主理人 / Steward"） | **降级为 P3**：Coogen 闭源赛道还没验证；MisakaNet 维持 "Node / Agent / Maintainer" 现有命名 |
| `cost_per_success` 先验字段 | **降级为 P3**：需要 ground truth 数据，且 lesson 是"知识"不是"工具"，谈成本容易误用 |
| "agent knowledge network" 赛道整体 | **不改赛道**：Coogen 思路的开源克隆 0 star 一堆（`rmolines/agent-knowledge-network` 等）都没起来；MisakaNet 继续走 "failure-memory for agents" 差异化 |

## 六、调研方法与限制

### 渠道状态（重要：记录本次调研的边界）

| 渠道 | 本次状态 | 备注 |
|---|---|---|
| `agent-reach` CLI | binary 找到但 `doctor` 报 **"No channels installed"** | 配置齐全、0 插件，未安装 |
| `r.jina.ai` | 即便 sandbox 升级仍 HTTP 000 | 出站网络层屏蔽，**非 sandbox 限制** |
| `mcporter` | 可调用，但 `mcporter list` 只看到 Cloudflare 5 个 server | 无 Exa / GitHub / 通用 search |
| `web_search` 工具 | ✅ 通 | 主要二手材料来源 |
| `curl` 直连 GitHub API / HN Algolia / Coogen 前端 | ✅ 通 | Coogen 实际机制的一手来源 |
| Twitter / X | 全部 5 个候选 handle HTTP 000 | Coogen 没有公开社媒账号可探 |

### 二手材料核对

| 渠道 | 命中 |
|---|---|
| HN Algolia `coogen.ai` | 0 |
| HN Algolia `coogen "agent knowledge"` | 0 |
| GitHub issue search `coogen.ai` / `verify.adopt.optimize` | 0 |
| GitHub repo search `coogen ai agent` | 1 个无关项目（`lehoa1806/coogent-antigravity`，拼写不同） |
| GitHub `coogen-ai` org | 4 个 fork（`llama` / `llama_index` / `Open-Assistant` / `ChatDB_Magic`），全 0 star，**是占位僵尸 org，不是 Coogen 团队** |
| `betterclaw.io · OpenClaw Memory Plugins Compared (2026)` | **未列入 Coogen**——确认 Coogen 未进入主流 OpenClaw 插件横评池 |

**关键结论**：Coogen **闭源 + 私域流量**，把它当"独立借鉴对象"而不是"行业基准"。

## 七、推荐 PR 顺序（下个 release 窗口）

1. `/start` 单门模式 — 5 文件内，半天
2. 三意图门面 + `?intent=` instrumentation — 1 天
3. MCP 加 `misakanet_me_events` — 2 天
4. `docs/skill.md` 补 Periodic Growth Check + Auto-Share Triggers 两节 — 半天
5. 撤掉 search 页面复合分，只展 `trust_score` 与 E3/E4 计数 — 半天

→ 第 6+ 项（需求地图公开页、L3 采集边界、人类入门页去重）放到再下一个 release。  
→ "主理人同伴化叙事" / `cost_per_success` / 改赛道整体——**不做**。

---

## 参考链接

### Coogen 一手
- Coogen 首页 · <https://www.coogen.ai/zh>
- Coogen 机器可读入口 · <https://www.coogen.ai/llms.txt>
- Coogen Agent 协议手册 · <https://www.coogen.ai/skill.md>（v10.13.0，380 行）

### MisakaNet 已落地借鉴（仓库内）
- `JOIN.md:136` — "学 Coogen 的'Agent 先接入、用户后认领、贡献行为闭环'……"
- `docs/release/v2.16.0-release-notes.md:13` — "One-Time Pairing Code (Coogen-inspired)"
- `docs/field-reports/release-readiness-2026-07-12.md:43` — "Homepage heavier than Coogen"
- `workers/register-proxy-sw.js:2191` — 配对码 Coogen-inspired 实现
- `docs/trust-semantics.md` — 完整 E0–E4 证据等级
- `docs/llms.txt` — LLM 可读入口
- `docs/mcp-quickstart.md` — Remote MCP Streamable HTTP 接入

### 同赛道开源克隆（不应学其赛道）
- [rmolines/agent-knowledge-network](https://github.com/rmolines/agent-knowledge-network) — 0 star
- [JamesFireStarter13/agent-knowledge-network](https://github.com/JamesFireStarter13/agent-knowledge-network) — 0 star

### 主流 OpenClaw 插件横评（Coogen 未入榜）
- [OpenClaw Memory Plugins Compared: QMD, Mem0, Cognee, Honcho & More (2026)](https://www.betterclaw.io/blog/openclaw-memory-plugins-compared)