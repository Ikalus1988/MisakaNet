# 研究：课程反馈 action 飞轮化 + 任务下发方案（2026-09-07）

> 目标：MisakaNet 的"CI 失败 → 课程建议/intake"反馈闭环，从**本仓自用**变成**外部仓库
> （含 zsxh）可复用**的 action，形成"复用越多 → intake/issue 越多 → 任务越多 → lesson 越多 →
> 命中越好 → 复用越多"的飞轮；达标后开赏金 issue 下发，验收 = ≥50 样本完整报告。
> 本文先回答"现状还差什么、如何下发"，不改代码（前置修复范围待用户确认）。

---

## 1. 飞轮机制（目标形态）

```
外部仓库（zsxh 等）复用 action
   │  CI 失败（真实运行时错误）
   ▼
misaka-intake-bot action（suggest-and-intake）
   │  ① 本地决策：hit / intake / ignore（stack-aware + noise + 阈值）
   │  ② hit → PR/issue 评论课程建议（建设性，suggest-only）
   │  ③ intake（novel + 达标）→ 匿名 MCP misakanet_submit_intake
   ▼
misakanet.org worker
   │  ④ canonical 去重（已有 #1526 findCoveringLesson）→ 重复回 already_have
   │  ⑤ 新颖 → 自动在 Ikalus1988/MisakaNet 建 [Intake]/[Question] issue
   ▼
MisakaNet 仓
   │  ⑥ issue 进 triage → bounty/agent 认领 → lesson 转正 → 回执（#1528）
   ▼
语料变厚 → 命中率↑（现 0.489 → 目标 ≥0.6）→ 复用价值↑ → 更多外部仓库接入
```

**关键事实（已核实）**：
- `misakanet_submit_intake` 是**开放无鉴权** MCP（`https://misakanet.org/mcp`），
  worker 侧已实现：canonical 去重（#1526）→ 新颖即建 issue（`[Intake]`/`[Question]` + labels）。
  → 外部自动提交 → 自动在我们仓建 issue 的通道**已存在**。
- `scripts/intake_bot.py` 决策完全远程化：语料 `GET /api/lessons`（免注册）+ 提交走 MCP。
- `intake-bot` 决策基准（#1543）CI-gated：hit_precision 1.00 / hit_recall 1.00 / noise 1.00
  （suggest-only，sim=0.45）——质量有量化护栏。

## 2. 现状 gap（下发前必须解决）

| # | Gap | 影响 | 修复方向 |
|---|---|---|---|
| G1 | **action 不 self-contained**：`.github/actions/misaka-intake-bot/action.yml` 依赖调用方仓库有 `scripts/intake_bot.py`（找不到即 skip） | 外部仓库 `uses:` 后**根本不跑** | action 内加一步 `checkout Ikalus1988/MisakaNet`（仅 scripts/）或改用 pip 分发；zsxh 已打包但未解决此点 |
| G2 | **无样本采集/报告通道**：外部跑完没有落盘样本、没有统一上报格式 | 无法验收"≥50 样本报告" | action 增加 `report` 输出（decision/fingerprint/error/lesson/issue 的 NDJSON 累积），外部可 PR 回传或 issue 附报告 |
| G3 | **无外部接入文档/模板** | 外部用户不知怎么接 | 写 `EXTERNAL-USAGE.md`：3 行 workflow 模板 + 白名单/配额说明 |
| G4 | **无"达标判定"的观测**：本仓 dogfood 没有公开效果数据 | 无法证明"达到预期"再下发 | 先在本仓用真实 CI 失败跑 N 样本，出一份 dogfood 报告（同验收格式） |
| G5 | 外部 intake 的**配额/信任**未定 | 滥用风险 | 沿用闸5（source token bucket）+ 服务端双阶段兜底（已有） |

## 3. 任务下发形态（建议）

**时机**：G1-G4 完成后（action 可被外部真正复用 + 有样本通道 + 有 dogfood 基线），再开赏金。

**赏金 issue 模板**（达标后才创建，内容如下草稿）：

---
title: `[Bounty] 复用 misaka-intake-bot 于外部仓库并交付 ≥50 样本报告`
labels: `bounty, ready, area:workflow`

**验收标准（AC）**
1. 在**你自己的真实仓库**（非 fork MisakaNet）接入 `Ikalus1988/MisakaNet/.github/actions/misaka-intake-bot@main`
   （或发布版 tag），mode=suggest-and-intake。
2. 交付**完整报告**（≥50 个 CI 失败样本），每样本含：仓库/workflow、错误签名（脱敏）、
   decision（hit/intake/ignore）、若 hit → 课程 id/相似度与是否采纳；若 intake → issue 链接。
3. 报告须含**自动生成的产物清单**：本 action 在你的仓库自动创建的 lesson/question intake
   （= 在我们仓自动开的 issue 列表），并注明哪些已转正 lesson（若有）。
4. 质量门槛：报告中 hit 建议**人工核对** ≥70% 采纳/认为对症（suggest-only 语义）；intake 样本
   无重复指纹、无纯噪音（URL/无上下文）；全部样本经 redaction 无凭据泄露。
5. 报告以 PR 提交至 `docs/external-pilots/<repo>-<date>.md`（含 NDJSON 样本附件）或附在 issue。
6. 额外加分：intake 转正 ≥1 条 lesson；命中→修复闭环证据（CI 由红转绿）。

**奖励**：按 bounty 规则结算 + leaderboard；转正 lesson 另有贡献积分。

---

**样本量的现实性评估**（用户拍 50）：若外部仓库 CI 失败频率低（每周几次），50 样本需数月——
建议 AC 放宽为"≥50 样本 **或** 持续 2-4 周累计"；或引导接入**报错面大**的仓库（爬虫/多步 CI/
多语言矩阵），其单周 CI 失败可达数十条。可同时开多个试点（zsxh + 1-2 个爬虫类）。

## 4. 报告格式（统一 schema，供 G2 实现）

```json
{"repo": "owner/name", "workflow": "ci.yml", "ts": "ISO",
 "error_sig": "git: fatal: could not read Username ...",   // 脱敏后
 "stack": ["git"], "decision": "hit|intake|ignore",
 "lesson_id": "git-credential-helper-gh-path-mismatch", "sim": 0.87, "adopted": true,
 "intake_issue": "https://github.com/Ikalus1988/MisakaNet/issues/1234",
 "source": "external-pilot:owner/name"}
```

## 5. 建议的执行顺序（等用户拍板）

1. **P0 前置修复**（本会话可做，~1 次提交）：G1 action 自包含化（checkout 依赖 or 远程直调）
   + G4 本仓 dogfood 基线报告（用真实 CI 失败样本先跑 ≥20 验证 action 可用）。
2. **P1**：G2 样本累积输出 + G3 外部接入文档。
3. **P2**：达标后按 §3 模板开赏金 issue（含 zsxh 在内公示）。
4. 长期：转换回执（#1528，已在 #1544 外部 PR 中实现待决策）关闭反馈环。

---
*研究完成于 2026-09-07 维护会话；未改代码。待用户确认 P0 前置修复范围后动工。*
