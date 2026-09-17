# 面向人的自动化能力清单（GitHub 侧）— 2026-09-18

> 范围：**替用户/贡献者做事的自动化**（不是纯质量门禁）。所有数字来自 GitHub API 实测或 `file:line`；
> 采集命令原样附在各项里。本文件只读采集，未改动仓库任何内容（除本文件本身）。
> 采集时点：2026-09-18，仓库 HEAD `c88ceafc`，默认分支运行记录窗口 = 该 workflow 全历史。

## 1. 一句话结论

**下表 30 项里，18 项有真实产出证据、7 项存在但查不到任何被使用的证据、4 项在文档里承诺了却根本跑不出东西、1 项（`claim-enforcer`）历史上真跑过但现在空转**；
其中最贵的一条是 `intake-bot-demo.yml`——21,732 次运行、0 条评论，因为复合 action 里未加引号的 `$ARGS` 让
`intake_bot.py` 每次都以 exit 2 失败，而失败落到 `return; // skip unknown decisions` 分支（`.github/actions/misaka-intake-bot/action.yml:145,152,210-212`）；
第二条是 `pr-checks.yml` 的 Auto-Merge Gate 把 REST 的布尔 `mergeable` 与 GraphQL 的枚举串 `"MERGEABLE"` 比较，
恒不相等 ⇒ 永远 `exit 0` 跳过合并——同一个 bug 仓库已在 `scripts/lesson_pr_mergeable.py:102-113` 里修好并写进注释，却漏在了这里。

## 2. 总表

状态栏：**(i)** 有证据的真实使用 · **(ii)** 存在但无任何被使用的证据 · **(iii)** 文档承诺但接不上/跑不到。

