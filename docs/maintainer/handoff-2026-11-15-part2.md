# Handoff — 2026-11-15 part2（vol 39）

> 承接 `handoff-2026-11-15.md`（vol 38）与它的 `-addendum`。这一卷只写**判断、实测数字、悬账、下一轮入口**
> 和踩到的坑（`handoff-rules.md` §5）。日记不写在这里。

本轮合并 **18 条 PR**（`#4952`–`#5031`），语料 **941 → 949**，两个 registry 对齐，code scanning 清零。

---

## 1. 本轮判断（下次别重新推导）

### 1.1 事件钩子只做加速，状态对账才是真相源

190 条 run 在队列里"卡死"：`status: queued` 永久不变，`cancel` 回 `409 Cannot cancel a workflow run
that has not been queued yet`，`delete` 回 `403`，而**同一工作流后来创建的 run 正常跑完** —— 所以它们
不在调度器的队列里，是记录层的僵尸。最老的 **2117 小时（≈88 天）**。

推论分三层，顺序不能反：

1. 它们即使真跑，载荷也已经过期：给几个月前的课发"已发布"通知、给早已关闭的 issue 重贴标签。**跑起来价值为负**；
2. 追取消/删除在平台层面不可能（409/403 是实测，不是推断）；
3. 真正的缺陷是**设计**：这些 workflow 都是"一次事件 = 一次有时效副作用的执行"，于是被丢弃的 run
   不是"延迟"而是**静默丢失的动作**。

所以方向是**让副作用可从状态重新推导**（每日对账"哪些已合入的课还没被宣告""哪些标签与正文不符"），
事件钩子只负责加速。190 条记录本身不用管；`approval-watch.yml` 现在把它们的**计数与最老时长**留在
审批追踪 issue、**完整列表进 step summary**（不通知、不进队列）。

### 1.2 Windows 上不能跑语料生成器（两种失效形态，都无报错）

| 实测 | 症状 |
|---|---|
| 同一套生成器在 Windows 上 | **778** 篇而不是 940 —— 文件名非 ASCII 的课**全部消失** |
| 生成器写出产物（数量对的情况下） | 21 个 tracked 文件变成 CRLF，diff 是 `102549 insertions(+) / 102549 deletions(-)`：内容一样、每行都变 |

POSIX（WSL）侧同一套命令给正确结果。`scripts/rebuild_lesson_pr.py` 因此**在 `os.name == "nt"` 上直接拒绝**，
拒绝文案里带这两个数字（否则下一个人会重试），`--allow-windows` 是给"自己核过语料数与 `git diff --stat`"的人的逃生门。

### 1.3 lesson PR 冲突的解是**重建**，不是解冲突

每合并一条 lesson PR，其余 lesson PR 就在 `data/lessons.json`、`docs/data/*.json`、`lessons/index.md`
上 DIRTY —— 那些是生成物，手解等于让下一次生成把它们覆盖掉。正确形状（今天手跑了 5 次，已固化为脚本）：

```
只取 PR head 里的 lessons/** → 干净分支从 origin/main 切 → 重跑 7 个生成器 + 重算证据表 → 提交（-C 原提交 + Co-authored-by）
```

`scripts/rebuild_lesson_pr.py <pr> [--commit] [--push]`，四条拒绝是它的价值所在：工作区脏、`lessons/`
下有未跟踪 `.md`、出现既非 lesson 也非生成物的路径、**重建后某篇课不在索引里**（这正是 frontmatter
引号未闭合从外面的样子 —— 今天 19 篇 adopt 里 3 篇是这毛病，别的地方一个都不报）。

### 1.4 release PR 什么时候可以合

判据只有一条，**先验再合**：

```console
# 同步之后有没有新提交碰过这个包的路径？空 → changelog 完整，可以合
$ git log --oneline --since="<该 PR 上次同步时间>" origin/main -- packages/<pkg>/
```

今天用两次：`misakanet-setup 0.10.1`（#4767）与根包 `3.17.0`（#4936）。合完的链路是
tag → `gh workflow run <publish>` → `environment: release` 审批 → registry，**npm 与 PyPI 都对齐了**。
这也是 `#4957`（先派发、后打 tag）的第一次实战：dispatch 与 tag 都产生，旧代码那种"tag 建好、派发 403
之后再没人管"的死状态没有出现。

### 1.5 赏金"每簇一次"是真的会把事推进的

`question_autopilot.py --post --bounties` 今天建了 **10 个 $0 簇包**（#4996–#5005，覆盖 36 条问题）。
两个后果值得记：

- **$0 赏金 20 分钟内就吸引机器产出**：4 个 PR 各新增 `submissions/bounty_<n>_<author>/SOLUTION.md`，
  内容是编造的（`misaka` CLI、`MCP Python SDK v2.3.1`、`MisakaNet Node Environment v0.12.4-alpha` 全不存在）；
  `pr_shape_guard` 原本只认 `solution*.py` 与 `solutions/`，**`submissions/` 是第三种拼法**，已补；
