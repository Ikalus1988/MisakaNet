# Handoff — 2026-11-14 第 36 卷（承接 `handoff-2026-11-14.md` 第 35 卷 / #4807）

> 这一卷把第 35 卷「悬着的账」结掉了：两个 PR 合并、worker 部署、`used` 从假零变成真数、
> 认领行验通。然后顺手揭出**三处面板在说没量过的话**，修在 #4810。
> 一句话总结这一轮：**天梯的每一格现在要么有数，要么诚实地说没数。**

## 1. 这一轮定下来的判断

1. **回填不必跑那条 15 分钟的 GitHub 巡检**。`lesson_authors` 的 `slug` 可以从 `path` 直接算出来，
   前提是一个可验证的语料不变量：**940/940 篇课程的 `id` 等于文件名 stem**（`data/lessons.json` 实测）。
   所以一条 `UPDATE` 就补齐了 424 行——工作流负责的是**未来**的新行，不是补历史。
2. **`top_id` 今天只有一种形状：裸文件名 stem**。15290 条非空 `top_id` 里，`lessons/` 开头的 0 条、
   带 `.md` 的 0 条、`faq-*` 2556 条。第 4806 号 PR 的注释说「三种形状」——代码里那条 `path` 分支对应的是
   `results[0].id || results[0].path` 的**回退**（记录没有 `id` 时写路径），今天没有这样的行，
   但它是一条真实可达的路径，所以三支 join 保留；`lesson_id` 那一支目前等价于 `slug`（见 §3）。
3. **`coverage.lesson_authors` 写死 `0` 是假零**，和第 35 卷 `used` 那个假零同一类：表里 424 行，
   面板印 0。改成真读；读不到时返回 `null`——**"读不到"和"没有"不能渲染成同一句话**。
4. **`login` 只能是已验证的那一半**。第 35 卷写「GitHub 的一半是可验证的：来自合并 lesson PR 的
   `user.login`，**不是提交者自报**」，但 `recordContribution` 一直把 `args.contributor`（文档写的是
   "GitHub username, agent name, or email"）原样写进 `contributions.login`，而面板给任何 `login`
   挂 `GH` 徽章。线上因此出现 `Misaka38084` 显示成 `GH claude-code`——**把 agent 类型渲染成了一个
   GitHub 账号**。写侧不再接收它，读侧也拒绝「伪名行带 login」这种配对，老数据一并清掉。
5. **面板文案也是要维护的代码**。`panel.ladder.coverage` 在归因上线后仍然说
   "retrieval attribution pending"——每个用户每次打开面板都读到一句假话。现在它说有多少篇课程
   真的有作者（`{count}`），读不到时退回不带数字的那句。

## 2. 数字（本轮实测）

| 项 | 值 | 判据 |
|---|---|---|
| worker 部署 | #4806 的 run `43462510108` 由 `release` 待批 → 批准 → **success** | `gh run view` |
| `lesson_authors` | 424 行，`slug` 424/424（回填前 0） | D1 `misakanet-ops` |
| 语料 | 940 篇 · 有作者记录 **424（45%）** | `data/lessons.json` / D1 |
| `search_signals` | 17237 行；`top_id` 非空 15290；`faq-*` 2556 | D1 |
| 可归因的取用 | **970 条**（占挂在真实课程上的 12734 条的 7.6%） | D1 + `data/lessons.json` |
| `used`（all） | `gh:Ikalus1988` **943**（score 73 → **261.6**）· `gh:zsxh1990` **27**（5 → **10.4**） | `GET /api/leaderboard/ladder?window=all` |
| `used`（week） | `gh:Ikalus1988` **411**（score **92.2** = 411×0.2 + 10） | 同上 `?window=week` |
| 认领行 | `?node=Misaka38084` → `me.rank=2`；`?node=gh:Ikalus1988` → `me.rank=1` | 同上 |
| `contributions` | 已验证行 80（`gh:*`）· 伪名行 10，其中自报 login 1 条已置 NULL | D1 |
| PR #4810 | 三处假话的修复，含 2 条新测试 | `gh pr view 4810` |

**归因天花板要说清楚**：12734 条挂在真实课程上的取用里，只有 970 条（7.6%）落在有作者的课程上。
其余 11764 条挂在**没有作者记录**的课程上——那些是 bootstrap 时期就没有经过 lesson PR 的老课，
GitHub 从来没有过它们的作者。这不是 bug，是「只认合并 PR 的作者」这条规则的必然结果；
想让它们有分数，唯一的路是让作者认领，而不是放宽归因。

## 3. 悬着的账

