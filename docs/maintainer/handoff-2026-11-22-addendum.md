# Handoff — 2026-11-22（vol 44 补遗）

> 承接 `handoff-2026-11-22-part2.md`（vol 44）。补两件**卷末才发生**的事：收据真的发出去了，
> 以及"发出去"之后运行是怎么在落地之前被取消的。

---

## 1.5 修好第一步，第二步的上限就露出来了

`#5578` 合并后手动触发了一次 `update-lessons.yml`（run 45039931336），收据步骤 **6 分半钟
发完了全部 318 条**（日志里 318 行 `✅ Receipt posted`，0 行 `Comment FAILED`）——
`github.token` 就是那三天的原因。

然后下一步把它全废掉了：

| 步骤 | 时间 | 结果 |
|---|---|---|
| Emit intake receipts | 15:45:15 → 15:51:46 | 成功，318 条已发出 |
| Close any intake whose lesson already exists | 15:51:46 → 16:04:57 | **被 20 分钟作业上限取消** |
| Check for changes / Land the regeneration | —— | 跳过 |

`intake_receipt.py --sweep` 对**每条 open intake** 调一次 `lessons_citing()`，而后者读**全部**
课程文件：461 × 1121 ≈ 50 万次文件读。13 分钟没跑完 → 作业被取消 → **记账那一步没执行**。
仓库里 `data/intake_receipts.jsonl` 依旧没有这 318 行，而它是这个作业唯一的记忆。

**判据**：幂等的前提是"做过的痕迹"**先**落地，不是"再做一次会很快"。
一个「先做外部写入（评论、关闭 issue）、后提交记账」的作业，崩溃面正好落在两者之间，
后果是**重复写入**而不是重试——所以记账文件必须与外部写入在同一批改动里落地，
或者外部写入必须自带幂等键（这里是 issue 号 + 课程路径，可惜没有去重查询）。
这次是手工按运行日志把 318 行补回去的（`#5580`）；结构上的修法是把 sweep 的读次数从
O(队列 × 语料) 降到 O(语料)（`#5581`，同一队列 **13 min+ → 7.7 s**）。

**顺带记下**：`gh run view --log` 只在整个运行结束后才可读，但**被取消的运行**里，
已完成步骤的日志仍然能取到——这次就是靠它把 318 条回执一行不少地重建出来的。

---

## 2 数字更新（卷末）

| 项 | 值 | 判据 |
|---|---|---|
| 语料 | 1121 | `data/lessons.json` |
| 回执：引用 / 已记 | **668 / 668** | `emit_intake_receipt.py --check` → "up to date" |
| 一次 sweep 的墙钟 | **7.7 s**（原 13 min+ 未完成） | `time python3 scripts/intake_receipt.py --sweep` |

---

## 3 悬账（只列卷末变动的）

- **等一次真跑**：下一次 `00:00Z` 的定时运行才是"收据 + 收尾 + 落地"三件事第一次同跑成功的
  证据。看两处：`Emit intake receipts` 是否 0 输出（已无欠账）、`Land the regeneration` 是否
  真的开了 PR 或打印 `nothing to land`。
- 若那次又被取消，先看 `Close any intake whose lesson already exists` 的耗时——它是唯一还在
  做逐条 `gh` 写入的步骤，改法同样是"先算清集合，再批量写"。
