# External PR Triage Window（维护者 SOP）

> 适用：**外部作者开来的 PR**（fork 或同仓但非维护者）。目的：把"审阅队列"从"谁先看见谁回"
> 变成**每周一个固定窗口**，让真贡献排在前面，让模板产物在进入人工之前被机械判据挡掉。
> 主 SOP 见 `docs/maintainer/intake-triage.md`（报料类 issue）；本文件只管 PR。

## 1. 为什么要有窗口

2026-09-22 一个会话里，同一个自动化账号开了 8 条 bounty PR，**每条都写了一次长评论**（#2066 的实测记录）。
2026-09-26/27 又来四条：根目录 `ai_solution.py`、`solutions/issue_2283_solution.ts`、一条把
`pyproject.toml` 删成两行的重写、一条改 `check_provenance.py` 却认领"写一篇课"的任务——**每一条都花了一次人手**，
而四条里有三条是**不需要判断**的。窗口的意义就是：机械的归机械，判断的归判断，剩下的排在窗口里一次看完。

## 2. 窗口怎么跑（每周一次，30 分钟足够）

```bash
# 1) 列出来
gh pr list --state open --json number,title,author,createdAt,mergeable,isDraft \
  --jq '.[] | "\(.number)\t\(.createdAt[:10])\t\(.author.login)\t\(.mergeable)\t\(.title[:70])"'

# 2) 机械判据先说话（在 PR 上就是 PR Shape Guard；本地同一个模块）
gh api --paginate repos/Ikalus1988/MisakaNet/pulls/<N>/files --jq '.[].filename' > /tmp/changed.txt
gh api repos/Ikalus1988/MisakaNet/pulls/<N> --jq '.title + "\n" + (.body // "")' > /tmp/pr-text.txt
git show <base>:pyproject.toml > /tmp/base-pyproject.toml
python3 scripts/pr_shape_guard.py --changed-files /tmp/changed.txt --pr-body /tmp/pr-text.txt \
  --base-pyproject /tmp/base-pyproject.toml --head-pyproject /tmp/base-pyproject.toml

# 3) 每条的现状（不要看 check 的图标，看结论与日志）
gh pr checks <N>
```

**四条机械判据**（`scripts/pr_shape_guard.py`，纯函数、有单测，见文件头）：

1. 根目录 `solution*` / `ai_solution*` / `test_solution*` 或新建 `solutions/` → **交付物不是它**；
2. `pyproject.toml` 丢掉 `[build-system]` / `[project]` → 破坏了打包（#2061–#2063 的形状）；
3. 认领 `misakanet-question-bounty` 任务却**没改 `lessons/{core,contrib,en}` 下任何文件** → 交付物缺失；
4. （原有）生成器残留文件名、破坏性 README 重写、source 文件里贴了 markdown/diff；
5. 文件落在仓库**没有**的点目录下（`.ai_bounty_patches/` 这类）→ 是某个工具自己的草稿，不是项目的一部分；
6. 新增**顶层目录** → 仓库的布局是已经定过的决定，不是 PR 顺手就能加的。

判据 5 与 6 的"仓库有什么"不是本文件里的一张常量表，而是工作流从**可信 base 检出**里读出来的
（`git ls-tree -d --name-only HEAD`）——常量表会在仓库第一次新增目录时过期，读树不会。
判据 6 有一条声明式例外：PR 正文里写 `<!-- shape-guard: allow-new-top-level-dir -->`。

> **注意 lesson 门禁在"没有课"时是绿的**：`lesson-gate.yml` 为了让必需检查永远上报，在没有
> `lessons/**/*.md` 命中时**故意成功**。所以"Lesson Quality Gate ✅"**不代表**交付物存在——这正是判据 3 存在的原因。

## 3. 判定与动作（每条只走一个）

| 判定 | 判据 | 动作 |
|---|---|---|
| **合并** | 交付物是任务要的那个、门禁绿、证据可复现 | squash 合并；在 issue 里 @ 作者致谢（信用/排行榜/Hall of Fame） |
| **采纳（adopt）** | 内容对，但 PR 里混了生成物/冲突/改动面过大 | 由维护者用干净分支重提，commit 写 `Co-authored-by:`，原 PR 关闭并说明可重开（2026-09-26 #2299 → #2316 的先例） |
| **要求修改** | 差的是小项（缺 frontmatter、字段超长、缺 `Signed-off-by`、证据是编造的） | 一条评论列**最小修复顺序**（第一项能过门禁的那种），保留 PR；draft 的等作者回来 |
| **关闭** | 交付物不存在 / 答错 issue / 内容与任务无关 / 与已合入项重复 | 一条评论说明**为什么不能合**（引用任务正文的原句），给出重试路径；已解决的 issue 一并结账 |

**铁律**（与主 SOP §3 一致）：**关闭也要给理由**，且理由要指到任务正文的具体句子——"不符合要求"不是理由，
"任务要的是 `lessons/` 下的课，这个文件不在索引路径里，所以 `misakanet_search` 永远不会返回它"是理由。

## 4. 收尾清单（窗口结束前）

- [ ] 每条 open PR 都有标签（`shape-risk` / `needs-dco` / `shape-safe` / `reviewed`），没有"看过但没留痕"的；
- [ ] 被判"要求修改"的，评论里第一条是**能让它变绿的最小改动**；
- [ ] 被判"关闭"的，若它对应的 issue 已交付，**把 issue 也关掉并写明交付物落在哪**（否则悬赏任务会一直留在待认领列表里）；
- [ ] 被采纳的，`Co-authored-by:` 已在提交里，PR 正文指回原 PR；
- [ ] 追记：把本窗口新出现的**垃圾形状**写进 §2 的判据（判据 3 就是这么来的）。

### 2026-10-22 窗口的追记

**进 §2 机械判据的**：内部生成物（`.ai_bounty_patches/bdcaa82152a267ce_edit_plan.patch`，
是 bounty 工具写下的补丁草稿，而它正是同一个 PR 里的测试文件的补丁草稿）与新增顶层目录
（`hooks/`）。两条都是**关于仓库形状的事实**，不是对工作质量的判断，所以能机械化。

**留在 §3 人工判据的**：**PR 认领的 issue 与它实际改的东西无关**。
#3748 认领 #3697（OpenClaw 上 `--verify` 永远报钩子缺失），却加了一个通用的"拦截破坏性 bash"的
pre-tool-use 脚本，**一行都没碰** `packages/misakanet-setup/bin/misakanet-setup.mjs`——而那个文件正是
`--verify` 的实现所在。这条**没法机械化**，理由有两条：

1. issue 正文里的 `**Kind:**` 是启发式推断出来的（`scripts/intake_kind.py`），它可能不准——
   #3697 的 kind 是 `new_lesson_candidate`，但它其实是个产品缺陷，靠代码修才对；
2. issue 正文**常常不点名仓库路径**（#3697 通篇没有），所以"改了不相关的地方"缺少可判的依据。

所以它留在 §3 的判定表里（"答错 issue" → 关闭），而不是 §2 的机械判据里。
**把一条判据硬做成机械的，代价是误报；而误报的判据会教贡献者忽略守卫。**

## 5. 现存窗口待处理（2026-09-27 快照）

`#1544` `#1716` `#1801` `#2037` `#2068`（判据已由 #2332 落地，见其评论）`#2090` `#2304` `#2293` `#2294` `#2295`。
每条按 §3 走一个判定；`#2293`–`#2295` 已给最小修复清单，等作者。
