# 仓库现状（state of the repo）：一个**不在 gitignore 里**的交接面

> **这份文件为什么存在**：`docs/maintainer/handoff-*.md` 是逐轮交接与待办快照，但**最近几篇只存在
> owner 的机器上**（见 §1.4），所以"第二个人"接手时读不到当前在飞的东西、待决策项、门禁的信任边界。
> 这份文件把**可以公开**的那部分固定下来，敏感的部分（凭据线索、主机路径）继续留在本地 handoff 里。
> 背景：issue #2044；同类产物：`docs/maintainer/credentials-and-environments.md`（凭据放在哪个 environment）。

- **快照时间**：2026-09-22T14:54Z（下列所有 API 读取都在这一刻）
- **快照对象**：`main` @ `eb6519aa4acfacb0834b1a2bde072a6476b06889`
- **可公开性**：本文件不含任何凭据值、不含任何本机路径或主机名、不含只存在于 owner 机器上的文件内容。
  §6 里的 `<your own credential>` 是占位符——**不要**把真值写进这份文件。
- **怎么用**：只看 §4（现在需要谁拍板）和 §2.4（哪些门禁可以信）就能接手一次值班。
- **更新触发**在 §5；**所有数字的复现命令**在 §6，数字与命令不一致时**先信命令**。

## TL;DR (English)

- 69 workflows on `main`; 18 run on a schedule, 8 sit behind the `release` environment whose **only
  required reviewer is the owner**, and 6 run on the owner's PAT (repo-level secret `SHELDON_PAT`).
  The concrete failure mode: a publish run can wait for a human for a day with **nothing notifying
  anyone** (measured: one run waiting since 2026-09-21T12:13:42Z).
