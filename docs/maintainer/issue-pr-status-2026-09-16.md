# MisakaNet issue / PR 现状报告（2026-09-16）

> 本报告全部数字来自 GitHub REST API 的机器读取，快照时间 **2026-09-16T14:59Z**（下文所有「年龄 / 天数」都相对该时刻）。
> 凡是从 API 数据推导不出来的一律写 **未获取**，不做估算。
> 复现方式见文末「如何复现」。

## 0. 一句话结论

仓库整体在**高产运行**（近 7 天合并 86 个 PR、创建 58 个 issue），
但 **14 个开放 PR 里只有 2 个是「现在就能合并」**，
其余 12 个卡在两类机械性问题上（DCO 签核 / 已请求修改），
这才是当前真正的瓶颈——不是 issue 分诊量，而是 **PR 收口**。

---

## 1. 开放 PR（共 14 个）

### 1.1 按作者分组

| 作者 | 开放 PR 数 | PR 编号 |
|---|---|---|
| `zsxh1990` | 6 | #1701, #1713, #1714, #1715, #1716, #1761 |
| `huiyuansun28-cmyk` | 5 | #1746, #1747, #1748, #1749, #1750 |
| `s6pa1rta3n-lab` | 1 | #1544 |
| `TaherEzzi` | 1 | #1656 |
| `2lll5` | 1 | #1674 |
| **合计** | **14** | |

### 1.2 逐个明细（年龄 = 相对 2026-09-16T14:59Z）

检查列格式：`通过/跳过/失败`（来自 `/commits/{sha}/check-runs`）。

