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

**这条铁律的"提醒"半边已经有机制**（2026-09-25 接上，#2040）：`intake-salvage-digest.yml` 每天
08:00 UTC 跑 `scripts/done_but_open.py`，找出「课程已经在 `main` 上、issue 还开着」的 intake 并写进
`salvage-digest` 议题（清单为空时**不发言**，只写 step summary）。它**只报告**：不代替人写回执、
也不关单——§2 已经把"服务端 auto-rejected 的噪音不主动关闭"写死了，而"按文件名匹配就自动关"正是本
节反例的机器版本。人要做的仍然是那 5 条模板要点。

### 3.1 怎么真的把一条 question 答完（2026-09-25 按此流程走过 #2099 与 #1724）

§2 说"question 类：维护者直接在 issue 内答复"——下面是把这句话**执行完**的步骤，
每一步都有一句话说明它为什么必须是这一步。完整闭环的意义在于：**答复一次 = 之后同类问题自动被回答**，
所以积压不是"8 条/天 vs 人工答 1 条/天"的线性竞赛，而是"每簇答一次"。

```bash
# 0) 先检索（SOP §1 要求的"确认 0 覆盖"）。用**生产检索路径**，不要用本地 Python 引擎：
#    本地 `misakanet/search/engine.py` 的 _rank_docs 是无下限的原始打分器，实测把
#    "knitting pattern stitch count" 打到 1.007、而 "pip install timeout behind corporate proxy" 只有 0.905
#    ——用它判"伪盲区"会把无关问题判成"已有覆盖"。生产路径 = worker 的 BM25 + IDF 加权相关性下限。
#    no_match → 真盲区（要写新知识）；有 lesson 命中 → 伪盲区（修召回，**不要写重复课**）。

# 1) 写答复。三件事同时满足：
#    (a) **必须**含 ANSWER_MARKERS 之一：`<!-- misakanet-answer -->`（推荐，对读者不可见）
#        或 `## ✅ Answered` / `## [ANSWER]`。没有标记 = 同步脚本找不到它 = D1 里没有这行 = FAQ 不会回答任何人。
#    (b) **不能**含 AUTOMATED_MARKERS 任何一个（`<!-- misakanet-intake-triage -->`、
#        `<!-- misakanet-intake-question -->`、`## [QUESTION]`、`## [REJECTED]` …）。
#        脚本的判据是"有 answer 标记 **且** 无 bot 标记"——粘错一条 bot 评论就会被静默跳过。
#    (c) §3 的 5 条：点名致谢报料来源 / 根因或结论 / 答复本体 / **报料者自己能跑的验证命令** / 回执渠道说明。
gh issue comment <N> --body-file answer.md          # 或 POST /repos/{o}/{r}/issues/<N>/comments

# 2) 打 answered 标签 —— 这一步**就是**闭环开关：`issues: labeled` 事件会触发单条同步。
gh issue edit <N> --add-label answered

# 3) 关单（`closed` + 有 answered 标签会再触发一次；upsert 幂等，跑两次无害）
gh issue close <N> --reason completed

# 4) **读日志，不要看绿点**。`Sync single question answer to D1` 这一步在"没找到答复评论"时
#    也是 success（脚本只 print 并 return 0）。要看的是这一行：
gh run list --workflow=sync-question-answers.yml -L 3
gh run view <run-id> --log | grep -E "#<N>|upserted|no answer comment"
#    期望：`#<N>: answered row upserted`；若是 `no answer comment found (skipped)` → 回第 1 步查标记。

