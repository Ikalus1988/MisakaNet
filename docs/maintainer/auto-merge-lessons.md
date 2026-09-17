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
| `check_suite: completed` | 兜底：某个检查套件跑完时再判一次 |

> ⚠️ **关于 `check_suite` 的实话**：社区多份报告（[discussion #26169](https://github.com/orgs/community/discussions/26169)、
> [#26236](https://github.com/orgs/community/discussions/26236)）指出，**由 GitHub Actions 自己创建的
> check suite 完成时不会触发 `check_suite` 工作流**，只有别的 GitHub App 产生的套件才会。
> 本仓的机械检查恰好都是 Actions 工作流，所以这条触发**很可能根本不响**——它写在那里是零成本的兜底，
> **真正干活的是 `synchronize` 与 `ready_for_review`**。也就是说：检查全绿之后如果没有任何新事件，
> 合并可能不会自动发生，需要人手动合一次（这也是"安全的一侧"）。

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