| 自动化 | 触发 | 它替谁做了什么 | 真实运行证据（数字） | 已知缺陷 | 证据强度 |
|---|---|---|---|---|---|
| `intake-bot-demo.yml` | `workflow_run`(Cross-Platform Tests completed) + 手动 | 给失败 PR 贴检索命中/报料建议评论 | total=**21732**；我抽的最近 100 个 run **100% skipped**，再往前翻到第 3 页才见 1 个非 skipped（`35248089853`，手动），其日志 `RESULT: {"decision":"error","reason":"script failed"}`；marker 评论全仓 **0 条** | 参数未加引号 → argparse exit 2 → 落 `return` 分支不发评论；`pull_requests` 为空再挡一层 | 强 **(iii)** |
| `intake-auto-review.yml` | `issues[opened,reopened]` + 手动 | 给 intake 打分、写 review 评论、贴标签 | total=**344**（success 86 / skipped 218 / failure 40）；40 次 failure **全部落在 2026-08-25→08-27**，此后 86 次连续 success（至 2026-09-15） | 历史故障期已过；评论无幂等 marker 复查 | 强 **(i)** |
| `issue-intake-triage.yml` | `issues[opened,reopened]` + 手动 | MCP 报料分诊 + 贴 checklist 评论 | total=**1233**（success 436 / failure 24）；#1368、#1619 各有 `<!-- misakanet-intake-triage -->` 评论 | — | 强 **(i)** |
| `intake-salvage-digest.yml` | `schedule 0 8 * * *` + 手动 | 汇总 `auto-rejected` 报料、开/更新 digest issue、30 天自动关闭 | total=**30**：run 1–24 **连续失败**（2026-08-24→09-12），run 25–30 成功；issue #1639 + 5 条日更评论 | 曾连续 20 天静默失败（GH_TOKEN 缺失 + date 未加引号，见 `:13-19,44-47`）；`:128-130` 自动关闭与 SOP 冲突 | 强 **(i)** |
| `intake-pipeline-test.yml` | 手动（唯一） | E2E 冒烟：建 D1 draft + 开 review issue | total=**1**（2026-08-28 手动） | 只跑过一次；依赖 `secrets.CF_API_TOKEN` | 中 **(ii)** |
| `intake-benchmark.yml` | `push`(改 intake 脚本) + 手动 | 离线决策基准，不产出人可见物 | total=**7** | 无用户可见产物（纯 CI） | 中 **(i)** |
| `intake-kind-audit.yml` | `schedule 30 6 * * 1` + 手动 | 每周找"问题被当课程处理"的错分 | total=**3**，3/3 success，但 `label:intake-kind-audit` issue **0 条** | `:36` 用 grep 判"clean"，三次都判 clean ⇒ 建 issue 分支从未走通 | 中 **(ii)** |
| `auto-merge-lessons.yml` | `pull_request[labeled,synchronize,ready_for_review]` + `check_suite` | 打了 `auto-merge-lesson` 的纯课程 PR 自动 squash 合并 | total=**313**；该标签历史上只出现 **1 次**（PR #1796）；bot 于 2026-09-17T09:43:22Z 合并成功（handoff-2026-09-17.md:111-119） | 首次运行被 mergeable 形状 bug 卡住（同文件 :86-100）；仅 1 例、且是维护者自己的 PR | 强 **(i)** |
| `auto-merge-docs.yml` | `pull_request[opened,synchronize,ready_for_review]` | 外部贡献者的纯文档 PR 开 auto-merge | total=**1815**：success 66 / failure 235 / action_required 209 / skipped 1305；抽取 **59 条 success 日志全部 `Docs-only: false`**，0 条 "Auto-merge enabled"、0 条 "Could not enable" | 通道是通的，但**从未有过合格输入**（外部作者 + `good first issue`/`area:docs` + 纯文档）；唯一带该标签的外部 PR #1756 有 2 个 `.mjs` 文件，判定 false 属正确；`ARCHITECTURE.md:75` 写触发是 "PR labeled"，与 `:4-5` 不符 | 强 **(ii)** |
| `pr-checks.yml` → Auto-Merge Gate | 随 `pr-checks` 的 `pull_request` | 全绿 PR 自动合并 | 全仓 **0 条** `Auto-merge #N` 提交主题 | `:720` 读 REST `mergeable`、`:722` 比 `"MERGEABLE"` ⇒ 恒跳过；`:738` 的 `gh pr merge` 不可达 | 强 **(iii)** |
| `adopt-pr.yml` | `issue_comment[created]`，评论以 `/adopt` 开头且作者是 MEMBER/OWNER/COLLABORATOR | 把只缺签核的 fork PR 用同仓分支收养落地 | total=**70**，**70/70 skipped**；`/adopt --apply` 在评论里 0 次真实使用 | 入口条件靠人打 `/adopt`，从未发生 | 强 **(ii)** |
| `fatal-guard.yml` | `push`/`pull_request`(改 `packages/fatal-guard/**`) + 手动 | 包测试（零依赖、崩溃路径） | total=**614** | 纯 CI | 中 **(i)** |
| `fatal-guard-publish.yml` | `push` tag `fatal-guard-v*` | 发 npm 包 | total=**4**，1 次 success（2026-07-25）；npm `@misaka-net/fatal-guard` 近 30 天 **32** 次下载、全期 **935** | 下载量级更像镜像/CI 拉取，非人使用 | 中 **(i)** |
| `auto-draft.yml`（墓碑→draft） | 手动 + `repository_dispatch[crash-tombstone]` | 墓碑 JSON → draft lesson → 自动开 PR | total=**1**（2026-06-22 手动）；`lessons/drafts/` 只有 `README.md`；`crash-reports/` **不存在** | `:72` 传入的 `--create-bounty` 脚本不认 → `EXIT=2`（实测）；`:64` 的 `crash-reports/latest-tombstone.json` 永不存在 | 强 **(iii)** |
| `provenance-gate.yml` | `pull_request`(涉及 provenance/lessons) + `schedule` + 手动 | 校验课程引用来源真实 | total=**16**，failure **5**（含 `[DO NOT MERGE] red-team probe` PR） | 新建（2026-09-16），样本少 | 强 **(i)** |
| `claim-enforcer.yml` | `schedule 0 */6 * * *` + 手动 | 8 小时独占认领窗口到期后放行 | total=**382**，**382/382 success（从未失败）**；"Claim Window Expired" 评论共 **4 条**，最后一次 2026-08-08 | `:36` 判定 `-lt 4` → 实际 **4 小时**，与自己发的"8-hour"文案（`:48`）相矛盾；近 41 天 0 次触发 | 强 **(i→ii)** |
| `pr-shape-guard.yml` | `pull_request_target` | 阻止删文件/改形状的 PR | total=**1515**，failure **78**（5.1%） | — | 强 **(i)** |
| `dco-check.yml` | `pull_request` + 手动 | 校验 `Signed-off-by` | total=**2037**，failure **761**（37%） | 不贴 `needs-dco` 标签（标签在 `pr-shape-guard` 里），与 CONTRIBUTING 描述不符 | 强 **(i)** |
| `fix-dco.yml` | `issue_comment` 含 `/fix-dco` | 自动 rebase --signoff 并强推同一 PR | total=**4427**：success 39 / failure 1 / **skipped 4387（99.1%）**；逐 PR 复核后确认 **3 个 PR** 收到过 "DCO Auto-Fix applied!"（#1608 / #1757 / #1549，共 16 条评论），另有 5 个 fork PR 收到手工说明 | 无幂等：PR #1608 被刷了 **14 条**同文评论；fork 路径只能贴说明 | 强 **(i)** |
| `issue-quality-gate.yml` | `issues[opened,edited]` | 给任务类 issue 贴 `ready`/`needs-ac` | total=**1155**，failure 12；`needs-ac` 77 条、`ready` 21 条 | — | 强 **(i)** |
| `newbie-welcome.yml` | `issue_comment[created]` | 非成员在 good-first-issue 下评论时欢迎 | total=**4825**：success 259 / failure 38 / skipped 4527（+1 条无 conclusion）；最新真实欢迎 2026-09-15T05:51:32Z（issue #1651），按 1100 字符正文在评论里逐条核对 | 无去重：#1651 上同一模板贴了 4 次；对已有贡献记录的 `zsxh1990`(CONTRIBUTOR) 也欢迎 | 强 **(i)** |
| `pr-welcome.yml` | `pull_request_target[opened,reopened]` | 首次贡献者欢迎 + DCO 提示 | total=**1035**：success 358；"Thanks for your first PR!" 评论 214 条 | — | 强 **(i)** |
| `stale.yml` | `schedule 0 6 * * *` + 手动 | 14/30 天未活动则标 stale、再关闭 | total=**97**（97/97 success）；`label:stale` 全仓 **1 条**；"automatically closed due to" 评论 **0 条** | 阈值 + `exempt-issue-labels`/milestone 豁免使它在活跃仓库里等于空转 | 强 **(ii)** |
| `star-request.yml` | `pull_request[opened]` + `pull_request_review[submitted]` | 给 PR / 已批准 review 贴求 star 评论 | total=**859**：success 780 / failure 41；"⭐ Star" 评论 **118** 条 | review 分支的 `context.eventName` 写法曾致文案错（已在 `:25-32` 注明修复） | 强 **(i)** |
| `leaderboard-watch.yml` | `push` | Leaderboard 快照变化时提交并推送 | total=**1474**（success 1175 / failure 292）；`data/leaderboard.json` 最近提交 2026-09-17 | 20% failure 无解释 | 强 **(i)** |
| `update-badges.yml` | `workflow_run`(148)/`push`(82)/`schedule 23 3 * * 1`/手动 | 重算课程/工具/节点数推 `data` 分支 | total=**239**；`data` 分支最近提交 `badges: auto-update...` 2026-09-17T17:11:36Z | 数字源自被描述文件自身（`TOOL_COUNT` 直接 grep 源文件），无外部校验 | 强 **(i)** |
| `lesson-notify.yml` | `issues[opened,labeled]`（含 `new-lesson`） | 飞书推送新课程贡献 | total=**2953**：**skipped 2946**、success 2、failure 5；最后一次触发 2026-09-08；`label:new-lesson` 仅 6 条 | 命中率 0.24%；投递成功与否不可见 | 中 **(ii)** |
| `d1-counters-report.yml` | 手动（唯一） | 打印 D1 计数并对账 KV 遗留键 | total=**2**（2026-09-13） | 产物只在 run 日志里，无归档 | 中 **(ii)** |
| `register.yml` | `issues[opened,reopened]` + 手动 | 分配 node_id、贴入门测试、注册完成关 issue | total=**656**；`label:registration` 63 条、`label:registered` 11 条 | 完成率 11/63 需人工确认口径 | 中 **(i)** |
| `automation_output_audit.py`（`guarded-repository.yml` 内，新） | `schedule 0 7 * * 1`（`guarded-repository.yml:30-31`） | 把"运行次数 vs 产物"对账，跑不出产物就 fail | 该 job 加于 2026-09-17（#1811）；`guarded-repository.yml` 最近一次非 push 运行是 **2026-09-14** 的 schedule，jobs 里**只有** `guarded-repository / scan` ⇒ **这个 job 一次都还没跑过** | 下次窗口 2026-09-21；目前所有结论都还无人复核 | 强 **(iii)** |