# 5) 验证闭环两端（都在线上、都别只看自己的仓）：
#    (a) 检索侧：misakanet_search(query="...") 期望出现 `faq-issue-<N>`（type=faq，且 no_match 被抑制）
#    (b) 回拉侧：用**完全相同的 problem 文本**重新 submit_intake(kind="question", ...)
#        期望 {"submitted": false, "duplicate": true, "answered": true, "intake_id": "issue-<N>", "answer": "..."}
#        —— 且**不会**新建 issue。这是报料者拿到答复的官方路径。
```

**四个坑（都实测踩过）：**

1. **bot 的 intake 评论也带标记，别把它们当成答复**。每条 intake 会收到 2 条机器评论
   （`<!-- misakanet-intake-triage -->` 与 `<!-- misakanet-intake-question -->`）；它们**故意**带 bot 标记，
   正是为了不被当成维护者答复。
2. **`ANSWER_MARKERS` 混了两类东西**：`<!-- misakanet-answer -->` 是**给脚本的信号**（issue 里谁也看不见），
   而 `## ✅ Answered` / `## [ANSWER]` 是维护者写的**可见标题**（是内容）。存进 D1 的是评论原文，
   而 D1 那行会被**逐字**返回给 agent（`type=faq` 与回拉路径都是），所以只有 HTML 注释那一类会被剥掉——
   见 #2271（剥可见标题 = 改答复）。
3. **本地跑不了 `--dry-run`**：它会查 D1 的 `questions` 表，需要 Cloudflare 凭据。所以"写进去了吗"
   只能靠第 4 步的日志 + 第 5 步的线上验证。
4. **读 job 日志要处理 302**：`/actions/jobs/{id}/logs` 会 302 到签名 URL，且**签名 URL 上不能带
   `Authorization` 头**（带了会被拒）。先取 `Location` 再裸取。

**一个自愈性质**：`upsert_answered` 是 upsert，且每天 07:20 UTC 有批量同步。所以"答复已发但某一轮同步
写坏了"会在下一轮被覆盖修正——不需要为了修一行数据去手工触发什么。

## 4. 与自动化管线的关系

| 管线 | 职责 | 与 SOP 的接口 |
|---|---|---|
| 服务端 canonical 去重（#1526，已交付）| 提交时查重，命中已有课不开 issue | 减少伪盲区进入 triage |
| intake-bot 外部试点（#1550）| 外部仓库 CI 失败 → 建议/intake | 报料来源；回执靠 §3 |
| `workers/register-proxy-sw.js` `gap:*` | 记录检索无结果的查询 | 定期分析（gap→lesson 生命周期 #1586 已交付） |
| failure_harvest / watcher（#1545/#1597）| 失败事件 → lesson 草稿 | 草稿仍需人工 triage |
| `intake-salvage-digest.yml` + `scripts/done_but_open.py`（#2040，2026-09-25 接上）| 每天找出「工作已在 `main`、issue 还开着」的 intake，非空时写进 digest 议题 | **只提醒，不代替 §3**：回执与关单仍由人做 |

## 5. 参考

- 回执机制 bounty：#1528（含 2026-09-10 真实案例评论）
- 外部试点征集（长期）：#1550
- KV/邮件数据分析方法与结论：`reports/user_analysis_2026-09-07/`（结论已转 issue #1562-1572）


---

## 附则：可复跑证据（#2041，2026-09-21 增补）

**「做完了」不等于「可复跑」。** 与 §3 的回执铁律并列，本仓对任何"完成"声明要求一件同样具体的东西：
**跑什么命令、看什么输出**。

- 提交方（PR / field report / 悬赏交付）必须给出命令与输出摘录。缺这一项时，维护者**不要**替它补，
  而是按"证据不成立"处理，并在回执里写清回主线的路。
- 端点必须是 `misakanet.org`；引用工具输出要与真实返回同形（检索返回 `results`/`no_match` 的 JSON
  信封，不是散文）。
- **没有运行就说没有运行。** 「只检查了本地配置、未发起运行时调用」是合格的回答；把没做的运行写成
  已验证不是——2026-09-21 有三个 PR 因此被关闭，其中一个声称的可复跑证据里 `tools/list` 返回 1 个工具，
  而线上是 7 个。
- 这条与 §3 的分工：§3 管**我们给报料者的回执**，本条管**投稿者给自己的证据**。两边缺一个，闭环就断。
