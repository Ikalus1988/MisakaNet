# 课程 PR 自动合并通道（`auto-merge-lesson`）

> Issue **#1777** 的实现说明。本页是这条通道的**唯一权威说明**：决策表、启用/停止方式、
> 风险边界与回滚步骤。
> 相关文件：`.github/workflows/auto-merge-lessons.yml`（触发与动作）·
> `scripts/lesson_pr_mergeable.py`（判定，纯函数、无网络）·
> `tests/test_lesson_pr_mergeable.py`（离线单测）。

---

## 1. 它做什么

给一个 **纯课程（`lessons/` 内）** 的 PR 打上标签 `auto-merge-lesson` 之后：

- 所有**机械条件**成立的瞬间，机器人用 **squash** 合并它；
- 有一个条件**不成立**（检查失败 / 改了 `lessons/` 以外的文件 / draft / 被请求修改 / 打了拒绝标签），
  机器人在 PR 上留**一条**评论，写清**卡在哪一条**；
- 某个条件**只是还没完成**（检查还在跑 / 必需检查还没上报 / 标签还没打），机器人**什么都不做**，
  等下一次事件再判断。

一句话：**它是"收口"工具，不是"审阅"工具。** 它只回答"机械条件是否都成立"，
不回答"这篇课程写得对不对"——内容判断仍然是人（维护者）的事，见 §5。

### 触发时机

| 事件 | 说明 |
|---|---|
| `pull_request: labeled` | 打标签的瞬间（这是"我同意自动合并"的入口） |
| `pull_request: synchronize` | 每次 push 新提交（这是**主力**触发路径：检查重启后会再判一次） |
| `pull_request: ready_for_review` | draft 转正 |