## 3. 逐项细节（只记关键项）

### 3.1 intake-bot 通道：21,732 次运行，0 条评论

- 触发：`.github/workflows/intake-bot-demo.yml:19-25` 只认 `workflows: ["Cross-Platform Tests"]`；`:29` 的 job `if` 要求 `workflow_run.conclusion == 'failure'` 或手动。
- 实测（全历史）：`total_count=21732`；最近 300 个 run 里只有 1 个非 skipped。该 run 日志结尾：
  `RESULT: {"decision":"error","reason":"script failed"}`。
- 根因（可复核）：`.github/actions/misaka-intake-bot/action.yml:145` `ARGS="$ARGS --error $INPUT_ERROR"` 与
  `:152` `RESULT=$(python3 $SCRIPT $ARGS 2>/dev/null || echo '{"decision":"error",...}')` 都未加引号；
  实测 `python3 scripts/intake_bot.py --json --source github-action --sim 0.45 --error ModuleNotFoundError: No module named requests`
  → `intake_bot.py: error: unrecognized arguments: No module named requests`，exit 2。
- 失败后落到 `action.yml:210-212` 的 `return; // skip unknown decisions`，因此评论步骤从不执行；
  即使走到，`:215-219` 还要求 `context.payload.workflow_run.pull_requests` 非空（实测该字段为空数组）。
