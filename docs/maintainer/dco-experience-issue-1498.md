# DCO 体验改进 — issue #1498 抱怨取证与方案（2026-09-06）

> 来源：[issue #1498 — Feedback from PR #1487: dsh integration tests](https://github.com/Ikalus1988/MisakaNet/issues/1498)
> 报告人：hummern（PR #1487 作者，bounty #1403 首个真实 dsh 集成测试贡献者）
> 状态：**评估完成，待拍板执行**（见 §6 分级方案）
> 相关：`handoff-2026-09-05.md`（fork DCO 等作者队列）、`docs/journey-reports/2026-07-20-uncledad96-glitch.md`

---

## 1. 抱怨原文与翻译

> *"The DCO `needs-dco` label doesn't auto-clear — even after force-pushing a signed commit, the bot's comment stayed. I had to push a new commit to trigger a fresh scan. Consider auto-rechecking on every push."*
>
> **DCO `needs-dco` 标签不会自动清除——即使 force-push 了已签名的提交，bot 的评论仍然保留。我不得不 push 一个新提交来触发重新扫描。建议每次 push 自动复查。**

其余两条反馈（非 DCO）：
1. `tests/dsh/fixtures/` 目录约定无文档，需自行推断 → 建议 CONTRIBUTING.md 补一行说明。
2. `tests/dsh/performance.test.js` 依赖未安装 dsh CLI 时用 `this.skip()` 优雅跳过，此模式未文档化。

## 2. PR #1487 时间线取证（REST API）

| 时间 (UTC) | 事件 | 证据 |
|---|---|---|
| 13:25:56 | hummern 开 PR（fork: hummern/MisakaNet，4 commits） | pulls API |
| 13:26 | 机器人（经 Ikalus1988 PAT）打 `needs-dco` 等 4 个标签 | timeline: `labeled +needs-dco` |
| 13:31 | hummern **force-push**（amend 补签） | timeline: `head_ref_force_pushed` |
| 13:34 | hummern 评论 *"Re-triggering DCO check after signoff fix."* | issue comments |
| 13:43-13:44 | 新 head 上 `dco` ✅、`audit-shape` ✅、`quality-labels` ✅ 全部通过；`audit` ❌（13:44:16） | check-runs API |
| 13:43 | hummern push 真实新提交 `52d4fe13 "Trigger fresh CI scan for PR #1487"` | commits API |
| 14:07-14:09 | 再 push 后 `audit` ✅、`dco` ✅ 全绿 | check-runs API |
| 14:58 | 第三次 force-push（补 fixtures 目录） | timeline |
| 16:47 | Ikalus1988 手动合并——**合并时 `needs-dco` 标签仍在 PR 上** | pulls API labels: `[..., 'needs-dco', 'shape-safe']` |

**关键事实**：
- 全流程**从未出现 `unlabeled -needs-dco` 事件**——标签从 13:26 一直挂到合并（3h21m），即使最终 head 上 `dco` 检查全绿。
- 贡献者体验到的"必须 push 新提交才能触发扫描"是**表象误读**：每次 push（含 force-push）都会重跑 workflow；真正没被清除的是**标签与历史评论**，导致"红标/红评 vs 绿检查"的自相矛盾界面。
- #1487 是 fork PR：`checks.create`（'DCO / Signed-off-by'）与 `gh pr comment`（REGULATORY BLOCK / audit 报告）在 fork 上**静默失败**（2>/dev/null），贡献者唯一看到的 bot 痕迹 = welcome 评论 + `needs-dco` 标签 + 检查结果。

## 3. 根因分析（代码级）

### 3.1 `needs-dco` 标签是"只加不删"的单向门闩（核心缺陷）

| 文件 | 行为 |
|---|---|
| `.github/workflows/pr-shape-guard.yml:206-214`（`pull_request_target: opened/synchronize/reopened`） | **只 add**：`if (!hasDCO) toAdd.push('needs-dco')`——通过时**不** `toRemove` |
| `.github/workflows/pr-quality-gate.yml:71`（`check_run` + `synchronize`） | 只把 `existing.includes('needs-dco')` 当 `ready-to-merge` 的**阻断条件**，自身从不 remove 该标签 |
| 全仓 grep | **没有任何一处 `removeLabel('needs-dco')`**（含 dco-audit action） |

后果：任何 PR 只要曾经有过一个未签名提交，标签就永久残留。`pr-quality-gate` 又把标签存在当作硬门禁 → `ready-to-merge` 永远打不上 → 合并依赖维护者人工判断（main 无强制 CI 门禁，`#1487` 正是人工合并）。

### 3.2 三套 DCO 实现语义不一致（产生误判源）

| 实现 | 扫描范围 | 匹配规则 |
|---|---|---|
| `dco-check.yml` | `git log upstream/main..HEAD`（**含 merge 提交**） | `grep -qi 'Signed-off-by:'` |
| `.github/actions/dco-audit/action.yml`（pr-checks 用） | `git rev-list --no-merges`（**排除 merge**） | `grep -qE 'Signed-off-by: .* <.*>'` |
| `pr-shape-guard.yml` Gate 4 | REST `listCommits`（**含 merge 提交**） | `.includes('Signed-off-by:')` |

贡献者 `git merge main` 产生的**未签名 merge 提交**会在 shape-guard/dco-check 被判失败，而权威 audit 判通过 → 又一个标签误挂来源（#1411/#1400 的 upstream merge 提交恰好都带签，故未触发）。

### 3.3 失败态评论"只追加不清扫"

- `dco-audit` 每次失败都 `gh pr comment` 新发一条 **REGULATORY BLOCK**（无 marker、无去重/更新/删除）。
- pr-checks 的 Audit Report 每次 run 追加新评论，旧 ❌ 报告永不更新。
- 修复后评论区残留多条红色指令，与绿检查并存 → 新贡献者无所适从（journey-report 2026-07-20 已记录同类困惑）。

### 3.4 维护者侧噪声叠加

- `scripts/maintainer_review_queue.py:66` 把 `needs-dco` 标签直接映射为动作 `request-dco-signoff` → **标签失实 = 队列误判 = 已就绪 PR 被当成"等作者"**。
- 维护者 handoff 里 release PR 流程**手工**记录"去掉 pending/needs-dco"（`handoff-2026-09-05.md` §63）——证明人肉清标签已是日常负担。

## 4. 影响评估（量化）

### 4.1 对贡献者（首 PR 漏斗，最痛）

| 影响 | 证据 |
|---|---|
| 界面状态矛盾：绿检查 + 红 `needs-dco` 标签 → "我的 PR 到底行不行？" | #1487 合并时标签仍在 |
| 被迫用"加空提交"这类**错误工作流**绕过问题（`52d4fe13 "Trigger fresh CI scan"`） | #1487 commits |
| 首 PR 贡献者需人工联系维护者才能推进（本来应全自动） | #1487 由 Ikalus1988 人工合并 |
| 历史已记录同类挫败：agent 新贡献者把 403/标签噪音误读为"我内容错了" | `docs/blog/2026-07-20-agent-first-contrib-path.md`、`docs/journey-reports/2026-07-20-uncledad96-glitch.md` |
| Windows 用户 DCO 报错已多到沉淀成课程（多语言） | `lessons/contrib/error-dco-signoff-windows.md` |

### 4.2 对维护者 / 自动化（静默成本）

| 指标 | 数值 | 说明 |
|---|---|---|
| 已合并 PR 中仍挂 `needs-dco` | **64 / 415 ≈ 15.4%** | 标签已失去实时语义，等于"曾碰过 DCO"的历史标记 |
| 当前开放 PR 挂 `needs-dco` | **3（#1400/#1411/#1461）** | 逐一核对 commits：**3 个全部 0 未签名提交**——100% 误挂 |
| 曾挂过该标签的 PR 总数 | 302 | 其中大量在作者修复后被继续标红 |
| 队列误判 | zsxh1990 的 #1400/#1411/#1461 在 handoff 中被记为"fork DCO 等作者补签"，实际早已签好 | 阻塞合并多日（#1400 自 8/29 起） |

### 4.3 结论

这不是单次事件，而是**标签状态机缺陷**（3.1）+ **语义分裂**（3.2）+ **评论卫生缺失**（3.3）叠加的结构性问题。对"agent-first 贡献"定位的项目伤害尤其大：agent 贡献者（占本仓多数）按红/绿信号决策，红标不消会直接打断其自动闭环（retry 循环 / 放弃 / 无效 push），正是 #1498 抱怨的体验。

## 5. 目标行为（修复后）

1. **每次 push（含 force-push）自动重扫**：DCO 通过 → 立刻摘掉 `needs-dco`；失败 → 保留/打上。
2. **单一事实源**：标签与评论严格跟随 `dco-check` 的结论；三套检查的提交范围统一为 `--no-merges`。
3. **评论就地更新**：失败评论带 marker，状态翻转时更新为"✅ 已通过"或删除，不堆叠。
4. **队列可信**：`ready-to-merge` 由 DCO 检查结论驱动，而非残留标签。
5. **文档承诺真实**：CONTRIBUTING.md 明说"补签 force-push 后标签自动清除，无需新提交"。

## 6. 改进方案（分级）

### P0 止血（<1h，建议立即做）
- **backfill**：对 3 个开放 PR（#1400/#1411/#1461）与 64 个已合并 PR 用 REST 核对 commits（no-merges）后移除失实 `needs-dco`（开放 PR 可即刻解锁合并；已合并属数据卫生）。→ 一次性脚本 `scripts/dco_label_backfill.py` 或 workflow_dispatch。

### P1 根治（核心，随 PR 合入）
1. **`pr-shape-guard.yml` Gate 4**：`hasDCO` 为真时 `toRemove.push('needs-dco')`；commit 范围对齐 dco-audit——跳过 merge 提交（`c.parents.length <= 1` 再判 sign-off）。shape-guard 走 `pull_request_target` + SHELDON_PAT，fork PR 也能写标签 → **自动清除在每次 push 生效**（正是 #1498 诉求）。
2. **`pr-quality-gate.yml`**：阻断条件从"标签存在"改为"DCO 检查结论"——解析 checkRuns 中 `dco`/`DCO / Signed-off-by` 的 conclusion；`action_required/failure` 才算阻断；另加 `toRemove.push('needs-dco')` 兜底（防 shape-guard 与 quality-gate 并发竞态）。
3. **评论就地更新**：`dco-audit` 与 pr-checks 报告引入 marker（如 `<!-- misakanet-dco-block -->`），重跑时 updateComment 替代 createComment（shape-guard 失败评论已用此模式，直接复用）。fork PR 上注释/检查创建本就静默失败——在 pr-checks 报告里改为非静默告警或 README 说明。

### P2 语义与文档
4. **统一检查语义**：`dco-check.yml` 与 shape-guard 一律 `--no-merges`（merge 提交免签是社区惯例，与 dco-audit 一致）。
5. **CONTRIBUTING.md DCO 节**：补"补签 + force-push 后标签/评论会自动清除、无需新提交；等待数分钟"；新增 `tests/dsh/fixtures/README.md` 说明 + `this.skip()` 优雅跳过模式（回应 #1498 其余两点）。
6. **`docs/label-system.md`**：`needs-dco` 行注明"每次 push 自动重扫、通过即清除"。
7. **`pr-welcome.yml`**：欢迎评论"CI runs automatically once DCO passes"改为在标签真实自动清除后成立；或将 DCO 指引改为条件式（有 `needs-dco` 才讲）。
8. **`scripts/maintainer_review_queue.py:66`**：动作改为"核对 commits 后再决定 request-dco-signoff"，或依赖 P1 后标签可信度直接使用。

### P3 观测
9. 可选：dco-check 结论 → 打 `ready-to-merge` 前置条件已有 quality-gate 处理；无需新增。
10. 追踪：1 个发布周期后复查"合并时仍挂 needs-dco 的 PR 数"（目标 0）与开放 PR 误挂率（目标 0）。

## 7. 验证与风险

- **验证**：合并后开一个测试 PR（先推未签名提交 → 看 `needs-dco` 打上；amend 补签 force-push → 看自动摘除 + 评论翻转 ✅）；复查 #1487/#1400/#1411/#1461 标签清理。
- **风险**：
  - shape-guard 是 `pull_request_target`（信任何人提交的代码）——只加"删标签"不改 checkout 逻辑，风险不变（维持现状审计）。
  - `--no-merges` 语义变更会让少数"merge 提交未签"的 PR 从红变绿——符合社区惯例，需在 changelog/文档注明。
  - 并发竞态（shape-guard vs quality-gate 同写标签）用幂等 remove + 双保险缓解。

## 8. 附：本次取证所用数据（均来自 GitHub REST，2026-09-06）

```
merged PR 总数                                  415
merged 且仍挂 needs-dco                         64 (15.4%)
曾挂 needs-dco 的 PR（open+closed）             302
当前 open 且挂 needs-dco                         3 → commits 核对全部已签名（100% 误挂）
#1487 标签时间线      labeled 13:26 → merged 16:47，全程无 unlabeled
#1487 最终 head       dco ✅ audit ✅ quality-labels ✅ 但 needs-dco 仍在
```

---
*报告人视角为维护者侧取证；改进方案待拍板后以独立 PR 落地（遵循 Shape Guard 规则：工作流文件改动走 `workflow-change` 标签 + 人工 review）。*