- `main` requires **three** status checks (`DCO / Signed-off-by`, `test (ubuntu-latest, 3.11)`, `gate`)
  with **no bypass actors** — and GitHub enforces that rule on *direct pushes* as well as merges, so
  every workflow that commits back to `main` is now refused (#2073). The `audit` gate that actually runs
  the full suite is still **not** required — it is only repaired every two hours by `pr-audit-watch.yml`.
- Backlog: **72 open issues / 14 open PRs**; **1** of those open issues had its work already merged on
  `main` (`scripts/done_but_open.py`) — "done but never said". That number read **4** until 2026-09-23,
  when three of the four turned out to be the detector matching digits inside other people's URLs.
- Bus factor is one: 2 collaborators, **1 admin**, 1 environment reviewer, 75 of the 100 most recently
  merged PRs authored by the owner.
- This document is a snapshot. Re-measure with §6, do not trust a stale number.

---

## 1. 什么在自动跑，什么在等人

### 1.1 不需要人就会发生的（推 main / 定时 / 事件触发）

`main` 上共 **69 个 workflow 文件**（`main` @ 上述 SHA）。**18 个**带 `schedule`：

| workflow | cron (UTC) | 干什么 |
|---|---|---|
| `update-lessons.yml` | `0 0 * * *` | 每日刷新课程索引与计数 |
| `sync-d1.yml` | `0 3 * * *` | 语料同步到 D1（`automation` 环境） |
| `build-feed.yml` | `23 */3 * * *` | 每 3 小时重建 feed |
| `nightly-mirror-consistency.yml` | `17 3 * * *` | 镜像一致性 |
| `stale.yml` | `0 6 * * *` | 过期 issue/PR 处理 |
| `update-smithery-badge.yml` | `0 6 * * *` | 徽章刷新 |
| `sync-question-answers.yml` | `20 7 * * *` | 问答回填（`automation` 环境） |
| `intake-salvage-digest.yml` | `0 8 * * *` | 每日 intake 打捞摘要 |
| `sync-node-counter.yml` | `41 4 * * *` | 节点计数 |
| `claim-enforcer.yml` | `0 */6 * * *` | 悬赏认领到期 |
| `pr-audit-watch.yml` | `17 */2 * * *` | **补跑没跑过的 audit**（见 §2.4） |
| `benchmark-workers-ai.yml` | `0 2 * * 1` | 每周基准 |
| `update-badges.yml` | `23 3 * * 1` | 每周徽章/计数 |
| `intake-kind-audit.yml` | `30 6 * * 1` | 每周 intake 分类审计 |
| `provenance-gate.yml` | `17 6 * * 1` | 每周来源链接腐烂检查（只报告） |
| `guarded-repository.yml` | `0 7 * * 1` | 每周第三方扫描 + **产出核对**（见 §2.3 末） |
| `codeql.yml` | `0 6 * * 0` | 每周 CodeQL |
| `arch-review.yml` | `0 2 1 * *` | 每月架构评审 |

除定时之外，**推 main 就会自己动**的主要有：`deploy-worker.yml`（改 `workers/register-proxy-sw.js`
时，见 §1.2 的审批）、Cloudflare Workers Builds（git 集成，任何 push 都会跑，在 commit 上留下
`Workers Builds: misakanet-web` 这个 check）、`release-please.yml`（开 release PR / 打 tag）、
`auto-sync-prs.yml`（把 main 合并进同仓 PR 分支）、`docs.yml`（GitHub Pages）、`codeql.yml`、
`guarded-repository.yml`、`sync-d1.yml`、`update-badges.yml`。

PR / issue 事件上自己动的：`auto-merge-docs.yml`（`pull_request_target` + 标签驱动的合并）、
`auto-merge-lessons.yml`（`pull_request` + 标签，判定逻辑在 `scripts/lesson_pr_mergeable.py`）、
`pr-audit-watch.yml`、`intake-auto-review.yml`、`issue-intake-triage.yml`、`claim-enforcer.yml`、
`newbie-welcome.yml`、`pr-shape-guard.yml` 等。

按量级感受一下：**最近 8 天（`created>=2026-09-15`）有 33,094 次 workflow run**，约 4,100 次/天。

### 1.2 必须等人的：`release` 环境（审批人只有 owner）

仓库有 5 个 environment（`release` / `automation` / `pypi` / `github-pages` / `copilot`），其中
**只有 `release` 配了 required reviewer**，名单里只有 `Ikalus1988`。挂在它后面的 workflow 有 **8 个**：

`apply-d1-schema.yml` · `d1-bootstrap.yml` · `d1-counters-report.yml` · `deploy-worker.yml` ·
`fatal-guard-publish.yml` · `intake-pipeline-test.yml` · `misakanet-publish.yml` · `misakanet-setup-publish.yml`

`automation` 环境**故意没有审批人**（`sync-d1` / `sync-question-answers` 是 cron；在 cron 上挂审批
不是安全特性，是停摆）。它的安全来自另一头：里面的凭据只能做一件事（D1:Edit）。理由与全表见
`docs/maintainer/credentials-and-environments.md`。

**实测此刻有 1 个 run 卡在等审批**：`Publish misakanet`（分支 `main`，2026-09-21T12:13:42Z 创建）。

### 1.3 走 owner PAT 的那条链

**6 个 workflow** 读仓库级 secret `SHELDON_PAT`：`auto-merge-docs.yml` · `auto-sync-prs.yml` ·
`misakanet-publish.yml` · `pr-checks.yml` · `pr-shape-guard.yml` · `release-please.yml`。
（名字是公开的——它写在公开的 workflow 文件里，也在 `credentials-and-environments.md` 的表里；
值不在仓库里。）此外 **5 个 workflow** 用 `pull_request_target`：`auto-merge-docs.yml` ·
`pr-merged-thank.yml` · `pr-shape-guard.yml` · `pr-thank-you.yml` · `pr-welcome.yml`。

### 1.4 这造成的失效模式（点名，不是泛泛而谈）

1. **审批队列没有通知**。`release` 上的必需审批人只有一个人，而 GitHub 不会因为"有人在等审批"
   去敲任何人。上面那个 run 已经等了 24 小时以上。它的后果不是"慢"，是**发布与部署停在一个人的
   收件箱里**，而 issue 计数、CI 全绿都看不出来。
2. **队列会堆叠，而堆叠会产生"批错一个"的风险**。`deploy-worker.yml` 的注释记录了 2026-09-21 的实测：
   四个 run 排队等审批，最老的 22 小时，而线上 `serverInfo.version` 是 2.31.0、`main` 是 2.33.0——
   批错一个就会把 22 小时前的 worker 发上线。现在用 `cancel-in-progress` 缓解（部署是幂等的）。
   同一段注释明确说：npm/PyPI 的 publish **不能**这么干（两个等待中的 run 是两个不同版本，
   两个都得跑），它们需要一个"只取消已发布版本"的 reaper——**这个 reaper 目前不存在**。
3. **PAT 缺失时是静默降级**。`auto-sync-prs.yml` 在 `SHELDON_PAT` 为空时打一条 `::warning::` 然后
   **跳过**同步（它解释得对：用 `GITHUB_TOKEN` 推分支不会触发 CI，比不同步更糟）。但 warning 不是失败，
   所以"同步链停了"可以持续很久而没有任何红灯。
4. **bus factor 是 1，而且可以量化**：仓库有 **2 个 collaborator，1 个 admin**；环境审批人只有 1 个；
   最近 100 个 merged PR 里 **75 个**是 owner 提交的（窗口 2026-09-19 → 09-22）。
5. **交接文件本身也只有一个人有**：`docs/maintainer/handoff-*.md` 共 19 篇，其中 **16 篇在仓库里**
   （到 2026-09-16），**最近三篇（09-17 / 09-18 / 09-19）只被 owner 机器上的 `.git/info/exclude` 排除**，
   新 clone 里根本没有这三个文件——而"需用户拍板"清单恰好只写在最新那一篇里（§4 的来源）。
   这**不是** `.gitignore` 的规则：仓库里的 `.gitignore` 只排除 `docs/prd/HANDOFF.md`。

---

## 2. 门禁在哪里，哪些值得信任

### 2.1 `main` 上现在有**三条**必需检查（2026-09-23 读取；`gate` 于 09-22 加入）

```
$ curl -sS -H "Authorization: Bearer $GITHUB_TOKEN" \
    https://api.github.com/repos/Ikalus1988/MisakaNet/rules/branches/main
[
  {
    "type": "required_status_checks",
    "parameters": {
      "strict_required_status_checks_policy": false,
      "do_not_enforce_on_create": false,
      "required_status_checks": [
        { "context": "DCO / Signed-off-by" },
        { "context": "test (ubuntu-latest, 3.11)" },
        { "context": "gate" }
      ]
    },
    "ruleset_source_type": "Repository",
    "ruleset_source": "Ikalus1988/MisakaNet",
    "ruleset_id": 23826057
  }
]
```

- 这条规则来自仓库 ruleset **`23826057`「main: the deterministic gates」**（`active`，作用域
  `~DEFAULT_BRANCH`，只有 `required_status_checks` 这一条规则；`bypass_actors: []`）。
- 三个 context 的来源可以核对：`DCO / Signed-off-by` 由 `dco-check.yml` 用 checks API 上报；
  `test (ubuntu-latest, 3.11)` 是 `ci-cross-platform.yml` 里的 `test` job（那个矩阵是
  3 OS × 3 Python 减 1 个排除项 = **8 条腿**，而必需的只有其中 1 条）；`gate` 由 lesson-gate/审计链上报。
- ⚠️ **`bypass_actors: []` 的副作用（2026-09-23 实测，#2073）**：GitHub 对 `required_status_checks`
  规则**在直接 push 时也强制**，所以任何"跑完把结果提交回 main"的 workflow 都会被拒：
  `remote: - 3 of 3 required status checks are expected.` → `push declined due to repository rule violations`。
  第一次撞上是 npm 发布 2.34.0 的 record 步骤（包发成功、记账被拒，留下三行过期版本号）；每日的
  `sync-node-counter` / `update-lessons` / `update-badges` 是下一批。**"run 是绿的"不再等于"它写进去了"**——
  判据要看受管表面最后一次真实提交的时间。
- 分支保护的其余读法（同一个仓库、同一时刻）：`enforce_admins: true`；响应里**没有**
  `required_pull_request_reviews`（不强制 review）；`allow_force_pushes.enabled: true`——也就是说
  API 当前并不阻止一次强推 `main`。

### 2.2 PR 上会跑、但**不是**必需检查的门禁

| 门禁 | 工作流 | 跑什么 |
|---|---|---|
| `audit` | `pr-checks.yml`（"Misaka Network Agent Auditor"） | **全量测试 + DCO 审计 + secret 扫描 + lesson schema + verdict** |
| `audit-shape` | `pr-shape-guard.yml` | 把 diff/markdown 粘进源码、改动越出标题范围 |
| `lesson-gate` | `lesson-gate.yml` | frontmatter 必填字段、标题重复、domain 白名单 |
| `lesson-security` | `lesson-security.yml` | lesson 里的危险命令、注入扫描 |
| `unit` / `e2e` | `misakanet-setup-ci.yml` | 安装器单测 + 打包产物 e2e（`--inject` 必须让它变红） |
| `CodeQL` | `codeql.yml` | 安全查询 |
| `pr-agent` / `pr-genius` | `pr-agent-review.yml` / `pr-genius-check.yml` | **明确非阻断**，只做评审参考 |

**没有任何一条是必需的。** 门禁的完整清单与失败示例在 `docs/agents/repo-operations.md` §2。

### 2.3 "绿了但什么都没验证"的历史（都是可核对的记录）

- **2026-09-17**，`scripts/automation_output_audit.py` 的文档字符串记录了三条同形状的失败——
  *看起来健康、实际零产出*：`pr-genius-check.yml` **1,459 runs / 0 条评论**（权限是
  `pull-requests: read`，每次 403 被吞进 stderr，check 却一直绿着）；`intake-bot-demo.yml`
  **21,126 runs、98.1% skipped**；`arch-review.yml` 排了月跑却**一次都没跑**（`total_count = 0`）。
  根因是同一句话：**没有任何检查去看"运行数 / 产出"的比值**。
- **2026-09-20（#1920）**：PR #1918 打开时，`pull_request` 事件的工作流**一个都没跑**——真正干活的
  auditor 不在列表里；#1916 / #1917 同样如此。而当时 `main` **没有任何必需检查**，所以"门禁没跑"
  与"门禁全绿"呈现给维护者的是同一样东西（一串绿 check，只是少了几个）。
- **#1822（仍 open）**：三处不会失败的门禁——工具数门禁的期望值是从**被测文件自身**数出来的
  （数学上不可能失败）；`doctor.py` 的远端可达性检查在 CI 里根本走不到（`--kv-only` 提前 return）；
  `/api/health` 顶层 `ok` 掩盖了 `kv_writes` **5/5 全失败**。
- **#1999 / #2002（open PR）**：#1999 报告 23 条恒真测试；#2002 报告三处门禁**只能在真机上失败**。
- **`auto-merge-docs.yml` 自己的注释**：这个通道"自写出来就没产出过"——触发事件选错了
  （`labeled` 才是 load-bearing 的那个），两个合法的外部 docs PR（#1842、#1801）因此一直挂着。
- **`update-smithery-badge.yml` 的注释**：之前的 `git checkout data` **静默什么都没做**。

### 2.4 所以现在哪些门禁可以信（诚实结论）

- **可以信的**：`DCO / Signed-off-by` 与 `test (ubuntu-latest, 3.11)`——它们是必需检查，所以
  "没跑"会变成**永久 pending**（无法合并），不会再伪装成绿色。#1920 的**一半**因此关掉了。
- **还不能信的**：`audit`（跑全量测试 + DCO + secret 扫描的那个）**仍然不是必需检查**。它现在靠
  `pr-audit-watch.yml` 每 2 小时扫一遍"head commit 上没有 `audit` check-run"的 PR 并补跑——
  那是**修复**，不是门禁。`pr-audit-watch.yml` 的注释自己写着：把 `audit` 设为 required 是
  "the complementary half"。所以"这个 PR 到底跑过测试没有"这件事，**在界面上仍然可以被骗过去**。
- **矩阵同理**：8 条腿里只有 ubuntu/3.11 是必需的，另外 7 条（含 3 条 Windows）失败不阻塞合并。
- **唯一"看比值"的机制**是 `guarded-repository.yml` 里的 `automation-output-audit`（每周一）：
  当一个 automation 在窗口内跑 ≥20 次而零产出、或一个 scheduled workflow 超过 45 天一次没跑过，
  它会让那次运行失败。这是本仓唯一会"因为自动化空转而变红"的东西。
- **注入扫描只盖 `lessons/`**：CI 里唯一一次调用是 `lesson-security.yml` 的
  `injection_scan.py --dir lessons`。`docs/` **不在扫描范围**，而按扫描器自己的判据，当前 `docs/`
  有 **4 处 high**（2 处 `hidden_html_comment`、2 处 `invisible_characters`，全部在本次之前就存在于
  `main` 的文件里：`docs/archive/AGENT_GUIDE.md`、`docs/connect.html`、`docs/index.html`、
  `docs/maintainer/handoff-2026-08-02.md`）。没有门禁会因此变红——这正是 §2.3 那个模式的又一例。

---

## 3. 积压的形状（数字 + 口径）

| 指标 | 值 | 口径 |
|---|---|---|
| open issues | **72** | `search/issues?q=...is:open+is:issue` |
| open PRs | **14** | `...is:open+is:pr` |
| closed issues | 669 | `...is:closed+is:issue` |
| merged PRs（累计） | 707 | `...is:pr+is:merged` |
| 远端分支 | **304** | `branches?per_page=1` 的 `link` 头最后一页 |
| 近 8 天 workflow runs | 33,094 | `actions/runs?created=>=2026-09-15` |

### 3.1 诚实拆分

- **72 个 open issue 里 65 个是 owner 自己开的**；外部贡献者 6 个，另有 1 个来自 bot。
  按标题前缀：19 个 `[Intake]`、2 个 `[Question]`、4 个 `[Lesson]`、4 个 `[Compat]`、4 个 `[Bounty]`、
  7 个零散前缀（`[Docs]`/`[CI]`/`[Review]`/`[Zero-Bounty]`/`[Onboarding]`/`[Glama]`/`[bounty]`），
  其余 32 个是无前缀的自由标题。
- 标签分布（前几）：`ready` 39 · `needs-ac` 25 · `intake` 21 · `needs-human-review` 18 ·
  `priority:medium` 21 · `bounty` 10。**"标记为 ready" 多于 "有验收标准"**——`needs-ac` 的 25 条
  就是"还没写清怎么算完成"。
- **1 条 open issue 的工作已经在 `main` 上**（就是"已完成但没说"）：**#1555**。测法：
  `python3 scripts/done_but_open.py`。对报料者来说，"没人理"和"已经做完但没说"是分不出来的——后者是我们这边的失误。
  **这段原本写的是 4 条（#1555 / #1940 / #2015 / #2011），2026-09-23 更正为 1 条**：检测器当时只在引用字段里
  做**裸数字匹配**，于是 `#1940` 命中 `bbs.gongkong.com/d/201302/48**1940**`（别人的论坛帖号）、`#2015` 命中
  `samsaffron.com/archive/**2015**/03/31/…`（年份）、`#2011` 命中日期 `202011` 里的一段。它自己的误报比漏报更危险——
  按它的输出去关单，会给三个报料者发"已经做完了"的回执，而工作根本没做。已修（引用必须是
  `#NNN` / `intake-NNN` / 本仓 issue 链接三种形状之一，两侧加数字边界），并留了双向测试。
- **`done_but_open.py` 在 `main` 上，但没有任何 workflow 调用它**（`grep -l done_but_open
  .github/workflows/*.yml` 为空）。它目前是一次性动作，不是机制：下次要靠某个人记得跑。
- **14 个 open PR 里 12 个来自外部贡献者**，5 个已经超过 48 小时，最老的是 **#1544（14 天，且是
  draft）**。#2048 是本文件对应的悬赏 PR（issue #2044）。
- **304 个分支**是真实的平台债，但不要批量清：其中大多数是活跃 PR 的 head 分支；此前评估的结论是
  "只清 >60 天的，有开放 PR 的一律不碰"。

---

## 4. 只有 owner 能拍板的事（一行一个问题）

来源标注：**【#】** = open issue；**【H】** = `handoff-2026-09-19.md` §24.2 C（**该文件不公开**，
这是把它搬出来的一部分原因）；**【API】** = 本次实测。

1. **等审批的这一个 run 批不批？** 实测此刻有 1 个：`Publish misakanet`（`main`，
   2026-09-21T12:13:42Z 起）。【API】
2. **release PR #2020（2.35.0）合不合？** 它从 2026-09-21 起一直是 `mergeable_state: blocked`。【API】
3. **要不要把 `audit` 加进必需检查？**（以及 `lesson-gate`——#2039 正在把"永远上报"准备好，
   让它可以被设为必需）。这一步是把 #1920 关掉的"另一半"。【#1920 / #2039，API】
4. **`misakanet-automation-d1` 什么时候轮换？** 它 2027-03-01 过期；轮换需要有 Cloudflare 账号权限的
   人（步骤写在 #1886 里）。过期当天两个 cron 会开始失败，而没有人盯着 03:00 的 cron。【#1886】
5. **304 个分支清不清？**（改法建议：只清 >60 天、有开放 PR 的不碰）。【H / API】
6. **客户端提示头是否在 Python 安装器里补齐？** 两个安装器发的 `X-MisakaNet-*` 头不一致，影响客户端统计。【H】
7. **`v1` 这个 tag 是否随 action 变更前移？**【H】
8. **第二维护者席位给不给、给谁？** 这是本文件存在的理由：环境审批人只有 1 个、admin 只有 1 个，
   而交接面按 §1.4 第 5 条只存在于一台机器上。【#2044 / API】

> **维护规则**：每次更新本文（§5）时，把已经拍板的条目**从这里删掉**，把结论写成一行事实放进 §1 或 §2；
> 同时从 handoff 的最新一篇里把新的"需用户拍板"搬进来。这样 handoff 只留凭据线索，决策留在这里。

---

## 5. 这份文件怎么更新（否则它会变成第 4 个"看起来在维护"的物件）

**过期判据（可自检）**：顶部"快照时间"超过 **30 天**，或 §3 的数字与 §6 命令的输出不一致 → 视为**过期**，
不是"待更新"。一份写着旧数字的现状文档比没有更危险。

三个触发，按成本排序：

1. **每次 release**（`release-please` 的 PR 合并、tag 打上之后）：只更新**顶部的快照行**和 §3 的数字表。
   成本 = 跑 §6 的命令块（约 2 分钟）+ 复制输出。**机器数字只写在两处**（顶部一行、§3 一张表），
   就是为了让这一步这么便宜。
2. **每周一**，`guarded-repository.yml`（07:00 UTC）跑完之后花 5 分钟看 §4：有没有已经拍板的、
   有没有新出现的"需用户拍板"。新条目从 `needs-human-review` 标签的 open issue 和本地 handoff 进。
   顺手跑一次 `python3 scripts/done_but_open.py`（§3.1 那 4 条就是它找出来的）。
3. **任何带 `workflow-change` 标签的 PR 合并时**（门禁/环境被动过）：必须同步更新 §1.2、§1.3、§2.1、§2.4。
   这几节写的是"信任边界"，改门禁而不改它，等于让下一个人按错误的地图操作。

**故意不写的**：会每天变的东西（课程数、节点数、下载量）——那些有各自的 SSOT 门禁与
`docs/maintainer/` 里专门的报告；写进来只会加速腐烂。这里只留**接手一次值班需要知道的**。

---

## 6. 复现本文所有数字

用**你自己的**只读凭据（例如 `gh auth token` 的输出）导出到环境变量。**不要**把凭据写进本文档或任何提交。

> 口径提醒：下面几处 `grep` 数的是**你当前检出里的 `.github/workflows/`**。本文的数字取自
> `main` 的干净检出（69 个文件）；如果你本地带着未合并的 workflow 改动，数字会多出 1–2 个，
> 那是你的工作树，不是仓库现状。拿不准时在干净 clone 里复测，或改用上面的 contents API（它带 `?ref=main`）。

```bash
export GITHUB_TOKEN=<your own read-only credential>
API=https://api.github.com/repos/Ikalus1988/MisakaNet

# §1.1 工作流数量 / 定时数量 / 审批门数量 / PAT 数量 / pull_request_target 数量
curl -sS -H "Authorization: Bearer $GITHUB_TOKEN" "$API/contents/.github/workflows?ref=main" \
  | python3 -c 'import json,sys;print(len(json.load(sys.stdin)))'
grep -ln '^  schedule:'            .github/workflows/*.yml | wc -l
grep -ln '^    environment: release' .github/workflows/*.yml | wc -l
grep -ln 'secrets\.SHELDON_PAT'    .github/workflows/*.yml | wc -l
grep -ln '^  pull_request_target:' .github/workflows/*.yml | wc -l

# §1.1 自动化规模：最近 8 天的 run 数
curl -sS -H "Authorization: Bearer $GITHUB_TOKEN" "$API/actions/runs?created=%3E%3D2026-09-15&per_page=1" \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["total_count"])'

# §1.2 哪些 environment 有必需审批人；哪些 run 正在等审批
curl -sS -H "Authorization: Bearer $GITHUB_TOKEN" "$API/environments" \
  | python3 -c 'import json,sys;[print(e["name"], [r.get("reviewers") and [x["reviewer"]["login"] for x in r["reviewers"]] for r in e.get("protection_rules",[])]) for e in json.load(sys.stdin)["environments"]]'
curl -sS -H "Authorization: Bearer $GITHUB_TOKEN" "$API/actions/runs?status=waiting&per_page=20" \
  | python3 -c 'import json,sys;d=json.load(sys.stdin);print("waiting:",d["total_count"]);[print(" ",r["name"],r["head_branch"],r["created_at"]) for r in d["workflow_runs"]]'

# §2.1 必需检查（原文）+ 分支保护
curl -sS -H "Authorization: Bearer $GITHUB_TOKEN" "$API/rules/branches/main"     | python3 -m json.tool
curl -sS -H "Authorization: Bearer $GITHUB_TOKEN" "$API/rulesets/23826057"       | python3 -m json.tool
curl -sS -H "Authorization: Bearer $GITHUB_TOKEN" "$API/branches/main/protection" | python3 -m json.tool

# §3 积压
for q in is:open+is:issue is:open+is:pr is:closed+is:issue is:pr+is:merged; do
  curl -sS -H "Authorization: Bearer $GITHUB_TOKEN" \
    "https://api.github.com/search/issues?q=repo:Ikalus1988/MisakaNet+$q&per_page=1" \
    | python3 -c 'import json,sys;print(json.load(sys.stdin)["total_count"])'
done
python3 scripts/done_but_open.py                     # §3.1 的"已完成但没关"
curl -sSI -H "Authorization: Bearer $GITHUB_TOKEN" "$API/branches?per_page=1" | grep -i '^link:'   # 最后一页的 page=N 就是分支数

# §1.4 / §3 bus factor：最近 100 个 merged PR 的作者分布
curl -sS -H "Authorization: Bearer $GITHUB_TOKEN" \
  "https://api.github.com/search/issues?q=repo:Ikalus1988/MisakaNet+is:pr+is:merged&sort=updated&order=desc&per_page=100" \
  | python3 -c 'import json,sys,collections;print(collections.Counter(i["user"]["login"] for i in json.load(sys.stdin)["items"]).most_common(6))'

# §2.3 自动化产出核对（每周一那个 job 用的是同一个脚本）
GITHUB_TOKEN="$GITHUB_TOKEN" python3 scripts/automation_output_audit.py

# §2.4 注入扫描的实际覆盖面（CI 只跑 `--dir lessons`；`--dir docs` 会给出 high，且没有门禁因此变红）
grep -rn 'injection_scan' .github/workflows/
python3 scripts/injection_scan.py --dir docs | tail -3
```

**本次快照的实际输出**（2026-09-22，供对照）：69 / 18 / 8 / 6 / 5；33,094 runs；`release` 的审批人
`["Ikalus1988"]`，其余 environment 无审批人；waiting = 1（`Publish misakanet` @ `main`）；
72 / 14 / 669 / 707；`done_but_open.py` → 4 条（#1555 / #1940 / #2015 / #2011）；分支 304；
最近 100 个 merged PR 作者：`Ikalus1988 75` · `zsxh1990 13` · `dependabot[bot] 6` · 其他 6。

`automation_output_audit.py` 本次输出（窗口 30 天）：`pr-genius-check.yml` 1,426 runs / 130 产出 ·
`auto-merge-lessons.yml` 2,148 runs / 4 产出 · `intake-salvage-digest.yml` 35 / 1 ·
`intake-bot-demo.yml` 22,058 / 14 · `arch-review.yml` 尚未跑过（宽限 45 天，最长排期是每月）。


---

## 附：2026-09-22 会话交接（下一次先读这里）

**本轮完成**：8 个 PR 合并（#2032 #2039 #2047 #2049 #2051 #2052 #2053 #2054）；战略审视的 7 条建议全部拆成
issue（#2040–#2046）并**全部落地**；main 的必需检查从 **0 条**变为 **3 条**（`DCO / Signed-off-by`、
`test (ubuntu-latest, 3.11)`、`gate`），ruleset `23826057`，**无人可绕过（包括 owner）**。

**新增的机制（用之前先读它们自己的文档）**
- `scripts/done_but_open.py` —— 找出"工作已在 main 上、issue 仍开着"的 intake。
- `scripts/check_field_reports.py` —— field report 的 8 条结构规则（FR1/FR2 全语料，其余只门禁改动文件）。
- `scripts/bounty_claim.py` —— 悬赏认领四个判定；`ok` **绝不评论**（`__post_init__` 不变量）。
- `scripts/gate_mutation_audit.py` —— 每周变异抽查；**门禁在变异下仍绿 = 审计失败**。
- 里程碑 `v2.36` / `v2.37` / `later`（无 due date，绑定 release-please 的既有节律）。

**未决（需要 owner）**：`#1886`（Cloudflare token，已挂起）、`#2020`（release PR，`mergeable_state: blocked`）、
§4 的 12 项决定、`#1544`（赏金归属）、`#2056`（提问→反馈的 MCP 收件箱：是否做成 keyed inbox）、
`#2057`（注册页文案与节点计数的定位）。

**已知脆弱点（未修）**
- `docs/` **不在**注入扫描范围内（CI 只扫 `lessons/`），main 上有 4 处 high。
- **每个新 workflow 必须同时加它自己的 `docs/CI.md` 行，且只加自己的**（本轮我踩过两次：带了别的工作流的行；
  修正提交的分支因 422 没动而我的脚本仍打印"corrected"——两次都是"报告了没发生的事"）。
- `sync_lesson_count.py --check` 与 `injection_scan.py` 尚未纳入变异抽查（#2045 文档里列为下一步）。
- `install_misakanet_agent.py` 的 `--home` 默认值仍在解析参数时调 `Path.home()`（同一隐患，无测试覆盖）。

**收尾纪律（本轮教训，值得写进 SOP）**：我三次中止或回滚了自己的改动，原因都是**证据不足**而不是难度——
一个只改默认文本、会被 i18n 覆盖的文案编辑；一个声称成功但分支没动的推送；一个括号不匹配什么都没推的脚本。
**"看起来改了"与"确实改了"之间的差距，就是本会话一直在拆的那个病。**

**队列现状**：开放 PR 约 10（多为外部悬赏投稿）；≤1 小时的行动项约 26 条；课程类必须**攒批**后
**一次**重生成（`lessons/**` 共享生成物，一课一合会让每个 PR 都触发一次重生成）。

---

## 附：2026-09-23 会话交接（下一次先读这里）

**本轮落地**：#2069（`done_but_open` 的引用判据：裸数字 → 必须有形状）· #2065（注册页文案与 i18n）·
#2064（row-id 门禁不再扫文件系统）· #2072（补记 npm 2.34.0 的三行版本号）。
**在飞**：#2070（首页"注册记录"标签 + 客户端列表从安装器派生 + 未知类型不再显示成 Hermes）·
#2071（traffic 写入从 KV 搬到 D1 计数器，冷 isolate 不再首次请求就 flush）。
**新 issue**：#2066（纯模板 bounty PR 的机械判据）· #2073（ruleset 与回写 main 的冲突）·
#2074（KV 面板分不清"操作数/不同键"，含 10 分钟判定实验）· #2075（仍按不同键无界的家族）。

**本轮更正了本文自己的两处错**（都已在正文改掉，留痕在此）：
1. §2.1 写的"只有两条必需检查"是快照过时（`gate` 已加入，现在是三条，且 `bypass_actors: []`）；
2. §3.1 写的"4 条 open issue 的工作已经在 main 上"是**检测器误报**，真实是 **1 条**（#1555）——
   另外三条是裸数字匹配到了别人 URL 里的号码和年份。**这条值得记住：一个把误报当事实写进现状文档的
   工具，比没有工具更危险**；修完之后它才重新可信。

**KV（#1890）诊断被推翻**：面板里的 `traffic: 1,342` 是 **(isolate × key) 写入尝试**，不是不同键；
一次真实命名空间快照（685 键）里 `traffic:` 只有 **64 个**（= 4 类 × 16 天）。真正花掉额度的是
**每个冷 isolate 的第一次请求就 flush**（`trafficFlushedAt` 从 0 开始），约 1,300 次 PUT/天打在 4 个键名上。
#2071 把它改走 D1 计数器后，预期降到 0。**要不要付 $5/月，先看 #2074 的判定实验，不要先付。**

**新发现的门禁反噬**：`required_status_checks` 规则**对直接 push 也生效**，而 `bypass_actors: []` →
所有"跑完写回 main"的 workflow 都被拒。第一个撞上的是 npm 发布的记账步骤（**包发布成功、记账失败**，
run 于是显示红——"红"与"没发出去"在这里不是一回事）。受影响的还有每日的计数镜像、课程索引与徽章。
判据：**看受管表面最后一次真实提交的时间，不要看 run 的颜色**（#2073）。

**仍需 owner**：批准 #2071 的 worker 部署（`release` 环境）· 决定 #2073 走"自动化 bypass"还是"改成开 PR" ·
#2074 的判定实验窗口（UTC 00:00 之后）· 以及 §4 那张仍在等待的清单。

**未修的脆弱点（本轮新增）**：`done_but_open.py` 仍然**没有任何 workflow 调用它**（§3.1 记着这件事），
所以"已完成但没说"下次还是靠人记得跑；`docs/` 仍不在注入扫描范围内。