- 反例（证明它确实"能"发评论）：同仓 `ci-lesson-search.yml` 走的是 `--log /tmp/ci_error.log`（无空格）绕开了这个 bug。
- 文档承诺：`scripts/automation_output_audit.py:96-99` 明确把它的产物定义为 `in:comments "MisakaNet: Lesson Found"`，
  该搜索在全仓命中 0 条精确评论。

### 3.2 auto-merge 三条通道

- `auto-merge-lessons.yml`：`:70` `OPT_IN_LABEL: auto-merge-lesson`；`scripts/lesson_pr_mergeable.py:217-220`
  要求标签存在否则 wait。实测 `label:auto-merge-lesson` 全仓 **1 条**（PR #1796，作者 Ikalus1988），
  `merged_by=github-actions[bot]`，时间 2026-09-17T09:43:22Z。首次运行（run `35204235065`）判定 merge 但复核拒绝，
  日志与根因见 `docs/maintainer/handoff-2026-09-17.md:86-100`，成功记录见同文件 `:111-119`。
- `auto-merge-docs.yml`：`:4-5` 只有 `[opened, synchronize, ready_for_review]`（**文档 `ARCHITECTURE.md:75` 写的是 "PR labeled"**）。
  `:18-25` 要求作者非 Ikalus1988/zsxh1990 且带 `good first issue`/`area:docs`；`:40-48` 的 docs-only 判定用白名单。
  实测：total=1815，仅 66 次走进 job；把 59 条 success 的日志全部下载 grep，`Docs-only: (true|false)` 一律为 **false**，
  0 条 `Auto-merge enabled for PR`、0 条 `Could not enable auto-merge` ⇒ "Enable auto-merge" 步骤从未执行。
  外部作者合并过的 PR 只有 2 个（#1646 canburakyol、#1756 2lll5），两者 `merged_by` 都是 **Ikalus1988**。