> ⚠️ **`check_suite: completed` 那条兜底已在 2026-10-02 删除**。它原本依据的是社区报告
> （[discussion #26169](https://github.com/orgs/community/discussions/26169)、
> [#26236](https://github.com/orgs/community/discussions/26236)）里的说法：**由 GitHub Actions
> 自己创建的 check suite 完成时不会触发 `check_suite` 工作流**，只有别的 GitHub App 产生的套件才会。
> **那个说法在本仓是假的**。实测（`dedc383b`，main 从 04:07:48Z 到 05:22:42Z 的 tip）：
>
> * 该 commit 上有 **280 个 check suite，其中 276 个来自 `github-actions`**；非 Actions 的 4 个里
>   只有 `cloudflare-workers-and-pages` 真正完成过（04:08:19Z），另外 3 个一直停在 `queued`。
> * 本工作流在那条 commit 上启动了 **39 个 `check_suite` run**，其中 **37 个**发生在同一 commit 上
>   某个 `github-actions` 套件完成后的 **60 秒内**；而每一次 run 又会完成一个 `auto-merge-lessons`
>   套件——于是触发自己。真正的触发源不是第三方 App，是本仓自己的工作流。
>
> 所以"零成本兜底"不成立，它是**扇出**。删掉之后要接受的后果，正是这份文档原本就写明的"安全的一侧"：
> 一个已 opt-in 的 PR 如果在 `synchronize` / `ready_for_review` / `labeled` 之后检查才全绿，
> **不会**自动合并，需要人手动合一次。判定逻辑与 opt-in 标签的校验都没变，变的是"什么时候被叫醒"。

### 判定从哪来（事实全部读 API，不读 PR 内容）

| 事实 | 来源 |
|---|---|
| 改动文件 + 每个文件的新增/删除行数 | `GET /pulls/{n}/files?per_page=100`（分页） |
| 检查名 + 结论 | `GET /commits/{head_sha}/check-runs?per_page=100`（分页；同名取**最新**一次，避免旧的失败重跑压过新结果） |
| 标签 | `GET /pulls/{n}` 的 `labels` |
| draft | `GET /pulls/{n}` 的 `draft` |
| 评审状态 | `GET /pulls/{n}/reviews?per_page=100`：**按作者取最后一次** `APPROVED`/`CHANGES_REQUESTED`（`DISMISSED` 自动被排除）；任一位作者最后一次是 `CHANGES_REQUESTED` → 视为"被请求修改" |
| 合并前复核 | 合并**之前**重新 `GET /pulls/{n}`，要求 `mergeable` 为真、`state == open`、`draft == false`、标签仍在。⚠️ REST 的 `mergeable` 是**布尔** `true`/`false`/`null`，枚举串 `MERGEABLE` 是 **GraphQL** 的形状——`scripts/lesson_pr_mergeable.py:mergeable_is_clean()` 把两种形状归一化成 `clean`/`unclean`，shell 只比较归一化结果，不再拿一个 API 的拼写去比另一个 API 的读法（这正是 2026-09-17 首次真实运行时"判定 merge、复核却自拒"的原因） |

---

## 2. 决策表

判定顺序**从上到下，第一个命中的就是结论**（评论里写的就是这一条）。

| # | 条件 | 结论 | 评论里会写什么 |
|---|---|---|---|
| 1 | 有 `do-not-merge` 或 `wip` 标签 | **refuse** | `deny-list label(s) present: …` |
| 2 | 没有 `auto-merge-lesson` 标签 | **wait** | （不评论；工作流在调用判定之前就已退出） |
| 3 | PR 是 draft | **refuse** | `the pull request is still a draft` |
| 4 | 评审状态是 `CHANGES_REQUESTED` | **refuse** | `a review requests changes (CHANGES_REQUESTED)` |
| 5 | 有任何一个改动文件不在 `lessons/` 下 | **refuse** | `file(s) outside lessons/: scripts/…` |
| 5b | 改动文件列表为空 | **wait** | `no changed files reported — scope could not be verified` |
| 6 | 动了 `lessons/index.md` 且 `deletions > 0` 或 `additions > 1` | **refuse** | `lessons/index.md must be at most a one-line addition: +3/-5 …` |
| 6b | 动了 `lessons/index.md` 但拿不到行数 | **wait** | `lessons/index.md is touched but its line stats are unknown` |
| 7 | 任一必需检查结论不是 `success` | **refuse** | `required check(s) not successful: provenance (failure)` |
| 8 | 任一必需检查缺失 / 还在跑 / 排队 | **wait** | `required check(s) not green yet: provenance (in_progress)` |
| 9 | 以上都不命中 | **merge** | 合并后把上一次的"拒绝"评论改写成"已合并" |

**必需检查**（名字完全匹配）：

- `gate`（Lesson Quality Gate）
- `provenance`（Provenance Gate）
- `dco`（DCO Check）
- `audit-shape`（PR Shape Guard）
- 所有名字以 `test (` 开头的矩阵分片（Cross-Platform Tests）

**"缺失"与"没上报"的区别（重要）**：`gate` / `provenance` / `dco` / `audit-shape` 这四个名字是**写死**的，
缺一个就 `wait`（不合并、不评论）；而 `test (…)` 分片是把**当前上报了的**名字全部要求为 `success`——
**某个分片整个没跑，这里是看不见的**（分片数量写在 `ci-cross-platform.yml` 里，不在这条通道的输入里）。
`skipped` / `neutral` 这类"跑了但没通过"的结论按 `refuse` 处理（比分支保护更严）。

**`auto-merge-lesson` 之外的路径**：本通道只处理打了标签的 PR。没标签的 PR 连判定都不会调用
（工作流在取标签后立即退出），所以它**不会**给仓库里成百上千个普通 PR 刷评论。

### wait 与 refuse 的分界

- **wait**：没有错，只是**还没完成**。什么都不做，因为检查/事件会再来一次。
- **refuse**：有东西**明确不成立**，只有人（或新提交）能解除。留一条评论，并在下一次 push 时
  **改写同一条评论**（用 `<!-- auto-merge-lessons -->` 标记定位，且只改写**本 token 自己发的**那条），
  不会每次 push 刷一条新评论。

---

## 3. 如何启用

1. **确认内容已经有人看过。** 标签就是"我（维护者）已经看过内容，剩下的交给机器"的声明，
   本通道不会替你判断内容（见 §5）。
2. 给 PR 打标签 `auto-merge-lesson`：

   ```bash
   gh pr edit <PR号> --repo Ikalus1988/MisakaNet --add-label auto-merge-lesson
   # 或在 PR 页面右侧 Labels 里选
   ```

   **只有对该仓库有 triage/write 权限的人才能加标签**——外部贡献者无法自助开启这条通道，
   这是本通道唯一的人工授权点，也是它最重要的安全边界。
3. 然后什么都不用做。检查全绿的瞬间 PR 会被 squash 合并；有阻塞会收到一条评论。
4. **不想合并的 PR 请主动打 `wip` 或 `do-not-merge`**，它们优先于本通道（决策表第 1 条）。

> 自动合并**不使用** `--delete-branch`：分支保留，方便出问题时人工核对。

### 本地手工判定（不需要网络）

```bash
python3 scripts/lesson_pr_mergeable.py --json '{
  "files":["lessons/contrib/x.md"], "file_stats":{"lessons/contrib/x.md":[58,0]},
  "checks":{"gate":"success","provenance":"success","dco":"success",
            "audit-shape":"success","test (ubuntu-latest, 3.12)":"success"},
  "labels":["auto-merge-lesson"], "draft":false, "review_state":"APPROVED"}'
```

退出码即判定：**0 = merge**、**1 = refuse**、**2 = wait**、**3 = payload 不可用（什么都别做）**。
工作流就是按这个退出码分支的，也会在日志里打印 `verdict (exit N): …`。
（`--json -` 可以从 stdin 读，方便管道。）

---

## 4. 如何停止

| 想做什么 | 怎么做 | 效果 |
|---|---|---|
| 只停一个 PR | 摘掉标签：`gh pr edit <PR号> --remove-label auto-merge-lesson` | 工作流在取到标签后立即退出：不合并、不评论。**下一次事件**生效，已经发起的合并无法撤回 |
| 给某个 PR 加"硬刹车" | 打 `wip` 或 `do-not-merge` | 立即 refuse（并且会留一条说明），摘掉标签后才恢复 |
| 临时停整条通道 | `gh workflow disable auto-merge-lessons.yml` | 不再有新的运行；已存在的 PR 全部退回人工合并。或用 Actions 页面上的 "Disable workflow" |
| 彻底停掉 | 见 §6 回滚 | 代码级移除 |

> 注意：**标签是"开关"，不是"排队"。** 摘标签不会把已经合并的 PR 变回来。

---

## 5. 风险声明（这一节请不要跳读）

本通道是**机械门禁的收口器**：它验证的是**形状**（路径、检查结论、标签、draft、评审状态），
**不是内容**。以下风险是本通道**明确挡不住**的——加标签之前请当成"这就是我在背书"：

| 挡不住的东西 | 为什么 | 现有的其它门禁能帮到多少 |
|---|---|---|
| **来源伪造但"可解析"的课程** | `provenance` 只验证 URL 不是占位符、能解析（`check_provenance.py`）。一个真实存在但**与本次经验无关**的 issue 链接、或一个被精心挑过的可访问链接，它一样会通过 | 只能挡掉 404 / `<owner>/<repo>` 占位符 / 已知死链 |
| **与既有课程重复的课程** | 没有任何去重门禁在本通道的判定里；`find_duplicate_lessons.py` 是**人工按需**跑的工具，不是阻塞项 | 需要人自己跑/看 |
| **技术上错误的修复建议** | 没有任何检查能判断"这个 fix 是否真的管用" | 只能靠人 |
| **注入形态以外的有害内容**（错误引导、广告、越权指令） | `injection_scan.py` 只对**高置信度注入形态**失败；措辞层面的操纵不在它的判定范围内 | 部分 |
| **没有人工批准就合并** | 决策表**不要求** `APPROVED`：`NONE`（无人评审）也会合并。这是刻意的（本仓 14 个开放 PR 里有 11 个根本没评审记录），**也是这条通道最大的风险点** | 无 |
| **标签被误加** | 一次误加 = 一次无人复核的自动合并；`wip`/`do-not-merge` 是唯一的对冲手段 | 无 |
| **必需检查从未上报** | 永远停在 `wait`（不合并、不评论），需要人工合并；反过来，`test (…)` 分片**整个没跑**时判定看不见 | 无 |
| **`CHANGES_REQUESTED` 的"过期"近似** | 我们只按"作者最后一次评审状态"算，不比对提交时间：**force-push 之前的旧 `CHANGES_REQUESTED` 依然阻塞**（偏严，安全的一侧）；`DISMISSED` 会被排除 | 偏保守 |
| **两个 API 的字段形状不一致** | 复核读的是 REST（`mergeable` 是**布尔**），却按 GraphQL 的枚举串比较 → **每个候选都被自拒**：判定说 merge、复核说"no longer a clean candidate"，通道静默失效。2026-09-17 这条通道**第一次真实运行**时就是这样（PR #1796 未被合并），已由 `mergeable_is_clean()` 修掉；教训是这类"读了 A 的形状、比了 B 的拼写"的缺陷，桩回放看不出来，只有真跑一次才知道 | 现在有单测同时钉住两种形状，以及"shell 不得再拿原始拼写比较" |

**信任边界（实现层面的三条硬规矩）**：

1. 工作流 **checkout 默认分支**、绝不 checkout PR 的 head 去执行脚本——否则 PR 可以改自己的门禁来批准自己。
   事实全部来自 API，PR 里的内容一行都不会被执行。
2. 合并不是"决定了就直接合"：合并**前**重新从 API 读 `mergeable` / `state` / `draft` / 标签，任一不满足就
   放弃并打 `::warning::`。
3. 没有标签 = 什么都不做（脚本里还有第二道同样的判断）。

**失败时的表现**：判定之外的一切（取数据失败、`gh pr merge` 失败、环境异常）都只会打
`::warning::` 并以 0 退出——**不会**在贡献者的 PR 上挂一个他无法处理的红灯。
唯一会让这一步变红的情况是脚本退出码不是 0/1/2（那是实现坏了，需要人看）。

---

## 6. 如何回滚

按影响面从小到大：

1. **只影响未来的 PR**：`gh workflow disable auto-merge-lessons.yml`（或 Actions 页面 Disable）。
   立即停止自动合并，其它文件不动。
2. **代码级回滚**：revert 掉引入这条通道的那个 squash commit（一次提交包含工作流、脚本、测试、本页）。
   ```bash
   git revert <引入本通道的 commit>   # 然后照常开 PR、走评审
   ```
   工作流文件消失即通道消失；`scripts/lesson_pr_mergeable.py` 被 revert 掉时，工作流会打一条
   `::warning::… is not on this branch yet` 并退出 0（不会红）。
3. **已经自动合并错了**：**不要**直接改 `main`。开一个 revert PR（`git revert <被合并的 squash commit>`），
   照常走评审合并；如果涉及课程内容，同时按 `docs/maintainer/intake-triage.md` 的口径登记后续动作。
   本通道保留了 head 分支（不删分支），所以原始提交随时可取回。

---

## 7. 维护者速查

```bash
# 判定这条 PR 现在会怎样（本地、离线、与线上同一份逻辑）
python3 scripts/lesson_pr_mergeable.py --json "$(gh api repos/Ikalus1988/MisakaNet/pulls/<N> --jq '{files:[],checks:{},labels:[.labels[].name],draft:.draft,review_state:"NONE"}')"

# 单测（离线、无网络）
python3 -m pytest tests/test_lesson_pr_mergeable.py -q

# 看这条通道最近做了什么
gh run list --repo Ikalus1988/MisakaNet --workflow auto-merge-lessons.yml
```

判定规则改了必须同步改三处：`scripts/lesson_pr_mergeable.py`（规则）·
`tests/test_lesson_pr_mergeable.py`（断言）· 本页的决策表（§2）。

---

## 8. 2026-10-17：标签**存在**、以及"谁把标签打上"这件事

> 本节是**追加**的（本页的日期史不改写）。它记录两件事的实测结论：本页 §3 里"打标签"
> 这一步的现状，以及为什么这一步**不能**在 PR 打开的那一刻做。

### 8.1 前提核对：`auto-merge-lesson` 标签一直都在

要改动这条通道之前的前提是"标签不存在，通道因此从不触发"。**实测前提为假**（2026-10-17）：

```console
$ gh label list --repo Ikalus1988/MisakaNet --limit 300 --json name,description,color \
    --jq '.[] | select(.name=="auto-merge-lesson") | "\(.name) | \(.color) | \(.description)"'
auto-merge-lesson | 0e8a16 | Maintainer opt-in: squash-merge this lesson PR automatically once every mechanical check is green

$ gh pr list --repo Ikalus1988/MisakaNet --state all --label auto-merge-lesson --limit 20 \
    --json number,state,mergedAt
[{"number":1909,…,"mergedAt":"2026-09-20T06:25:09Z"},
 {"number":1908,…,"mergedAt":"2026-09-20T06:26:51Z"},
 {"number":1907,…,"mergedAt":"2026-09-20T09:14:28Z"},
 {"number":1796,…,"mergedAt":"2026-09-17T09:43:22Z"}]
```

标签存在、描述与 §3 的政策一致，并且已经被用过 **4 次**（#1796 是 §5 记的第一次真实运行；
#1907–#1909 是 2026-09-20 的三次）。所以"通道从不触发"的正确原因是**没有任何东西去应用这个
标签**，不是标签缺失。新增一个同名标签是空操作；本页因此只记录核对结果，不改标签。

### 8.2 为什么"在 PR 打开时打标签"是错的（这条决定了实现位置）

本工作流只监听 `labeled` / `synchronize` / `ready_for_review`（`opened` 是**故意**不在里面的），
`check_suite` 兜底也已在 2026-10-02 删除。§1 已经写了它的后果：

> 一个已 opt-in 的 PR 如果在 `synchronize` / `ready_for_review` / `labeled` 之后检查才全绿，
> **不会**自动合并，需要人手动合一次。

于是"pipeline 在开 PR 时顺手打标签"这条**看起来**顺理成章的路径，实际结果是：`labeled` 事件到达时
检查还在跑 → 判定 `wait`（按设计不评论、不重试）→ 检查变绿时**没有任何事件再叫醒这条通道** →
标签挂在那里、PR 永远等人。这正是本仓反复记录的"看起来做了、其实什么都没发生"的形状。

**结论：标签必须在机械条件已经成立的时刻打上。** 而能承载"此刻已成立"的事件只剩时钟 ——
所以这一步落在既有的定时清扫里（`.github/workflows/auto-sync-prs.yml` 的
`arm-lesson-auto-merge` job，调用 `scripts/arm_auto_merge_lesson_prs.py`），**不新增工作流**。

它的判定**不是**第二套规则：脚本 `import` 本页 §2 的判定器（`scripts/lesson_pr_mergeable.py`），
把标签**模拟为已存在**后问它"现在会不会合"；只有答案是 `merge` 才真的打标签。另一条同样硬的要求是
**令牌必须是 PAT**（`secrets.SHELDON_PAT`）：GitHub 会抑制由内置 `GITHUB_TOKEN` 引起的事件，
用它打的标签**不会**触发任何 `pull_request: labeled` 运行——标签看起来打上了，实际什么都没叫醒。
（同一个坑在 push 路径上已经付过三次学费，见 `scripts/ci/land_change.py`。）

清扫范围与"外部贡献者仍然是手动 opt-in"并不冲突：只有 **head 分支在本仓库内** 的 PR 会被考虑，
而本仓库的分支不是外部贡献者能创建的（那需要写权限）——所以集合恰好是"本来就能直接 push/merge 的人"，
外部 fork PR 一个都不碰。`wip` / `do-not-merge` / draft / 被请求修改 / 改动 `lessons/` 之外的文件，
全部由共用的判定器拒绝。

### 8.3 还没被证明的那一步（只在真实 PR 上才能观测）

本节的实现只证明了"标签会在正确的时刻被打上，且判定与通道完全一致"（`tests/test_arm_auto_merge_lesson_prs.py`，
含 `test_arming_means_the_label_is_the_only_thing_missing` 这条不变量）。**"打上标签之后通道真的被叫醒并合并"
至今没有在本次改动里观测到**——历史上它只在 #1796 上跑通过一次。要看的是：

```bash
# 1) 标签是否由 PAT 打上（不是 GITHUB_TOKEN）：run 的 triggering_actor 应是普通账号
gh api repos/Ikalus1988/MisakaNet/issues/<PR> --jq '[.labels[].name]'
gh run list --repo Ikalus1988/MisakaNet --workflow auto-merge-lessons.yml --limit 5

# 2) 那次 run 的日志里有没有 `verdict (exit 0): merge` 与合并动作
gh run view <run-id> --repo Ikalus1988/MisakaNet --log | grep -E "verdict \(exit|mergeable"
```

若第 1 步里**没有**出现 `auto-merge-lessons` 的新 run，唯一原因就是令牌：`SHELDON_PAT` 为空时
清扫只打 `::warning::` 并跳过（它绝不用 `GITHUB_TOKEN` 去补），因为那个标签是"打了也没用"的。

### 8.4 残余缺口（写在前面，不留给下一个人发现）

* **armed 之后又被 push**：`synchronize` 会让通道重新判定；若那次 push 之后检查才全绿，标签已在，
  没有人再叫醒通道。清扫的 6 小时周期**不会**重打一个已存在的标签（重复打标签不产生事件，
  只是一个看起来像动作的空操作）。这与 §1 记录的安全侧是同一件事，修法（扫描时对"已 armed 且判定为
  merge"的 PR 做 remove+add 重新触发）**故意没有做**：那会在真正的阻塞（如冲突）上每 6 小时制造一次
  无意义的重新触发，而收益是一个已知需要人类合一次的窄窗口。
* **判定所需的事实全部读 API**：清扫与通道都不执行 PR 的内容；清扫 job 用全新的
  `actions/checkout` 只取默认分支（sync job 会 checkout 贡献者分支，所以这一步**不能**放在那个 job 里，
  否则等于用写权限执行 PR 带来的脚本副本）。
