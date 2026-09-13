# Intake 分诊记录 — 2026-09-13

> SOP：`docs/maintainer/intake-triage.md`（分类口径、回执铁律）。本文件是**一次批量分诊的可查记录**：
> 21 条带 `intake` 标签的开放 issue 逐条分类、已采取的动作、以及留给下一轮候选。
> 目的不是清空 issue 列表，而是让"这堆到底卡在哪"变成可读的表。

## 方法（可复现）

1. 取全部开放 intake：`GET /issues?state=open&labels=intake` → 21 条。
2. **判定"真盲区 vs 伪盲区"用真实检索，不用印象**：用一个注册了稳定 `client_id` 的节点拿 token，
   走 `misakanet_search`（`detail=compact`, `top=5`）。
   - 先用**标题原文**当 query（模拟报料者的自然写法）；
   - 对"只命中 FAQ"或"命中明显无关课"的条目，再用**canonical 短查询**复核一次
     （例：`docker exit code 137`、`firestore go omitempty not saved`）。
3. 结果按 `type` 分流：`type != "faq"` 才算课程命中；FAQ 命中（分数 18–60）**不构成覆盖**。
4. 分类与动作按 SOP §1/§2；每条动作后回执按 §3（含"匿名报料收不到通知"的渠道说明）。

### 方法本身的发现（值得单独跟进）

**把 intake 标题原文当 query，会系统性低估覆盖。** 例：`#1460` 的标题很长（"Docker build fails with exit
code 137 when using multi-stage builds…"），用它检索只召回一条 FAQ（18 分）；换成 canonical 短查询
`docker exit code 137` 就召回了真正的课程 `kubernetes-crashloopbackoff-debugging`。
→ intake 标题是**自然语言长句 + 双语混杂**，与课程标题的词面重合度低；这是检索侧的召回问题，不是缺课。
建议：把"intake 标题 → 检索 query"的规范化（抽关键词/去模板块）做成 triage 工具的一部分，否则每轮分诊
都会把伪盲区误判成真盲区。

## 已处置（本轮实际动作）

| intake | 分类 | 动作 |
|---|---|---|
| #1460 Docker build exit 137（多阶段） | **伪盲区** — 已有 `kubernetes-crashloopbackoff-debugging` | 回执指向该课 + 说明长标题导致未召回；请报料者补"构建假成功"角度的原始输出以决定是否补课 |
| #1499 葡语 roleplay 第三人称/`Ele` 错位 | **伪盲区** — 已有 `roleplay-vocative-entity-disambiguation-portuguese` | 回执指向该课（+ `roleplay-dialogue-loop-context-poisoning`），并请其提供实际错位对话样本 |
| #1501 roleplay + prompt caching 重复注入 | **伪盲区** — 已有 `roleplay-dialogue-loop-context-poisoning` | 回执指向该课（+ `character-assistant-repetition-loop`），并指出"缓存断点落在动态段落"是尚未覆盖的一层 |
| #1472 + #1473 Vertex/Gemini 模型 ID 命名 | **真盲区** | 合并转任务 **#1665**（入口 × 写法对照表 + 定位法），两条 intake 已留指向回执 |
| #1618 BigQuery 遥测静默失效 + #1619 Firestore Go `omitempty` 未落库 | **真盲区** | 合并转任务 **#1666**（"写成功但数据没到"的分层检查法），两条 intake 已留指向回执 |
| #1664 单体前端（4,909 行 app.js） | **重复** | 与 #1663 是同一代码库的两次投稿 → 留回执后关闭（保留 #1663 为主记录） |

## 仍然开放的真盲区（下一轮候选，均已确认课程 0 覆盖）

| intake | 主题 | 备注 |
|---|---|---|
| #1145 / #1146 | DSH 2.0.1 `DSH_HOME` robocopy 迁移后 profile 异常；`hindsight-memory` 插件 daemon 启动失败 | 两条都是 DSH 侧、`priority:high`，且都挂着 `good first issue`——但需要**报料者补可复现细节**才能成课（现在只有症状） |
| #1397 | 记忆摘要器用的是默认 chat 模型还是专用模型（问题类） | **question 类**：SOP §2 允许维护者直接答复即回执；不需要课程 |
| #1504 | "Mock Attribute Cascade"：新增属性访问导致既有测试崩溃 | 有机制、缺现场；适合先补一段最小复现 |
| #1548 | 角色生成 `POST /api/characters/assist/sheet` HTTP 失败 | 缺错误码/响应体，先索取 |
| #1553 | `alembic upgrade head` 失败 | **已有任务 #1652**（贡献者 TaherEzzi 在做） |
| #1555 | nano-gpt.com SSE 流式调用失败 | **已有任务 #1651** |
| #1574 | LLM 代替用户发言（god-moding） | **已有任务 #1650** |
| #1635 | LLM 成本遥测少计（`model` 列记错） | `needs-ac`：**缺的是验收标准**，不是课程——需要维护者把它写成可验收的任务或先补 AC |
| #1662 | SPA 改版（Stitch 设计）后 DOM 选择器断裂 | `auto-rejected`（antigravity/charchat 来源）：属"SOP §1 噪音"，需报料者补可复现细节才值得转课 |
| #1663 | 单体前端重构（承接 #1664 的主记录） | 同上，`auto-rejected`，等现场细节 |

## 本轮未做的事（说清楚，免得看起来像已完成）

- **没有**对 #1145/#1146/#1397/#1504/#1548/#1635/#1662/#1663 逐条回执：它们的共同缺口是**报料里没有可复现细节**，
  而按 SOP 这一步的产出应当是"向其索取细节"的模板化回复。留到下一轮一次性做，避免这里写一堆彼此重复的话。
- **没有**清理 `auto-rejected` 噪音：SOP 明确"不主动关闭"，且其中 #1553/#1555/#1574 已被 salvage 成任务。
- **没有**动 19 条以外的非 intake issue（如 #1635 之外的 `needs-ac` 项）。

## 下一轮建议顺序

1. #1397 属 question 类，**答复即回执**，成本最低 → 先清掉。
2. 对 #1145/#1146/#1504/#1548/#1662/#1663 发**同一套索取细节的模板**（要什么：命令、完整错误文本、环境、期望 vs 实际）。
3. #1635 补 AC 或转任务（它卡在"没有验收标准"）。
4. 把"intake 标题 → 检索 query 规范化"提成一条检索改进项（本轮发现，见上）。