- `pr-checks.yml` Auto-Merge Gate：`:720` `MERGEABLE=$(gh api repos/Ikalus1988/MisakaNet/pulls/$PR_NUM --jq '.mergeable')`
  + `:722` `[ "$MERGEABLE" != "MERGEABLE" ] && { ... exit 0; }`。实测 REST 返回 `true`/`false`/`null`：
  `PR 1801 -> True unstable`、`PR 1656 -> None unknown`，**永不等于字符串 `MERGEABLE`** ⇒ `:738` 的 `gh pr merge` 不可达。
  全仓提交主题搜索 `"Auto-merge #"` 只命中描述该功能的提交，**0 条**由该 gate 产生的合并提交。
  同一个 bug 仓库已记录在 `scripts/lesson_pr_mergeable.py:102-113`（"reading the wrong shape silently disables the whole channel"），
  并在 `docs/maintainer/auto-merge-lessons.md:49` 写明 REST 是布尔——**修了一条，漏了这一条**。
- `adopt-pr.yml`：`:32-35` 的 `if` 要求 PR 评论 + 以 `/adopt` 开头 + 作者是 MEMBER/OWNER/COLLABORATOR。
  实测 total=**70，70/70 skipped**；`"/adopt --apply"` 的评论搜索只命中介绍该流程的两个 PR（#1786/#1789），无真实使用。

### 3.3 fatal-guard 与墓碑链

- 包已发布可用：npm 下载 `@misaka-net/fatal-guard` 近 30 天 **32**、全期 **935**（`api.npmjs.org`）。
- 但"崩溃 → 墓碑 → draft → 课程"这条链在仓库里**接不上**：
  - `auto-draft.yml:72` `python3 scripts/tombstone_to_draft.py --from-file /tmp/tombstone.json --create-bounty`，
    而脚本只认 `--from-file/--stdin/--dry-run/--create-issue/--ai-hint`（`scripts/tombstone_to_draft.py:341-347`）。
    实测：`tombstone_to_draft.py: error: unrecognized arguments: --create-bounty`，`EXIT=2`。
  - `auto-draft.yml:64` 回退读 `crash-reports/latest-tombstone.json`；实测 `ls crash-reports` → `No such file or directory`。
  - 实跑 total=**1**（2026-06-22 手动）；`lessons/drafts/` 只有 `README.md`，无任何 draft 产出。
  - `AGENTS.md:15-18`、`docs/zero-day-drill.md:53`、`SKILL.md:175` 都把这条链写成已闭环，与上述代码矛盾。

### 3.4 贡献者门禁

- 真跑过并拦住东西的：`pr-shape-guard`（1515 run / 78 failure）、`dco-check`（2037 / 761 failure）、
  `provenance-gate`（16 / 5 failure）、`fix-dco`（39 次修复成功，最近 2026-09-16）。
- `claim-enforcer`：`:36` `[ "$ELAPSED" -lt 4 ] && continue` 与 `:46-50` 自己发的 "The 8-hour exclusive /claim window" 文案
  相差一倍；实测 382 run **全部 success**（脚本内 `gh api ... > /dev/null 2>&1` 与管道 `while read` 吞掉了错误），
  4 条到期评论分别落在 2026-06-23 / 08-04 / 08-05 / 08-08，此后 41 天无产出。
- `stale.yml`：97 次每日运行，全仓 `label:stale` 仅 1 条、`"automatically closed due to"` 评论 0 条 ⇒ 触发条件在活跃仓库中几乎不成立。
- `issue-quality-gate` 的 intake 豁免（`:44-58`）是 2026-09-13 才补的，此前会给报料类 issue 打 `needs-ac`；当前 77 条 `needs-ac` 多为历史。

### 3.5 定时产出（人可见）

- 真的在更新的：`leaderboard-watch`（`data/leaderboard.json` 2026-09-17）、`update-badges`（`data` 分支 2026-09-17T17:11:36Z）、
  `intake-salvage-digest`（#1639 每日一条，2026-09-13→09-17 连续 5 条）。
- 不是自动的：`STATUS.md` 的 "自动更新于 …" 由 `scripts/update_status.py` 生成，但全仓没有任何 workflow 调它（实测 `grep -rn update_status .github/ Makefile` → exit 1）。
- 计数类文案已漂移：README `:485`/`:504` 写 "68 workflows"，而实测 `ls .github/workflows/*.yml | wc -l` = **69**，`ARCHITECTURE.md:54` 也写 69——该数字不在 `sync_lesson_count.py` 的 SSOT 注册表里，没有门禁会拦住它（README 的两处在同一次改动里已改成 69）。
- 自我校验缺口：唯一做"运行次数 vs 产物"对账的 `automation_output_audit.py`（`guarded-repository.yml:60-73`）
  自 2026-09-17 加入后**尚未跑过一次**（最近一次 schedule 是 2026-09-14，其 jobs 只有 scan）。