| # | 标题（截断） | 作者 | 创建 | 年龄(天) | mergeable_state | draft | 改动文件 | 检查 | 阻塞原因 |
|---|---|---|---|---|---|---|---|---|---|
| 1544 | feat: intake conversion receipt — notify source when its intake becomes a lesson | s6pa1rta3n-lab | 2026-09-07 | 8.9 | `dirty` | **是** | 17 | 18/4/0 | **合并冲突 + draft 未转正** |
| 1656 | fix: resolve #1652 — 把 intake #1553 转成课程 | TaherEzzi | 2026-09-13 | 3.1 | `unstable` | 否 | 2 | 19/1/4 | **检查失败** `dco`,`audit`,`gate`,`auto-merge` + **2 次 CHANGES_REQUESTED** |
| 1674 | feat: add intake coverage triage helper (#1673) | 2lll5 | 2026-09-14 | 2.5 | `clean` | 否 | 2 | 19/2/0 | 无（**可合并**） |
| 1701 | fix(guard): exempt test files from markdown leak detection (Rule 3) | zsxh1990 | 2026-09-15 | 1.3 | `clean` | 否 | 1 | 19/1/0 | 无（**可合并**） |
| 1713 | feat(lesson): alembic upgrade failure diagnosis | zsxh1990 | 2026-09-15 | 1.2 | `clean` | 否 | 1 | 23/1/0 | 仅**评审**：1 次 CHANGES_REQUESTED |
| 1714 | feat(lesson): SSE streaming failure via proxy or client parsing | zsxh1990 | 2026-09-15 | 1.2 | `clean` | 否 | 1 | 23/1/0 | 仅**评审**：1 次 CHANGES_REQUESTED |
| 1715 | feat(lesson): Vertex AI vs Gemini model ID naming conventions | zsxh1990 | 2026-09-15 | 1.2 | `clean` | 否 | 1 | 23/1/0 | 仅**评审**：1 次 CHANGES_REQUESTED |
| 1716 | feat(lesson): write success but data missing — silent failures | zsxh1990 | 2026-09-15 | 1.2 | `clean` | 否 | 1 | 23/1/0 | 仅**评审**：1 次 CHANGES_REQUESTED |
| 1746 | Add lesson: Gemini model ID naming and parameter constraints | huiyuansun28-cmyk | 2026-09-16 | 0.6 | `unstable` | 否 | 1 | 20/1/3 | **检查失败** `audit`,`gate`,`dco` |
| 1747 | Add lesson: LLM cost telemetry undercounting | huiyuansun28-cmyk | 2026-09-16 | 0.6 | `unstable` | 否 | 1 | 20/1/3 | **检查失败** `audit`,`gate`,`dco` |
| 1748 | Add lesson: Silent data loss in Google Cloud | huiyuansun28-cmyk | 2026-09-16 | 0.6 | `unstable` | 否 | 1 | 20/1/3 | **检查失败** `audit`,`gate`,`dco` |
| 1749 | Add lesson: NPC dispatch and speaker/location disambiguation | huiyuansun28-cmyk | 2026-09-16 | 0.6 | `unstable` | 否 | 1 | 20/1/3 | **检查失败** `audit`,`gate`,`dco` |
| 1750 | Add lesson: LLM god-moding prevention in roleplay | huiyuansun28-cmyk | 2026-09-16 | 0.6 | `unstable` | 否 | 1 | 20/1/3 | **检查失败** `audit`,`gate`,`dco` |
| 1761 | docs: misakanet-setup v0.5.1 architecture review + macOS test report | zsxh1990 | 2026-09-16 | 0.1 | `clean` | 否 | 1 | 20/2/0 | 仅**评审**：1 次 CHANGES_REQUESTED |

### 1.3 阻塞归因汇总

| 阻塞类型 | PR 数 | PR 编号 |
|---|---|---|
| 无需处理，**随时可合并** | 2 | #1674, #1701 |
| 仅被评审卡住（检查全绿） | 5 | #1713, #1714, #1715, #1716, #1761 |
| 检查失败（`dco` / `audit` / `gate`） | 6 | #1656, #1746, #1747, #1748, #1749, #1750 |
| 合并冲突 + draft | 1 | #1544 |
| **合计** | **14** | |

**失败的检查名清单**：`dco`、`audit`、`gate`（另 #1656 还有 `auto-merge`）。
其中可核验的具体原因只有 #1746 拿到注解：`audit` 检查的注解写着 **"DCO audit failed"**，
即 **缺少 `Signed-off-by:` 签核**；#1656 的注解同样是 **"DCO audit failed"**。
其余检查失败的**具体日志文本未获取**（check-run 的 `output.summary` 为空，需读 Actions 日志）。

**评审状态**：只有 3 个 PR 有评审记录，全部来自维护者 `Ikalus1988`，且全部为 `CHANGES_REQUESTED`：

- #1656：2 次 CHANGES_REQUESTED（2026-09-13、2026-09-16），正文明确指出唯一提交缺 `Signed-off-by:`
- #1713、#1714、#1715、#1716：#1714–#1716 的评审正文写「Same blocker as #1713，请照 #1713 的四行修复」，即**同一处 `provenance.source` 写法问题**
- #1761：1 次 CHANGES_REQUESTED
- 其余 11 个 PR **没有任何评审**（未获取评审意见）

**值得注意**：#1713–#1716（zsxh1990）与 #1746–#1750（huiyuansun28-cmyk）**在抢同一批 bounty**——
见 §4 第 5–7 条的对照关系，存在重复劳动。

---

## 2. 开放 issue（共 43 个）

- `/issues?state=open` 返回 57 条，其中 14 条带 `pull_request` 字段（是 PR，已剔除）→ **真实开放 issue = 43**
- 全量 issue（`state=all`）**661** 条，其中开放 43、已关 618
- 开放 issue **无一是无标签的**（未标注数 = 0）

### 2.1 开放 issue 标签分布（一个 issue 可多标签）

| 标签 | 数量 | | 标签 | 数量 |
|---|---|---|---|---|
| `ready` | 29 | | `needs-ac` | 9 |
| `agent-friendly` | 28 | | `area:core` | 9 |
| `intake` | 22 | | `priority:medium` | 8 |
| `mcp-intake` | 22 | | **`auto-rejected`** | **6** |
| `needs-human-review` | 18 | | **`needs-salvage`** | **6** |
| `pending-review` | 17 | | `type:question` | 4 |
| `good first issue` | 17 | | `area:lessons` | 4 |
| `priority:high` | 16 | | `area:scripts` | 3 |
| **`bounty`** | **14** | | `question` | 2 |
| `zero-bounty` | 13 | | `lesson-submission` | 2 |
| `type:bug` | 13 | | `area:workflow` | 2 |
| `help wanted` | 12 | | `priority:low` | 1 |

（低频标签各 1–2 个：`status: competition` 2、`bug` 2、`salvage-digest` 1、`type:feature` 1、
`enhancement` 1、`activation` 1、`registered` 1、`roadmap` 1、`status:competition` 1、`onboarding` 1、`stale` 1。）

### 2.2 指定标签族的「开放 / 历史累计」对照

| 标签族 | 当前开放 | 历史累计 |
|---|---|---|
| `intake` | 22 | 105 |
| `mcp-intake` | 22 | 105 |
| `pending-review` | 17 | 未获取 |
| `auto-rejected` | 6 | 21 |
| `needs-salvage` | 6 | 21 |
| `question` + `type:question` | 2 + 4 | 13 |
| `bounty` | 14 | 122 |
| `good first issue` | 17 | 158 |
| `priority:high` | 16 | 未获取 |
| `priority:medium` | 8 | 未获取 |
| `priority:low` | 1 | 未获取 |
| `priority:*` 合计 | **25** | 未获取 |

> `intake` 与 `mcp-intake` 的开放数、累计数**完全相等**（22 / 105），
> 说明这两个标签目前是**成对打上的**，没有只带其一的 issue。

**重要发现**：`auto-rejected` 的 6 个开放 issue **全部同时带 `needs-salvage`**（6 = 6），
即「自动拒绝」并未直接关闭，而是转成**需要人工打捞**的待办。

---

## 3. intake 与整体流量（时间维度）

窗口相对快照时刻 2026-09-16T14:59Z。数量来自 `/search/issues` 的 `created:>=` / `merged:>=` 过滤。

### 3.1 三个窗口的总量

| 窗口 | 新建 issue | 新建 PR | 其中 intake | 其中 mcp-intake | 其中 auto-rejected | 其中 needs-human-review | 其中 needs-salvage | 其中 pending-review |
|---|---|---|---|---|---|---|---|---|
| 近 24 小时 | 5 | 28 | **0** | 0 | 0 | 0 | 0 | 0 |
| 近 7 天 | 58 | 116 | **17** | 17 | 8 | 8 | 8 | 4 |
| 近 30 天 | 246 | 393 | **88** | 88 | 21 | 71 | 21 | 72 |

**换算成「每天」**：

- 近 7 天：issue **8.3/天**、PR **16.6/天**、intake **2.4/天**
- 近 30 天：issue **8.2/天**、PR **13.1/天**、intake **2.9/天**
- 近 24 小时：issue 5、PR 28、intake **0**（intake 出现 0 是真实数据，非抓取失败）

> 近 7 天 intake 只占全部新建 issue 的 **17/58 = 29.3%**；
> 近 30 天为 **88/246 = 35.8%**。

### 3.2 每日明细（近 10 天，来自 `/search/issues`）

| 日期(UTC) | 新建 issue | 新建 PR | 其中 intake | 当日合并 PR |
|---|---|---|---|---|
| 2026-09-16 | 3 | 19 | 0 | 11 |
| 2026-09-15 | 15 | 51 | 1 | 24 |
| 2026-09-14 | 5 | 1 | 1 | 0 |
| 2026-09-13 | 19 | 12 | 4 | 8 |
| 2026-09-12 | 5 | 2 | 3 | 4 |
| 2026-09-11 | 5 | 11 | 4 | 9 |
| 2026-09-10 | 4 | 14 | 3 | 11 |
| 2026-09-09 | 2 | 22 | 1 | 19 |
| 2026-09-08 | 18 | 11 | 6 | 4 |
| 2026-09-07 | 10 | 16 | 2 | 19 |

> 2026-09-16 为**不完整日**（快照在 14:59Z）。09-15 单日 51 个 PR、09-13 单日 19 个 issue 是两处明显峰值。

### 3.3 分周 open / close（基于全量 661 条 issue 的 `created_at` / `closed_at`）

| 周起始(UTC) | 新建 | 关闭 | 关闭/新建 |
|---|---|---|---|
| 2026-09-09 | 55 | 62 | 1.13 |
| 2026-09-02 | 48 | 46 | 0.96 |
| 2026-08-26 | 40 | 46 | 1.15 |
| 2026-08-19 | 91 | 62 | **0.68** |
| 2026-08-12 | 73 | 64 | 0.88 |
| 2026-08-05 | 50 | 48 | 0.96 |
| 2026-07-29 | 44 | 45 | 1.02 |
| 2026-07-22 | 10 | 9 | 0.90 |

> 近 7 天实际关闭 issue **64** 个，近 30 天 **233** 个。
> 唯一明显「入不敷出」的一周是 2026-08-19（新建 91、关闭 62）——那正是 intake 单周 **34** 个的高峰周。
> 此后 intake 回落到每周 14–18，关闭率也回到 ≥1.0，**说明 8 月下旬那波积压已经消化掉了**。

---

## 4. 最该被维护者处理的 10 个 issue

排序依据：是否「已答复但未关闭」、是否卡住可合并的 PR、开放时长、评论数却无决定、bounty 无进展。

| # | 标题（截断） | 开放天数 | 评论 | 关键标签 | 为什么值得维护者看 |
|---|---|---|---|---|---|
| 1724 | [Question] Bounty #1661: rebuild lessons/index.md … | 1 | 5 | `intake`,`question`,`needs-human-review`,`pending-review`,`priority:medium` | **唯一「真有人提问但维护者从未回复」的问题**（维护者评论数 = 0，最后发言是社区 `nazasnow`）——最像被漏掉的一条 |
| 1528 | feat: intake conversion receipt — notify source when its intake becomes a lesson | 9 | **47** | `bounty`,`area:core`,`area:workflow`,`ready` | **全仓评论最多**的开放 issue；承载 PR #1544，而 #1544 是 `dirty` + draft，被合并冲突卡了 8.9 天 |
| 1652 | [Bounty][$0][Lessons] 把 intake #1553（alembic upgrade 失败）转成课程 | 3 | 8 | `bounty`,`good first issue`,`ready`,`zero-bounty` | **最接近完成**：已有 2 个 PR 尝试（#1656、#1713），#1713 检查全绿只差评审；**只需维护者点一次合并或再指一次修** |
| 1665 | [Bounty][$0][Lessons] 把 intake #1472 + #1473（Vertex/Gemini 模型 ID 命名）转成课程 | 2 | 5 | `bounty`,`priority:high`,`ready`,`zero-bounty` | 有 **2 个互相竞争的 PR**（#1715 检查全绿 / #1746 DCO 失败）指向同一 bounty，需裁决保留哪个 |
| 1666 | [Bounty][$0][Lessons] 把 intake #1618 + #1619（写成功但数据静默丢失）转成课程 | 2 | 5 | `bounty`,`priority:high`,`ready`,`zero-bounty` | 同上：**#1716（全绿）vs #1748（DCO 失败）重复 PR**，需裁决 |
| 1258 | [Onboarding] Connect your agent & submit failures via MCP | 24 | 13 | `bounty`,`activation`,`roadmap`,`status: competition`,`ready` | **开放最久的非 intake 高互动 issue**；维护者只参与 1 次，最后发言是社区贡献者，属于「长跑型」issue 无决定 |
| 869 | [Glama] Track hosted endpoint routing support request | **40** | 6 | `stale`,`zero-bounty` | **全仓开放最久**的 issue（40 天，已打 `stale`），最后发言是 `github-actions[bot]`——要么推进要么关掉 |
| 1130 | [Intake] zsh: command not found: python | 27 | 2 | `intake`,`mcp-intake`,`needs-human-review`,`pending-review`,`priority:medium` | **最老的开放 intake**；维护者是最后发言人（已答复），但 **27 天未关闭**——典型「已答复未收口」 |
| 1170 | [Intake] 背景 2026-08-20/21 推送 M-900iB 换油修复 … | 26 | 3 | `intake`,`mcp-intake`,`needs-human-review`,`priority:high`,`help wanted` | 26 天、`priority:high` 的 intake，维护者已回复但未关闭；同类共 4 条（#1130/#1145/#1146/#1170） |
| 1651 | [Bounty][$0][Lessons] 把 intake #1555（nano-gpt.com SSE 流式调用失败）转成课程 | 3 | 8 | `bounty`,`good first issue`,`ready`,`zero-bounty` | 曾有 PR #1660（`vagusstoff`）但**未合并即关闭**；现有 #1714 检查全绿只差评审——重复投入的信号 |

**补充（差点进前 10）**：

- #1650、#1655、#1672：同为「intake 转课程」bounty，均**没有任何维护者评论**，但各自已有 PR（#1750 / #1749 / #1747），且这三个 PR 全部因 DCO 失败被卡 —— 合计 4 个 bounty 卡在同一处机械故障上。
- #1639：`github-actions[bot]` 产出的 **Intake Salvage Digest**（4 天，维护者评论 0）——**机器人生成的待办没人消费**。
- #1678、#1679、#1738、#1743、#1767：**评论数 = 0** 的 5 个开放 issue（3 个 lesson-submission / bug 各带 `needs-ac`，1 个 RFC），其中 #1767 是 `zsxh1990` 提交的 RFC，尚未有人回应。

**「已答复但未关闭」的量化**：43 个开放 issue 中，**最后一条评论来自维护者 `Ikalus1988` 的有 22 个**——
也就是说这 22 个 issue **维护者已经回过话、但至今仍开着**，属于纯收口动作，不需要再做判断。

---

## 5. 最近 7 天合并 / 关闭的 PR

窗口：2026-09-09T15:05Z 起。取 `/pulls?state=closed&sort=updated&direction=desc` 并按 `merged_at` / `closed_at` 过滤（扫到 150 条后按 `updated_at` 早于窗口停止）。

| 指标 | 数量 |
|---|---|
| 7 天内关闭的 PR | **130** |
| 其中**已合并** | **86**（66.2%） |
| 其中**未合并即关闭** | **44**（33.8%） |
| 7 天内新建 PR | 116 |
| 7 天内合并 PR（按 `merged:>=` 搜索） | 逐日合计见 §3.2 |

### 5.1 已合并 PR 的作者分布（86 个）

| 作者 | 合并数 |
|---|---|
| `Ikalus1988` | 52 |
| `zsxh1990` | 12 |
| `dependabot[bot]` | 5 |
| `s6pa1rta3n-lab` | 5 |
| `yashraj4` | 3 |
| `Mr-Neutr0n` | 3 |
| `2lll5` | 2 |
| `kveita` | 2 |
| `canburakyol` | 1 |
| `gloskull` | 1 |

### 5.2 未合并即关闭的作者分布（44 个）

| 作者 | 未合并关闭数 |
|---|---|
| `zsxh1990` | 17 |
| `Ikalus1988` | 9 |
| `tsunafire` | 5 |
| `Silverbullets1` | 5 |
| `vagusstoff` | 3 |
| `eliolatifllari513-coder` | 3 |
| `s6pa1rta3n-lab` | 1 |
| `yhq411` | 1 |

### 5.3 「未合并即关闭」的性质：大部分是**自我顶替**，不是被否决

对 44 个未合并关闭的 PR 按「同作者 + 同标题」聚类：

- **12 个**是同一作者把同一标题重复提交后被自己顶替。典型：
  `zsxh1990` 的「SSE streaming failure」提交了 **3 次**（#1694 → #1704 → #1709）；
  「Vertex AI vs Gemini model ID」**3 次**（#1695 → #1705 → #1710）；
  「write success but data missing」**3 次**（#1696 → #1706 → #1711）；
  「use context.payload instead of github.event」**3 次**（#1692 → #1702 → #1707）；
  「alembic upgrade」**2 次**（#1693 → #1703）；「exempt test files」**2 次**（#1604 → #1699）。
- **6 个**存在「同作者同标题的后续 PR 已合并」的顶替关系：#1691→#1697、#1728→#1730、#1732→#1733、
  #1740/#1741→#1742、#1757→#1758。
- **8 个**是**不同贡献者抢同一个 lesson**、只留一份的被关闭重复件：
  `Silverbullets1` 的 #1575–#1579 与 `tsunafire` 的 #1589–#1593 均在 2026-09-09T16:01 被关闭，
  最终由 `s6pa1rta3n-lab` 的 #1573/#1580/#1581/#1587/#1588 合并——**同一批 5 篇 lesson 有 3 个人在写**。
- `eliolatifllari513-coder` 的 #1616/#1634（intake conversion receipt）与 #1617（error-signature index）
  同样是 #1528 / #1654 的重复尝试。

> 结论：44 个未合并关闭里，**至少 18 个（12 重复顶替 + 6 后续已合并）是「提交流水」而非质量否决**。
> 剩余约 26 个的**关闭理由未获取**（API 不返回关闭原因说明，需读 PR 评论）。

**7 天内已合并 PR 的完整清单**（编号 / 合并时间 / 作者 / 标题截断）：

```
1582 09-09T16:02 @zsxh1990          fix(email): expand detectIntakeType with recruitment/pitch/...
1583 09-09T16:03 @zsxh1990          fix(email): switch rate limit from interval to count-based window
1584 09-09T16:03 @zsxh1990          fix(search): expand hyphenated tokens in BM25 tokenizer
1585 09-09T16:03 @zsxh1990          feat(traffic): add daily-to-monthly aggregation cron
1560 09-09T16:05 @zsxh1990          feat(lessons): CI failure pattern analysis — 52 cases, 3 lessons
1573 09-09T16:05 @s6pa1rta3n-lab    feat(lessons): add iap tcp forwarding and docker compose lessons
1580 09-09T16:05 @s6pa1rta3n-lab    feat(lessons): add Vertex AI cost attribution lesson
1581 09-09T16:06 @s6pa1rta3n-lab    lesson(contrib): Vertex AI Embedding migration for Python and Go
1587 09-09T16:06 @s6pa1rta3n-lab    feat(lessons): add Vertex AI streaming and Gemini safety passthrough
1588 09-09T16:06 @s6pa1rta3n-lab    feat(lessons): add 5 agent and engineering lessons
1412 09-09T16:11 @Mr-Neutr0n        fix: [Intake] Node.js: missing require("node:os")
1413 09-09T16:11 @Mr-Neutr0n        fix: [Intake] Windows CI: three bugs in one session
1415 09-09T16:11 @Mr-Neutr0n        fix: [Intake] R-2000iC 换油周期案例
1598 09-09T17:29 @Ikalus1988        fix(ops): debounce keepalive probe failures + cron */15
1594 09-09T17:46 @zsxh1990          fix(guard): add deprecation warning + CI schema check
1595 09-09T17:46 @zsxh1990          feat(verify): add Glama listing verification script
1596 09-09T17:46 @zsxh1990          feat(verify): add DSH plugin listing verification script
1597 09-09T17:47 @zsxh1990          feat(watcher): memory dump watcher — auto-extract lessons
1599 09-09T17:47 @zsxh1990          feat(intake): add contributor tracking to intake pipeline
1586 09-10T14:52 @zsxh1990          feat(gap): add gap→lesson lifecycle cleanup with BM25 matching
1513 09-10T14:52 @kveita            fix: replace broken Smithery badge with dynamic badge
1603 09-10T14:56 @zsxh1990          test(intake): statistical evaluation with 100 stratified samples
1606 09-10T14:56 @Ikalus1988        fix(mcp): include structuredContent in tools/call results
1607 09-10T15:47 @Ikalus1988        ci: auto-reopen protected long-running issues
1609 09-10T16:25 @Ikalus1988        fix(badges): repair Smithery badge pipeline
1610 09-10T16:51 @Ikalus1988        fix(deps): bump sharp override to 0.35.4
1611 09-10T16:51 @Ikalus1988        ci: add HOL Guard Guarded Repository scan
1612 09-10T17:23 @Ikalus1988        feat(plugin): add Codex plugin manifest + privacy/terms
1613 09-10T17:24 @Ikalus1988        feat(security): prompt-injection defense for content surfaces
1614 09-10T17:35 @Ikalus1988        feat(mcp): L3 read-path trust notice
1620 09-11T01:17 @Ikalus1988        feat(security): L4 scan anonymous intake payloads
1623 09-11T10:25 @yashraj4          fix: publish openclaw session_nodes lesson
1624 09-11T10:36 @Ikalus1988        feat(mcp): content-level suspicion flag on retrieved lessons
1625 09-11T12:17 @Ikalus1988        fix(ci): leaderboard-watch 并发快照冲突
1626 09-11T12:17 @Ikalus1988        lesson(contrib): push 触发的 bot workflow 自我竞争
1628 09-11T12:18 @Ikalus1988        fix(release): release-please 提交自带 sign-off
1627 09-11T12:22 @Ikalus1988        tool(scripts): gh_push_via_api.py
1629 09-11T12:47 @Ikalus1988        lesson(contrib): JSON Schema 的布尔子模式 true 不是推荐值
1608 09-11T13:29 @Ikalus1988        chore(main): release 2.29.0
1636 09-12T01:54 @Ikalus1988        fix(dsh): stop naming the protected component in bundle patch
1631 09-12T14:12 @Ikalus1988        chore(main): release 2.30.0
1615 09-12T14:28 @kveita            fix: correct shields.io endpoint badge URL for Smithery
1633 09-12T14:28 @yashraj4          feat: roleplay vocative vs mention disambiguation lesson
1645 09-13T11:22 @yashraj4          feat: character creator repetition loop lesson
1642 09-13T11:25 @gloskull          Windows voice hook verification
1657 09-13T12:53 @2lll5            ci: add nightly lessons mirror consistency check
1667 09-13T22:40 @dependabot[bot]  chore(deps): update mcp requirement >=2.1.1 -> >=2.2.0
1668 09-13T22:40 @dependabot[bot]  chore(deps-dev): bump wrangler 4.129.0 -> 4.131.0
1669 09-13T22:40 @dependabot[bot]  chore(deps): bump Codium-ai/pr-agent 0.44.0 -> 0.45.0
1670 09-13T22:40 @dependabot[bot]  chore(deps): bump pr-genius-check action
1671 09-13T22:41 @dependabot[bot]  chore(deps): bump hol-guard workflow
1684 09-15T02:08 @Ikalus1988        feat(setup): give the npx installer the OpenClaw target
1686 09-15T04:48 @Ikalus1988        feat(ssot): gate the node count, mirror it from the KV
1688 09-15T05:06 @Ikalus1988        fix(setup): stop handing file-derived values to other programs
1690 09-15T05:22 @Ikalus1988        fix(setup): keep the User-Agent version a literal, bind it by test
1697 09-15T06:02 @Ikalus1988        fix(worker): negotiate the MCP protocol version
1698 09-15T06:06 @Ikalus1988        feat(setup): register Hermes by file
1700 09-15T06:34 @Ikalus1988        fix(ci): read the event off context
1712 09-15T09:11 @Ikalus1988        feat(setup): a 14-day upgrade nudge
1717 09-15T10:45 @Ikalus1988        fix(setup): probe with a handshake
1720 09-15T10:59 @Ikalus1988        docs: contribution paths in plain words
1721 09-15T11:48 @Ikalus1988        fix(onboarding): ask a question the corpus answers
1722 09-15T11:51 @Ikalus1988        fix(agent-autostart): same two defects, fixed on the Python side
1723 09-15T11:55 @Ikalus1988        fix(counts): give the domain count a definition
1727 09-15T12:28 @Ikalus1988        fix(ci): stop the frontmatter parsers inventing slug/dir metadata
1729 09-15T12:50 @Ikalus1988        fix(counts): a named group is also a numbered group
1730 09-15T13:02 @Ikalus1988        fix(worker): bump the search index text version
1733 09-15T13:42 @Ikalus1988        fix(dsh): give the plugin package a repository field
1735 09-15T16:20 @Ikalus1988        feat(dsh): the bundle row points at the public endpoint
1736 09-15T16:45 @Ikalus1988        fix(mcp): lesson hits carry their content
1737 09-15T16:57 @Ikalus1988        fix(mcp): expose the Problem/Fix snippets in row shaping
1739 09-15T17:08 @Ikalus1988        fix(worker): rebuild the search index from D1
1742 09-15T17:44 @Ikalus1988        refactor(domains): make the domain vocabulary a reviewable file
1744 09-15T17:57 @Ikalus1988        fix(codex): the installer said the hook could not be confirmed
1745 09-15T18:04 @Ikalus1988        fix(setup): a re-run now refreshes a stale hook
1752 09-16T08:13 @Ikalus1988        feat(setup): codewhale becomes the fifth target
1755 09-16T09:40 @Ikalus1988        feat(voice): the voice hook becomes an installer switch
1758 09-16T09:50 @Ikalus1988        fix(setup): upgrade a matcher-less voice entry
1759 09-16T10:28 @Ikalus1988        feat(setup): --report prints this machine's state
1756 09-16T11:58 @2lll5            fix(setup): verify only detected agent targets
1760 09-16T12:03 @Ikalus1988        feat(setup): three onboarding examples instead of one
1762 09-16T12:25 @Ikalus1988        fix(setup): pre-allow the read-only tools
1646 09-16T13:20 @canburakyol      feat: add workflow shell checker (W1-W5) for bounty #1640
1764 09-16T13:22 @Ikalus1988        fix(ci): do not report a missing PyYAML as YAML breakage
1765 09-16T14:27 @Ikalus1988        chore(setup): ignore the generated voice/ copy too
1766 09-16T14:47 @Ikalus1988        docs(maintainer): blueprint completeness and strategy review
```

**未合并即关闭的完整清单**（44 个）：

```
1575 09-09T16:01 @Silverbullets1               Solution for #1572: [Lesson] 运维小课 ×2
1576 09-09T16:01 @Silverbullets1               Solution for #1571: [Lesson] Agent/LLM 工程小课 ×5
1577 09-09T16:01 @Silverbullets1               Solution for #1570: [Lesson] Vertex/Gemini 工程小课 ×2
1578 09-09T16:01 @Silverbullets1               Solution for #1569: [Lesson] Vertex AI Embedding 迁移
1579 09-09T16:01 @Silverbullets1               Solution for #1568: [Lesson] Vertex AI 成本归因
1589 09-09T16:01 @tsunafire                    Fix #1569: Vertex AI Embedding 迁移实战
1590 09-09T16:01 @tsunafire                    Fix #1568: Vertex AI 成本归因
1591 09-09T16:01 @tsunafire                    Fix #1570: Vertex/Gemini 工程小课 ×2
1592 09-09T16:06 @tsunafire                    Fix #1571: Agent/LLM 工程小课 ×5
1593 09-09T16:01 @tsunafire                    Fix #1572: 运维小课 ×2
1559 09-09T16:01 @yhq411                       Fix #1528: intake conversion receipt
1538 09-10T00:40 @s6pa1rta3n-lab               feat: error-signature index (failure_patterns)
1634 09-12T14:28 @eliolatifllari513-coder      Fix: intake conversion receipt
1617 09-12T14:28 @eliolatifllari513-coder      Fix: error-signature index (failure_patterns)
1616 09-12T14:28 @eliolatifllari513-coder      Fix: intake conversion receipt
1660 09-13T12:50 @vagusstoff                   docs: resolve #1651 - 把 intake #1555 转成课程
1659 09-13T12:50 @vagusstoff                   docs: resolve #1652 - 把 intake #1553 转成课程
1658 09-13T12:50 @vagusstoff                   docs: resolve #1653 - lessons.json 镜像 nightly 检查
1689 09-15T05:20 @Ikalus1988                   fix(setup): make the User-Agent version a literal
1691 09-15T06:00 @Ikalus1988                   fix(worker): negotiate the MCP protocol version
1604 09-15T06:07 @zsxh1990                     fix(guard): exempt test files from markdown leak detection
1699 09-15T08:43 @zsxh1990                     fix(guard): exempt test files from markdown leak detection
1692 09-15T08:45 @zsxh1990                     fix(workflow): use context.payload instead of github.event
1693 09-15T08:45 @zsxh1990                     feat(lesson): alembic upgrade failure diagnosis
1694 09-15T08:45 @zsxh1990                     feat(lesson): SSE streaming failure via proxy
1695 09-15T08:45 @zsxh1990                     feat(lesson): Vertex AI vs Gemini model ID naming
1696 09-15T08:45 @zsxh1990                     feat(lesson): write success but data missing
1702 09-15T08:46 @zsxh1990                     fix(workflow): use context.payload instead of github.event
1703 09-15T08:46 @zsxh1990                     feat(lesson): alembic upgrade failure diagnosis
1704 09-15T08:46 @zsxh1990                     feat(lesson): SSE streaming failure via proxy
1705 09-15T08:46 @zsxh1990                     feat(lesson): Vertex AI vs Gemini model ID naming
1706 09-15T08:46 @zsxh1990                     feat(lesson): write success but data missing
1707 09-15T09:58 @zsxh1990                     fix(workflow): use context.payload instead of github.event
1708 09-15T09:58 @zsxh1990                     feat(lesson): alembic upgrade failure diagnosis
1709 09-15T09:58 @zsxh1990                     feat(lesson): SSE streaming failure via proxy
1710 09-15T09:58 @zsxh1990                     feat(lesson): Vertex AI vs Gemini model ID naming
1711 09-15T09:58 @zsxh1990                     feat(lesson): write success but data missing
1763 09-16T13:20 @Ikalus1988                   feat(ci): add the workflow shell checker (W1-W5)
1757 09-16T14:39 @Ikalus1988                   fix(setup): upgrade a matcher-less voice entry
1754 09-16T14:39 @Ikalus1988                   feat(voice): the voice hook becomes part of the installer
1741 09-16T14:39 @Ikalus1988                   refactor(domains): make the domain vocabulary a file
1740 09-16T14:39 @Ikalus1988                   refactor(domains): make the domain vocabulary a file
1732 09-16T14:40 @Ikalus1988                   fix(dsh): give the plugin package a repository field
1728 09-16T14:40 @Ikalus1988                   fix(worker): bump the search index text version
```

---

## 6. 流程信号

以下每条都可由已抓取的数据直接算出。

### 6.1 关闭率：整体健康

- 历史累计 **661** 个 issue，已关 **618**（**93.5%**），开放 43
- 已关 issue 的 `state_reason`：**`completed` 589 / `not_planned` 29**（即 95.3% 是「已完成」关闭）
- 近 7 天关闭 64 个、近 30 天关闭 233 个
- PR 侧：历史累计 1024 个 PR，合并 **538**（52.5%）；近 7 天关闭 130 个中合并 86 个（**66.2%**）

### 6.2 分周关闭/新建比（见 §3.3）

8 周里有 5 周关闭 ≥ 新建，唯一明显倒挂的是 2026-08-19 周（0.68），
且该周正是 intake 单周峰值（34 个）。**当前不存在持续性的 issue 积压。**

### 6.3 intake 的走向

| 指标 | 数值 |
|---|---|
| 历史累计 intake issue | **105** |
| 其中已关闭 | **83**（79.0%） |
| 其中仍开放 | **22**（21.0%） |
| 历史累计被判 `auto-rejected` | **21**（占 intake 的 **20.0%**） |
| 近 7 天 intake 中 `auto-rejected` | **8 / 17 = 47.1%** |
| 近 30 天 intake 中 `auto-rejected` | **21 / 88 = 23.9%** |
| 近 30 天 intake 中 `needs-human-review` | **71 / 88**（注：该标签在 30 天窗口的口径与其他窗口不同，见下） |

> ⚠️ 口径提醒：`auto-rejected` / `needs-human-review` / `pending-review` 都是**事后追加**的标签。
> 「近 7 天新建且现在带某标签」只统计已走完分诊的；越新的窗口越偏低（近 24 小时全为 0 即此原因）。
> 因此 **47.1% 与 23.9% 不可直接比较**，二者都只是「当前快照下的状态」，不是最终判定率。

### 6.4 intake → lesson 的转化率：**未获取（无法从本次抓取的数据推导）**

我尝试了两条路，都不能得到可信的转化率：

1. **API 侧**：issue 的时间线里**没有** `converted` / `lesson` 之类的标记标签或事件；
   关闭事件也不带「由哪个 lesson 关闭」的信息。抽查 #1130 / #1397 / #1145 的时间线，
   事件类型只有 `labeled` / `unlabeled` / `commented` / `referenced` / `renamed` / `cross-referenced`。
2. **语料侧**（本地只读检查，未修改任何文件）：`lessons/` 下 440 个 `.md` 中，
   **只有 3 个**文件回指 issue 编号（`lessons/contrib/vertex-ai-embedding-qwen-go-migration.md` → `#1569`、
   `lessons/contrib/roleplay-dialogue-loop-context-poisoning.md` → `#1547`、
   `lessons/contrib/go-linter-cleanup-go-fix.md` → `#1500`），
   而这 3 个 issue **都不带 `intake` 标签**（是 `lesson` / `lesson-submission` 类）。
   全语料 provenance 字段使用情况：`source` 739、`evidence` 420、`contributor` 404、`merged_at` 400、**`issue` 1**。

> **结论：lesson 与 intake issue 之间没有系统性的回链记录，所以「多少 intake 变成了 lesson」未获取。**
> 要能回答这个问题，需要给 intake issue 打一个 `converted:<lesson-path>` 标签
> 或在 lesson frontmatter 里强制写 `provenance.issue`。

**唯一可算的替代指标**——本仓用 bounty 显式委托转化：

| 指标 | 数值 |
|---|---|
| 标题形如「把 intake #N 转成课程」的 bounty | **7** |
| 它们覆盖的**不同 intake** | **9** 个（#1574, #1555, #1553, #1643, #1472, #1473, #1618, #1619, #1635） |
| 这 7 个 bounty 中**已关闭**的 | **0** |
| 这 7 个 bounty 中**已有 PR 尝试**的 | **7**（全部有） |

→ 也就是说：**转化管线已经 100% 被认领，但没有一个走完流程**。

### 6.5 「跳过评审」与「重复劳动」是最突出的浪费

- 14 个开放 PR 中 **12 个被卡住，只有 2 个（#1674、#1701）真正可以立刻合并**。
  12 个里 **7 个卡在机械问题**上（6 个检查失败 + 1 个合并冲突/draft），另外 **5 个检查全绿、纯粹在等评审**。
- 5 个 bounty（#1650/#1651/#1652/#1655/#1672 ＋ #1665/#1666）合计被 **9 个开放 PR 争夺**，
  其中 2 组是**两个不同作者写同一篇 lesson**（#1715 vs #1746，均为 Vertex/Gemini 模型 ID；#1716 vs #1748，均为静默数据丢失）。
- 近 7 天 **12 个未合并关闭 + 6 个被后续合并顶替**，共 **18 个 PR 属于「提交流水」**。

---

## 7. 维护者每天实际要判断多少

这是本报告的核心问题。以下把「流量」拆成**机器可判**与**必须人判**两层。

### 7.1 每日新增（滚动窗口换算）

| 项目 | 近 24 小时（实测） | 近 7 天（÷7） | 近 30 天（÷30） |
|---|---|---|---|
| 新建 issue | 5 | **8.3 / 天** | **8.2 / 天** |
| 新建 PR | 28 | **16.6 / 天** | **13.1 / 天** |
| 其中 bot intake issue | 0 | 2.4 / 天 | 2.9 / 天 |
| 需要合并/关闭决策的 PR | — | 12.3 合并 + 6.3 关闭 ≈ **18.6 / 天** | 同量级 |

> **每天要面对的收口动作约 = 8.3 个 issue + 16.6 个 PR ≈ 25 项。**
> 其中 **PR 才是主战场**（16.6/天 vs 8.3/天），比重是 **2:1**。

### 7.2 issue 侧：真正需要「人做判断」的比例

以近 7 天为口径（58 个新 issue）：

| 分层 | 数量 | 占比 | 说明 |
|---|---|---|---|
| 全部新建 issue | 58 | 100% | 8.3 / 天 |
| 其中 **bot 送进来的 intake** | 17 | 29.3% | 2.4 / 天 |
| 其中已被 **`auto-rejected`** | 8 | 13.8% | 1.1 / 天，**机器已判，只需收口** |
| 其中打上 **`needs-human-review`** | 8 | 13.8% | 1.1 / 天 |
| **intake 中未被自动拒绝、需要人看** | **9** | 15.5% | **1.3 / 天** |

近 30 天（246 个新 issue）：

| 分层 | 数量 | 占比 | 说明 |
|---|---|---|---|
| 全部新建 issue | 246 | 100% | 8.2 / 天 |
| 其中 intake | 88 | 35.8% | 2.9 / 天 |
| 其中 `auto-rejected` | 21 | 8.5% | 0.7 / 天 |
| **intake 中未被自动拒绝、需要人看** | **67** | 27.2% | **2.2 / 天** |

> **关键结论：每天真正需要维护者「动脑判断」的 intake 只有约 1.3–2.2 条。**
> intake 分诊本身**并不是**压垮人的那件事——近 24 小时甚至只有 **0** 条新 intake。

### 7.3 那「分诊管不过来」的真实体感来自哪里

三处可以量化的来源：

1. **存量收口，而非增量分诊**：43 个开放 issue 里，**22 个的最后一条评论就是维护者本人**。
   维护者已经回过话，但 issue 还开着——这 22 条是**纯收口债**，占开放 issue 的 **51.2%**。
   另有 5 个开放 issue **评论数为 0**（#1767、#1743、#1738、#1679、#1678），是彻底没人碰过的。
2. **bounty 空转**：14 个开放 `bounty` 中，**7 个「转课程」bounty 无一关闭**，
   且这 7 个的评论区里**维护者评论数为 0**（讨论全发生在贡献者与 `opirebot[bot]` 之间）。
   贡献者 `huiyuansun28-cmyk` 一个人在 5 个 bounty（#1650/#1655/#1665/#1666/#1672）下留言，
   并开了 5 个 PR——**5 个 PR 全部因 DCO 失败卡住**。
   也就是说：**一波真实贡献被一个机械门禁整体挡住了**。
3. **机器人生成的待办没人消费**：`github-actions[bot]` 产出的 #1639（Intake Salvage Digest，
   2026-09-12）4 天来维护者评论 **0** 条，带 `salvage-digest` + `needs-ac` 标签。
   自动分诊**产出了工作**，但没有被接住。

### 7.4 一句话回答

> 每天新增 **8.3 个 issue / 16.6 个 PR**，但其中**真正需要人判断的新增 intake 只有 1.3–2.2 条/天**；
> 让人喘不过气的不是「进来多少」，而是 **22 条已答复未关闭的收口债 + 7 个空转 bounty + 5 个被 DCO 挡住的贡献者 PR**。
> **优先做收口，而不是做分诊。**

---

## 8. 未获取 / 无法从本次 API 数据推导的项

| 项目 | 状态 | 原因 |
|---|---|---|
| intake → lesson 的实际转化率 | **未获取** | issue 时间线与关闭事件无转化标记；语料侧仅 3 个 lesson 回指 issue 且均非 intake（详见 §6.4） |
| 各 PR 检查失败的**具体日志文本** | **未获取** | `check-runs` 的 `output.summary` 为空；`annotations` 仅对 #1746 / #1656 给出 "DCO audit failed"，其余仅 "Process completed with exit code 1." |
| 44 个未合并关闭 PR 的**关闭理由** | **未获取** | API 不返回关闭说明；需逐 PR 读评论 |
| `pending-review` / `priority:*` 的**历史累计**数 | **未获取** | 未对全量 661 条做标签时间线回溯（此处只统计当前快照） |
| 各 issue 是否曾被人类「真正读过」 | **未获取** | API 无已读状态 |
| 维护者实际响应时长（SLA） | **未获取** | 未计算首次人回复的时延分布 |

---

## 如何复现

Token 通过 `python3 -c "import sys; sys.path.insert(0,'scripts'); from gh_push_via_api import resolve_token; print(resolve_token())"` 获取
（**不要**把 token 写进任何文件或输出）。所有请求带
`Authorization: Bearer <token>` 与 `User-Agent: agent`，用 `python3` + `urllib`（无第三方库）。
基础路径 `https://api.github.com/repos/Ikalus1988/MisakaNet`。
所有列表端点均以 `per_page=100`（大数据集用 50 以规避截断）分页。

### 本报告用到的确切端点

| 用途 | 请求 |
|---|---|
| 仓库元信息 / 快照时钟 | `GET /repos/Ikalus1988/MisakaNet`（读 `pushed_at`） |
| 开放 PR 列表 | `GET /pulls?state=open&sort=created&direction=asc&per_page=100` |
| 单个 PR（`mergeable_state` / `changed_files` / `additions` / `deletions` / head sha） | `GET /pulls/{number}` |
| 检查运行 | `GET /commits/{head_sha}/check-runs?per_page=100` |
| 检查失败原因（注解） | `GET /check-runs/{check_run_id}/annotations` |
| 评审状态 | `GET /pulls/{number}/reviews` |
| 开放 issue（剔除 PR 用 `pull_request` 字段） | `GET /issues?state=open&per_page=100` |
| 全量 issue（算分周 open/close、intake 生命周期） | `GET /issues?state=all&sort=created&direction=desc&per_page=50` |
| issue 评论（判断「已答复未关闭」） | `GET /issues/{number}/comments` |
| issue 时间线（探查是否有转化标记） | `GET /issues/{number}/timeline` |
| 近 7 天关闭的 PR | `GET /pulls?state=closed&sort=updated&direction=desc&per_page=50`，按 `merged_at`/`closed_at` 过滤；扫到 `updated_at` 早于窗口即停 |
| 窗口化计数（issue/PR/intake/auto-rejected/merged） | `GET https://api.github.com/search/issues?q=repo:Ikalus1988/MisakaNet+is:issue+created:>=<ISO8601>`，同理用 `is:pr`、`label:intake`、`label:auto-rejected`、`is:pr+is:merged+merged:>=` |
| 语言侧转化核查（本地只读） | `grep -rhoE '\bissue:\s*"?[#]?[0-9]+' lessons/` 与 `grep -rhoE '^\s*(source|evidence|contributor|merged_at|issue):' lessons/` |

### 口径备注

- 「年龄(天)」= `2026-09-16T14:59Z` 减去 `created_at`。
- 2026-09-16 是**不完整日**，其每日计数只覆盖到快照时刻。
- 标签类计数均为**快照时刻状态**，不加时间回溯（`auto-rejected` 等标签是事后追加的）。
- issue 数量已剔除 `pull_request` 字段非空的条目（`state=open` 的 57 条中有 14 条其实是 PR）。