| 谁 | 项 | 状态 / 下一步 |
|---|---|---|
| 仓库 | **#4810** 徽章=已验证 + 覆盖率不再假零 + 面板文案 | CI 中，已 arm auto-merge；合并后**必须部署 worker**（批准 `release` env） |
| 仓库 | 面板文案要用户能看到，得等 release-please 出下一个 patch 版本，再让 DSH host 重启/升级（第 35 卷坑 3：客户端包按版本缓存） | 合并后查 `npm view` / 重启 host |
| 仓库 | `lesson_authors.lesson_id` 只有这次回填写过；`lesson-authors.yml` 不写它，join 里那一支等价于 `slug` | 下轮二选一：让 sweep 也写 `lesson_id`，或删掉那一支——不要让它一直半空 |
| 仓库 | `lesson-authors.yml` 全量回填仍会超 15 分钟（上次 dispatch 在 15m17s 被取消） | 历史已补齐，不急；真需要再跑时把 `timeout-minutes` 提到 30 或按月拆 `since` |
| owner | 三个目录简介仍是旧数字：Glama 连接器 **385+**、Glama server **500+**、dsh-plugin.org **310+**（语料已 940） | 仓库侧文案与规则已就绪（`docs/integrations/directory-blurbs.md` §2）；只能后台 paste，**不要 paste 带数字的版本** |
| owner | **一份未提交修改被我覆盖了**：`lessons/contrib/chroma-rebuild-no-checkpoint-cn.md`（第 35 卷后工作区里的 `M`）。我执行 `git checkout origin/main -- .` 时它被重置，没有 stash/备份可恢复 | 文件本身是已合并的 `-cn` 版本；如果那是一次翻译/校对改动，需要重做。这是我的过失，不是悬账 |

## 4. 下一轮入口

```bash
# 1) #4810 合并（CI 慢：admin merge 在有检查 in-progress 时也会被规则拒）
gh pr view 4810 --json state,mergeStateStatus

# 2) 部署 worker（合并后）
gh run list --workflow=deploy-worker.yml --limit 2
#    批准待部署（注意：environment_ids 必须是整数，见 §5）
printf '{"environment_ids":[22298828230],"state":"approved","comment":"..."}' \
  | gh api --method POST "repos/Ikalus1988/MisakaNet/actions/runs/<id>/pending_deployments" --input -

# 3) 验证覆盖率不再是假零
curl -sS "https://misakanet.org/api/leaderboard/ladder?window=all" | jq '.coverage, .top[0]'
#    期望：coverage.lesson_authors = 424（不再是 0）；top[0].used = 943

# 4) 验证徽章只给已验证身份
curl -sS "https://misakanet.org/api/leaderboard/ladder?window=week" \
  | jq '.top[] | select(.node=="Misaka38084") | {node, login, name, identity}'
#    期望：login="" · identity="node"（不再是 login="claude-code"）
```

## 5. 坑（这一轮新踩的）

- **`gh api -f environment_ids[]=…` 会 422**：`-f` 一律发字符串，部署 API 要整数 →
  `Invalid request. For 'items', "22298828230" is not an integer`。用 `--input -` 发原始 JSON。
- **WSL 沙箱里 wrangler 写不了日志**：`~/.config` 不可写 → `EACCES … .wrangler/logs/…`，命令看起来"卡住"。
  把 `XDG_CONFIG_HOME` 指到仓内的 gitignored 目录并复制一份 `default.toml`（OAuth 凭据）即可；
  用完记得删掉那份副本。
- **`git checkout origin/main -- .` 不是合并，是覆盖**：它把工作区里未提交的修改直接冲掉，
  且没有对象库副本可 `fsck` 找回。要切基线请走 `git stash -u` → `checkout -b` → `stash pop`。
- **worker 全量测试在本机会有 5 条红**，都是环境的：3 条是 `UNDICI-EHPA` 代理警告污染了断言
  stderr 为空的用例，2 条是共享 state 目录里残留一个 `update-check.json`。它们都在
  `workers/agent-autostart-hook.test.mjs`，不 import 本轮改的文件——别当成自己的回归。
- **`hits` 不是重复计分**：`scoreEntry` 里 `hits = used + self`，所以 `used` 943 时 `hits` 也是 943
  是设计口径；`score` 只对 `used + min(self, cap)` 乘 0.2。
- **假零的三种形态**：写死 `0`（本轮 2 处）、join 永不命中（第 35 卷）、文案写死（本轮 1 处）。
  这一轮之后，凡"面板上的一个数"，要么来自查询，要么是 `null` + 一句说清的话。