### 3.6 报料回执与转化口径

- `docs/maintainer/intake-triage.md:5,27-29` 的铁律是"每条报料都有确定的归宿与回执"。
- 实测 105 条 `label:intake` issue 逐条拉评论统计：拿到 `感谢报料`/`delivered`/`ANSWER` 回执的 **30 条（29%）**；
  2026-09-01 前 13/68（19%），之后 17/37（46%）；83 closed 中 70 条无回执；仅 4 条是"只有 bot 评论"（3 closed / 1 open）。
- 转化率目前不可观测：`python3 scripts/intake_outcome_tracker.py --summary` 实测
  `"total_reviewed": 0, "conversion_rate": 0.0, "conversion_rate_is_observable": false`；
  `grep -rn intake_outcome_tracker .github/` → exit 1（没有任何 workflow 跑它），`data/intake_outcomes.json` 不存在。
- intake 人口本身：105 条 issue 的创建者 = Ikalus1988 102 / zsxh1990 2 / github-actions[bot] 1；
  但 `**Source:**` 字段显示来源含 `remote-agent` 21、`dsh` 13、`mcp` 10、`antigravity` 6、`claude-code` 5 及外部仓库名（如 `s6pa1rta3n-lab/roof4u`）——
  即"MCP 报料"确实有量，但它走维护者 token 建 issue，**提交者身份不可验证**（与 `AGENTS.md` §3.3 自述边界一致）。
- Kind 分布（105 条）：`missing_lesson` 73、`new_lesson_candidate` 14、`question` 9、`lesson` 4、无字段 5。

## 4. 「看起来在工作但其实没在工作」

1. **`intake-bot-demo.yml`** — 见 3.1。反例：手动 dispatch 路径存在，且姊妹文件 `ci-lesson-search.yml` 的同类调用用 `--log` 绕开了空格 bug，
   说明链条本身可通，坏的是传参方式。
2. **`pr-checks.yml` Auto-Merge Gate** — 见 3.2。反例：`auto-merge-lessons.yml` 用 `mergeable_is_clean()`
   同时接受 `True` 与 `"MERGEABLE"` 后成功合并过 #1796——同一 bug 类在此处有可工作的实现。
3. **`auto-merge-docs.yml`** — 1815 次运行、66 次进 job、59 份日志全部 `Docs-only: false`，0 次启用 auto-merge。
   反例：`auto-merge-lessons.yml` 的机器合并确实发生过一次，说明机器合并通道整体不是死的；
   此处的问题不是脚本坏了，而是**从未有合格输入**（外部作者 + 该标签 + 纯文档三者同时成立）。
4. **`stale.yml`** — 97 次每日运行、0 次关闭、1 条 stale 标签。反例：仓库 issue 活跃度极高（105 条 intake 均有评论），
   阈值失效是"分母太活跃"而非"脚本坏了"。
5. **`adopt-pr.yml`** — 70/70 skipped，零次 `/adopt`。反例：`fix-dco.yml` 的 fork 分支在同一场景下确实贴出了 5 次手工说明，
   说明"fork 走不通"这个前提是真的、只是没人用新通道。
6. **`intake-kind-audit.yml`** — 3 次全 clean，建 issue 分支从未走通。反例：`issue-quality-gate.yml` 的同类
   `needs-ac`/`ready` 写入（77+21 条）证明这些 bot 写标签的能力是通的。
7. **`auto-draft.yml` 墓碑链** — 参数名对不上 + `crash-reports/` 不存在，1 次手动运行、0 产出。
   反例：`scripts/tombstone_to_draft.py --from-file <file>`（不带 `--create-bounty`）在本地是可用的，脚本本身没坏。
8. **`automation_output_audit.py`（仓库自建的对账器）** — 还没跑过第一次。这是"自报指标没有外部校验"的上游原因本身。

