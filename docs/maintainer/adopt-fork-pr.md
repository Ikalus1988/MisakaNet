# `/adopt` —— fork PR 签核短路径（维护者手册）

> 来源：[issue #1778 — fork PR 签核短路径：`/adopt` 收养流程（不依赖 PAT）](https://github.com/Ikalus1988/MisakaNet/issues/1778)
> 相关文件：`.github/workflows/adopt-pr.yml`（触发与编排）· `scripts/adopt_pr.py`（计划与执行）· `tests/test_adopt_pr.py`（离线测试）
> 先例：[PR #1756](https://github.com/Ikalus1988/MisakaNet/pull/1756) —— 维护者用 `Co-authored-by: 2lll5` 把别人的工作落地成 squash commit
> 状态：本文件描述的能力已实现；PAT 方案（§6）**未执行**，需要维护者自己配 secret

---

## 1. 什么时候用（以及什么时候别用）

`/adopt` 只解决**一个**问题：**fork PR 的内容没问题，只差 `Signed-off-by:`**。

`fix-dco.yml` 能自动给**同仓 PR** 补签核并 force-push，但对 fork PR 做不到——默认 `GITHUB_TOKEN`
没有 fork 的写权限，workflow 会停在名为 *"Handle fork PR — manual instructions only"* 的步骤上，只打印
"请你自己 rebase"。2026-09-16 的实测据此确认（#1746–#1750、#1656 六个 PR 全部因缺签核停滞）。

| 情况 | 用哪个 |
|---|---|
| fork PR，**只**缺 `Signed-off-by`，其余检查都过 | ✅ `/adopt` |
| 同仓 PR，缺 `Signed-off-by` | ❌ 用 `/fix-dco`（`fix-dco.yml` 能直接推自己的分支） |
| fork PR 但**内容/CI 本身还有问题**（课程门禁、注入扫描、测试失败……） | ❌ 别收养。收养只补签核、不改内容，收进来还是红的——先让作者改 |
| PR 相对 `main` **有冲突** | ❌ 别收养。`/adopt --apply` 会在冲突处停下并**不推送**（见 §5），让作者自己 rebase |
| PR 的 base **不是 `main`** | ❌ workflow 会直接拒绝并说明（保守起见只往 `main` 落地） |
| PR 只有空提交 / 已经全部签核 / 分支已存在 | ❌ 脚本按 §5 拒绝，`/fix-dco` 或人工处理 |

**判据一句话**：这条路径把"贡献者的工作"和"一个机械性的 DCO 卡口"分开——它只补后者，永不替作者改内容、解冲突或评判代码。

---

## 2. 两步评论流程（照抄即可）

两步都在**原始 PR** 的评论区发，且评论者必须是 `MEMBER` / `OWNER` / `COLLABORATOR`（`author_association` 判定，
与 `fix-dco.yml` 一致）。

### 第一步：看计划（dry run，不写任何东西）

```
/adopt
```

几秒后 bot 会在该 PR 下贴一条评论，内容是一份**有序计划**：

- fork 的 clone URL 与 head 分支/SHA、从哪儿 fetch（以及 fork 已删除时的回退 `origin refs/pull/<n>/head`）；
- 要跑的 rebase 命令、目标分支 `adopted/<n>`、新的 `Signed-off-by` 身份；
- 新 PR 的标题（**原样不变**）和**完整正文模板**（含 `Co-authored-by:` 行、原 PR 链接、原正文逐字引用）；
- `gh pr create` / `gh pr comment` / `gh pr close` 的完整命令。

dry run **不写任何东西、不访问网络**：只读本地 refs 与 API 已经取回的 commit 列表（这也是
`tests/test_adopt_pr.py` 里 `test_dry_run_performs_no_writes` 断言的"refs 与 reflog 一字不变"）。

### 第二步：执行

确认计划无误后，同一条 PR 下再发：

```
/adopt --apply
```

bot 会依次：fetch fork 的提交 → 建 `adopted/<n>` → `git rebase --signoff main` → push 同仓分支 →
`gh pr create --base main --head adopted/<n>` → 在新旧两个 PR 上留评论 → `gh pr close <原PR> --delete-branch=false`。
全过程 **不写 fork、不 force-push main、不碰别的分支**。

> 想先看计划再执行第三步以外的动作？不需要——`--apply` 会重新跑一遍全部前置检查，
> 计划与执行之间 fork 若被作者 push 过，脚本会以"fork 已移动"中止（见 §5）。
>
> 网络/环境不允许的时候，维护者也可以本地跑同样的两步（`--apply` 需要本地能 push 本仓）：
>
> ```bash
> python3 scripts/adopt_pr.py 1656 \
>   --head-repo https://github.com/TaherEzzi/MisakaNet.git \
>   --head-branch fix-issue-1652 --head-sha 3bbc508dff820335552c1889240cd072f4114f0b \
>   --head-label TaherEzzi:fix-issue-1652 \
>   --author 'Taher Ezzi <taherezzi.dev@gmail.com>' --author-login TaherEzzi \
>   --title 'fix: resolve #1652 - ...' --body-file /tmp/original-body.md \
>   --commits-file /tmp/pr-1656-commits.json      # 可选：离线判定签核状态
> # 确认后加 --apply --body-out /tmp/new-pr-body.md --comment-out /tmp/notice.md
> ```

---

## 3. 它对贡献者署名做了什么（credit）

这是收养流程最需要说清楚的部分：

1. **被收养分支上的 commit，author 仍是原作者**。`git rebase` 只重放补签核，不改作者；收养者只在
   committer / `Signed-off-by:` 位置出现（`Signed-off-by: <adopter> <adopter@users.noreply.github.com>`）。
   `scripts/adopt_pr.py` 在推送前会**比对重放前后的作者集合**（`authors_preserved`），出现陌生的作者身份会
   在日志里告警——`--apply` 的输出 JSON 里也有这个字段。
2. **新 PR 正文里带 `Co-authored-by: <原作者>`**，并逐字保留原 PR 正文与链接（先例 #1756）。
3. **合并方式影响 credit，这里必须讲实话**：
   - 用 **merge commit** 合并：作者身份原样保留（就是第 1 条）。
   - 用 **squash 合并**：GitHub 会把 squash commit 的 **author 设成新 PR 的作者**（也就是跑
     `/adopt --apply` 的机器人/维护者账号），所以**必须把 `Co-authored-by:` 那行留在 squash 提交信息里**——
     先例 #1756 就是这么做的（squash commit 的 message 末尾是 `Co-authored-by: 2lll5 <...>`，作者列为 2lll5）。
     改 squash message 是 GitHub UI / `gh pr merge --squash --body` 里的一个动作，做不到就别用 squash。
4. `Co-authored-by:` 需要**真实邮箱**：脚本默认用 PR 首个 commit 的 git author（`--author 'Name <email>'`），
   只给 login 时退化为 `<login>@users.noreply.github.com`——不会伪造身份。

---

## 4. 计划里会出现的东西（对照检查）

dry run 的输出按顺序给出（`--json` 是同一份计划的机器可读版本）：fetch 命令与回退、
`git checkout -b adopted/<n> FETCH_HEAD`、`git rebase --signoff <base>`、
`git push origin HEAD:refs/heads/adopted/<n>`、`gh pr create`、`gh pr comment` + `gh pr close`。
计划的每一项都对应 workflow 里真实会跑的步骤，没有"计划外"的写入。

新 PR 标题**永远是原 PR 标题**（不改写、不加前缀）：这样 issue/搜索/release-please 的关联和作者预期都不变。

---

## 5. 被拒绝的情况（exit 2）与失败（exit 1）

脚本把"不该做"和"做失败了"严格分开，**任何拒绝都不产生写入**（`--apply` 阶段中途发现的竞态会明确报出来）。

**拒绝（exit 2，评论里会说明怎么办）**

| 拒绝条件 | 说明 |
|---|---|
| PR 不是来自 fork | head repo 就是本仓 → 提示改用 `/fix-dco` |
| 每个 commit 都已有有效 `Signed-off-by` | 没什么可收养，DCO 本身就该过 |
| 目标分支 `adopted/<n>` 已存在（本地、`origin` 或远端 `ls-remote` 查到） | 可能已有一轮收养在飞：先处理它，或按 §7 放弃 |
| 工作区脏（`git status --porcelain` 非空） | rebase 不能夹带无关改动：先 commit/stash |
| PR 没有 commit | 空分支或已合并 |
| 非 `main` 的 base 分支 | workflow 侧直接拒绝（见 §1） |

**失败（exit 1，评论里给原因；失败路径下不会留下半成品）**

- **冲突**：`git rebase --signoff` 冲突 → `rebase --abort` + 删掉本地 `adopted/<n>` + 恢复原来的分支，
  **不推送**，评论里列出冲突文件。收养**不替作者解冲突**。
- **空提交**：rebase 把变成空的 commit 丢掉时，会打印 `NOTICE` 计数（不静默跳过），
  提醒你 `git log` 看一遍再开 PR。
- **fork 已移动**：fetch 到的 SHA 与计划里的 PR head SHA 不一致 → 中止，重新 `/adopt` 拿新计划。
- **push 被拒**：远端分支在检查之后出现了 → 报错并提示 `git push origin --delete adopted/<n>` 后重试。
- **`origin` 不是本仓**（例如 checkout 的 `origin` 被指到了 fork）→ 直接失败：脚本只往 `origin` 推，
  而 `origin` 必须是被收养 PR 的**目标仓库**。fork 对 `/adopt` 而言永远只读（只用匿名 `git fetch` 读，
  从不 push），这条守护就是防止"把分支推进贡献者的 fork"这类事故。
- **补签核失败**：重放后仍有 commit 没有 `Signed-off-by` → 拒绝推送（宁可不做，也不混进一个假签核）。

---

## 6. 可选：用 PAT 让 `fix-dco.yml` 直接支持 fork（**需要维护者配 secret，本次不代劳**）

`/adopt` 的意义是"**不需要新密钥**"。如果维护者愿意接受一个长期密钥，还有一条更短的路：
给 `fix-dco.yml` 一个对 fork 有写权限的 PAT，让它直接在**作者自己的 fork 分支**上补签核并 push。
代价与前提要说清楚：

- 需要维护者创建 **fine-grained PAT**（对 `Ikalus1988/MisakaNet` 与贡献者 fork 的 `contents: write`；
  fork 属于别人，实际可用性取决于 GitHub 对该 PAT/组织的策略），并在仓库里加 secret，例如 `ADOPT_PAT`；
- workflow 里把 fork handler 从"只打印说明"改成用该 secret checkout `head.repo.clone_url` + force-push；
- 风险：这是**对第三方仓库的写权限**，权限面与审计面都变大；PAT 到期/轮换要有主人；
- 顺带提醒：**本任务不创建 secret、也不改 `fix-dco.yml`**（issue #1778 有明确的范围隔离要求）。
  若要做，请单独开 issue/PR，并先确认 token 的最小权限与撤销路径。

---

## 7. 怎么放弃一次收养

收养的全部痕迹就是**一条同仓分支** `adopted/<n>`（外加新开的 PR 与原 PR 的评论）。放弃步骤：

```bash
# 1) 如果已经开了新 PR：先关掉它（不要合并）
gh pr close <新PR号>

# 2) 删掉收养分支（这就是"放弃"）
git push origin --delete adopted/<n>
```

删掉分支后，原 PR 仍然可以被作者自己补签核并正常合并（fork 从头到尾没被写过，作者的提交也没被改过）。
如果只是想让脚本重新跑一遍，**先删分支**——只要 `adopted/<n>` 还在，`/adopt` 就会按 §5 拒绝，
避免覆盖一轮可能已经审过的收养。想撤销"已关闭的原 PR"这种情况，重新打开原 PR 即可（关闭时用了
`--delete-branch=false`，分支保留）。

---

## 8. 速查

| 事项 | 值 |
|---|---|
| 触发 | PR 评论 `/adopt`（计划）、`/adopt --apply`（执行） |
| 权限门槛 | `MEMBER` / `OWNER` / `COLLABORATOR` |
| 目标分支 | `adopted/<n>`（同仓；永不 `main`、永不 fork） |
| 补的签核 | `Signed-off-by: <跑 --apply 的维护者> <login>@users.noreply.github.com` |
| 作者保留 | 是（重放前后比对作者集合，`authors_preserved`） |
| 退出码 | 0 计划/成功 · 1 运行时失败（冲突、push 被拒） · 2 拒绝前置条件 |
| 测试 | `python3 -m pytest tests/test_adopt_pr.py -q`（离线，含 dry-run 零写入断言与本地 bare origin 上的 apply 全流程） |