- **同一个簇也会被真人做完**：`zsxh1990` 一天提了 4 个 lesson PR，三条走 adopt、一条 29/29 全绿直接合并
  （`#5031`，5 篇课正好是我排队要做的 #5006/#5011/#5013 那几条）。

## 2. 实测数字（2026-11-15）

| 项 | 值 |
|---|---|
| 语料 | **949**（941 → 949） |
| 合并 PR | 18 条（#4952 … #5031） |
| 关闭 intake | #4947、#4931、#4932、#4933（回执 + 关单） |
| `needs-info` 回信 | #4835、#4859、#4963 |
| npm `@misaka-net/misakanet-setup` | **0.10.1**（漂移 3 天后收口） |
| PyPI `misakanet` | **3.17.0** |
| Code scanning open | **0**（#405 按 `won't fix` + 真修：0600 在创建时生效） |
| 卡死 run | **190** 条，最老 2117 h —— 不可取消、不可删除 |
| 数据集发布审批 | 两天 **8 次**点击 → 改每日日程（#5030） |

## 3. 悬着的账

| # | 事项 | 状态 / 谁欠 |
|---|---|---|
| 1 | `#4989` i18n README（#4751） | 等作者补 `README.ko.md` 最后三个徽章（dshfind / dsh-plugin.org / dsh.so，**顺序也要对**） |
| 2 | `#5030` 数据集改日程 | 等 CI；合并后逐次推送触发消失 |
| 3 | 59 条 open question | **需要 owner 一句"可以"**：按簇作答（MCP 客户端 ~45 条、Windows 桌面/GUI ~12 条）才由维护者署名写 |
| 4 | `#4874`/`#4889` 的 draft 账 | 走同一条 adopt，但"promote/retire"是判断题，不是机械活 |
| 5 | 数据集还嫌吵？ | 再挪到 `automation` 环境 → 0 点击；要移动写凭据，只有 owner 能做 |
| 6 | GSC 首拉 | **11-16 之后**才有行（属性 11-14 才验证） |
| 7 | 190 条卡死 run | 无解；若再爆一批，当作"某个事件型 workflow 需要状态对账"的信号 |

## 4. 下一轮入口（可直接粘）

```console
# lesson PR 冲突：一条命令重建（必须 POSIX）
$ wsl -e bash -lc "cd '/mnt/c/Users/Eric Jia/MisakaNet' && python3 scripts/rebuild_lesson_pr.py <pr> --commit"
$ git push --force origin rebuild-<pr>:<head-branch>

# 陈旧 needs-dco 标签（先看 dco 是否自己重跑过）
$ python3 scripts/dco_label_backfill.py --dry-run

# 发布漂移（三处比对：manifest / tag / registry）
$ python3 scripts/ae_query.py --days 1        # 需要 CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID
$ curl -s https://misakanet.org/api/health | jq -r .commit_sha

# 改过课程之后（POSIX！顺序不能反；先确认 lessons/ 下没有未跟踪 .md）
$ python3 scripts/update_lessons_json.py && python3 scripts/build_lesson_pages.py \
  && python3 scripts/sync_lesson_count.py && python3 scripts/export_okf.py \
  && python3 scripts/rebuild_lessons_index.py && python3 scripts/export_public_vocabulary.py \
  && python3 scripts/gen_ranking_snapshot.py
```

## 5. 坑（都是本轮实际踩到的）

1. **超长 commit message 会让自己的 trailer 消失**。#4986 有一条 74,704 行的提交信息（`git log --format=%B`
   生成消息文件时把整段历史灌了进去），GitHub 的 DCO 审计读到截断的消息，看不到末尾的 `Signed-off-by`，
   判"缺签" —— 症状是"明明签了却说没签"。
2. **`Co-authored-by` 写错位置就丢**。git 只从**最后一段**读 trailer：用第二个 `-m` 追加"重建说明"会把
   `Co-authored-by` 挤到 trailer 块之外，提交里只剩 `Signed-off-by`，**没有任何失败**。说明要在 trailer 之前。
3. **两点 diff 会把主分支新增的文件算成 PR 的改动**。`git diff origin/main <head>` 让重建脚本把**它自己**
   认成该 PR 的改动并拒绝；必须用 `git merge-base` 三点语义。
4. **`git show <ref>:<path> | python3` 在 Windows 上会毁掉 UTF-8**（管道走了本地代码页），JSON 解析报
   `Expecting ',' delimiter`。先重定向到文件再读。
5. **在 bash 里内联带反引号的 `gh` 评论正文会被 shell 当命令替换**：`` `main` `` 变成 `main: command not found`，
   评论里那段文字被吃掉。正文写进文件，用 `--body-file` / `-F body=@file`。
6. **Windows 生成器的两种失效形态**见 §1.2 —— 它们都**不报错**。
7. **监视器自己也会卡在队列里**：`approval-watch.yml` 的一次 run 在 11:15 是 `queued`。所以监视器的输出
   只能靠"上一次成功运行"留下的 step summary / issue 正文，别指望它实时。