**能证明"确实在工作"的反例清单（以防把整体误判为摆设）**：`dco-check` 761 次 failure、`pr-shape-guard` 78 次 failure、
`provenance-gate` 抓到红队 probe、`fix-dco` 3 个 PR 的真实签核修复（#1608 共 14 条 / #1757 于 2026-09-16 / #1549）、`newbie-welcome` 最新 2026-09-15 真实欢迎、
`pr-welcome` 214 条首次 PR 欢迎、`star-request` 118 条、`issue-intake-triage` 436 次成功分诊、
`intake-auto-review` 86 次成功评审、`update-badges`/`leaderboard-watch` 当日仍有推送、`fatal-guard` 在 npm 上有 0.3.0 且近月 32 次下载。

## 5. 我无法验证的部分

1. **`lesson-notify.yml` 的飞书投递**：2953 次运行里只有 7 次非 skipped（2 success），但投递成功与否只在飞书侧，
   仓库内不可见；也无法确认 `FEISHU_WEBHOOK_URL` 是否仍配置。查法：只看 run 结论与 `label:new-lesson`(6 条)，未取 webhook。
2. **npm 32 次/月下载的性质**：无法区分真人安装与镜像/CI 拉取；未查 npm 的 referrer 或 GitHub dependents。
3. **"谁提交了 intake"**：105 条 issue 全部由维护者账号或 bot 创建，`**Source:**` 是自声明字段
   （与 `AGENTS.md` §3.3 的口径一致）；要归因只能走 PR + DCO，本次未做。
4. **`auto-merge-docs` 未采样的 7 条 success 日志**：59/66 已读，剩 7 条归档下载未成功；结论建立在 89% 覆盖上。
5. **`repository_dispatch[crash-tombstone]` 是否有仓外发送方**：仓内 `grep -rn "crash-tombstone"` 只命中 `auto-draft.yml` 自己；
   若有外部发送方（例如某个 node 的本地脚本），本次无法证实也无法证伪。
6. **`guarded-repository.yml` 里 HOL Guard 扫描的结论**：只看 run 结论（235 次全 success），未读 SARIF 内容与 attestation。
7. **`claim-enforcer` 在 2026-06-12 之前的运行**：workflow 全历史 382 次已全取，但 4 条到期评论所对应的 issue 已在
   `/claim` 语义变化前；无法回推当时标签集合。
8. **"无证据"的强度声明**：对 `adopt-pr`、`stale`、`lesson-notify`、`intake-pipeline-test`、`d1-counters-report`
   这五项，我查的是 (a) workflow 全历史每个 run 的 conclusion，(b) 该 bot 会写的评论/标签/分支的全仓搜索结果。
   若某项的产物落在仓外（飞书、D1、npm），我只能说"仓内无痕迹"，不能说"没人用"。

## 6. 建议的下一步（按证据缺口排序，最多 5 条）

1. **先跑一次 `automation_output_audit.py`（`gh workflow run guarded-repository.yml`）**，
   让仓库自己的运行数/产物对账器产生第一份外部可看的记录——现在它是对账链条上唯一没跑过的环节。
2. **补 `pr-checks.yml:720-722` 的形状归一化**：直接复用 `scripts/lesson_pr_mergeable.py:102-120` 的 `mergeable_is_clean()`，
   并加一条断言"shell 不得拿原始拼写比较"（该断言已存在于 lessons 通道的测试里）。在本清单 30 项里，这是唯一一处**已被同仓证伪却仍生效**的门。
3. **修 `intake-bot-demo` 的传参**（`action.yml:145,152` 加引号或改走 `--log` 文件），
   然后**手工 dispatch 一次**确认评论真的落到 PR 上——否则 21,732 次运行的"0 产物"会继续被当成"没触发"。
4. **修 `auto-draft.yml:72` 的 `--create-bounty`**（改成 `--create-issue` 或补上该 flag），
   并把 `crash-reports/` 这个不存在的路径从 `:64` 与头注释里删掉——现在文档（`AGENTS.md:15-18`）承诺的闭环是死的。
5. **把 `intake-salvage-digest` 的 20 天静默失败做成可发现的**：给这类定时 digest 加"连续 N 天失败就开一条 issue"，
   或者至少让 `automation_output_audit` 把"30 天窗口内 failure 占比 > 50%"也纳入判定；当前它只查"跑了但没产物"。
