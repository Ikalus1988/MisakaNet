# Intake Triage SOP（维护者）

> 适用：所有从外部通道进来的报料类 issue——`[Intake]` / `[Question]` /
> `[Lesson]`——包括经远程 MCP 匿名提交（`misakanet_submit_intake`）自动开的 issue。
> 目的：**每条报料都有确定的归宿与回执**，外部贡献者能感知自己的贡献被采纳。

## 1. 分类（每条 intake 走其一）

| 类别 | 判据 | 归宿 |
|---|---|---|
| 真 bug / 服务缺陷 | 可复现、影响用户 | 立修（P0 优先），修复后按 §3 回执 |
| 真盲区（仓库无相关 lesson） | 检索确认 0 覆盖 | 转 lesson 任务或自家补课 |
| 伪盲区（已有 lesson 但没召回） | 仓库有但 gap 记录出现 | 修召回/索引（**不要写重复课**），引用既有 lesson id |
| 已知/重复 | 已有 issue/lesson | duplicate 关闭 + 指向原项 |
| 噪音 | 服务端已 `auto-rejected` | 不主动关闭；批量清理时按 salvage 评估 |

> 判定"真盲区 vs 伪盲区"必须先检索仓库（`search_knowledge.py` / lessons 目录），
> 2026-09-07 的 KV 分析显示 19 条 gap 里有 2 条是召回缺陷而非缺课。

## 2. 处置动作

- **修复类**：开 PR（引用 issue），合并后 issue 由 `Fixes #N` 自动关——**自动关不等于完成**，见 §3。
- **lesson 类**：走 lesson-gate（evidence_level + provenance），合入后关 issue。
- **question 类**：维护者直接在 issue 内答复（**答复即回执**），必要时沉淀进 FAQ/lesson。
- **服务端 auto-rejected 噪音**：保留标签，不占用维护者时间。

## 3. 铁律：修复/答复后必须给报料者回执（致谢）

**无论 issue 是否被 `Fixes` 自动关闭，都必须在该 issue 留一条回执评论。**

回执模板要点：

1. **致谢报料者**（点名来源标识，如 `dsh agent (charchat workspace)`）
2. **根因一句话**
3. **修复/答复**：PR + merge sha（或答复结论）
4. **验证方式**：报料者自己能跑什么命令确认（如重跑 `misakanet_search(...)`）
5. **回执渠道说明**：匿名 MCP 报料者收不到 GitHub 通知——公开留档，并告知
   `misakanet_register` 可注册以获得回执通道

> **反例（2026-09-10，issue #1605）**：DSH agent 报料 `misakanet_search` 输出校验失败
> （高价值 P0），维护者 30 分钟内修复并部署，但 issue 被 `Fixes` 自动关闭且**没有任何
> 致谢**——报料者（匿名）永远不会知道自己的报料已被采纳。维护者事后手工补回执评论。
> 教训：**"修完自动关"会让飞轮断在最后一环。**

自动回执机制见 #1528（bounty，实现前由人工执行本条）。

## 4. 与自动化管线的关系

| 管线 | 职责 | 与 SOP 的接口 |
|---|---|---|
| 服务端 canonical 去重（#1526，已交付）| 提交时查重，命中已有课不开 issue | 减少伪盲区进入 triage |
| intake-bot 外部试点（#1550）| 外部仓库 CI 失败 → 建议/intake | 报料来源；回执靠 §3 |
| `workers/register-proxy-sw.js` `gap:*` | 记录检索无结果的查询 | 定期分析（gap→lesson 生命周期 #1586 已交付） |
| failure_harvest / watcher（#1545/#1597）| 失败事件 → lesson 草稿 | 草稿仍需人工 triage |

## 5. 参考

- 回执机制 bounty：#1528（含 2026-09-10 真实案例评论）
- 外部试点征集（长期）：#1550
- KV/邮件数据分析方法与结论：`reports/user_analysis_2026-09-07/`（结论已转 issue #1562-1572）
