# CI 第一性原理清点：84 个 workflow，量出来的数与建议（2026-10-16/17）

> 这份文件回答一个问题：`.github/workflows/` 里的每个文件**实际**在防哪一种失败，其中哪些
> 什么都防不到。全部数字来自 GitHub API 与本地文件的实测，不是印象；无法取到的数字在
> §1.5 里逐条写明。
>
> **本 PR 不删除任何 workflow。** 这里的产出是清点、建议和一条新规则（§5）。删一个 workflow
> 是另一件需要自己证据的事：凭感觉删掉的那个，和"为了把红变绿而删掉"的那个，从外面看一模一样。

测量时间：**2026-10-17 00:30–00:45 UTC**（workflow 清单与全部运行统计同一次采集）。
线上 `/api/health` 探针与 ruleset 读取为同一时段。

## 1. 清点（量的，不是假设的）

### 1.1 总数

| 量 | 数 | 怎么量的 |
|---|---|---|
| 仓库里 `.github/workflows/` 的文件数 | **84** | `ls .github/workflows/ \| wc -l`（全为 `.yml`，无 `.yaml`、无子目录） |
| GitHub Actions 列出的 workflow 记录 | **93** | `gh api repos/Ikalus1988/MisakaNet/actions/workflows?per_page=100` |
| 其中 `state=active` | **93（全部）** | 同上，`state` 字段 |
| 其中 GitHub 动态生成、仓库里没有文件的 | **9** | `dynamic/…` 路径：Dependabot×2、Dependency Graph、CodeQL、pages-build-deployment、Copilot 评审 |
| 其中**仓库里删掉了、GitHub 仍保留记录**的 | **3** | `ci-boost.yml`（7 次运行，最后一次 2026-08-11）、`dsh-integration.yml`（9 次，2026-09-05）、`dsh-tests.yml`（3 次，2026-09-02） |

那 3 个"幽灵 workflow"值得单独说：它们的 API 记录仍是 `active`，但
`commits?path=.github/workflows/<file>` 返回空、code search 也返回 0——即**它们不在 `main`
的任何历史里**（本 checkout 是 shallow，但 GitHub 的 git 历史不是）。最后一次运行都在一个月
以前，30 天内 0 次运行。它们不会跑，却仍出现在 Actions 列表里，和活着的 workflow 长得一样。

### 1.2 必需检查（合并阻断面）

`gh api repos/Ikalus1988/MisakaNet/rulesets` 只返回**一个** ruleset：
`23826057 main: the deterministic gates`（`target: branch`、`enforcement: active`）。
它的 `required_status_checks` 实测为 **4 个 context**：

| 必需 context | 拥有它的 workflow | job | 该 job 会不会 skip |
|---|---|---|---|
| `DCO / Signed-off-by` | `dco-check.yml` | job `dco`，但 context 由 Checks API 造 | **会**：job `if` 排除 `release-please[bot]`（见下） |
| `test (ubuntu-latest, 3.11)` | `ci-cross-platform.yml` | `test`，3 OS × 3 版本矩阵 | 不会（`pull_request` 无 `paths:` 过滤，job 无 `if`） |
| `gate` | `lesson-gate.yml` | `gate` | 不会（无 `paths:`，无 job `if`；无 lesson 变更时仍报结果） |
| `audit` | `pr-checks.yml` | `audit` | 不会（无 `paths:`，无 job `if`） |

**同名 job 的碰撞**（容易被误读成"另一个 workflow 也在报必需上下文"）：`gate` 这个名字在
`issue-quality-gate.yml` 里也有一个 job，`audit` 在 `dependency-vuln-audit.yml`、
`intake-kind-audit.yml` 里各有一个，`test` 在 `fatal-guard.yml` 里也有。这四个都不是必需上下文
的来源——它们分别只在 `issues:`、`schedule:`、或 `packages/fatal-guard/**` 的 push 上跑，
不会在 PR 上生成同名 check。**目前没有两个 workflow 抢同一个必需 context**，这也是为什么
ruleset 现在还能正常放行。

### 1.3 逐文件清点

列含义：**触发**里 `PR`=`pull_request`、`PRt`=`pull_request_target`、`run后`=`workflow_run`、
`check后`=`check_run`、`suite后`=`check_suite`、`repo事件`=`repository_dispatch`、`review后`=
`pull_request_review`；`+paths/+branches/+types` 表示带对应过滤（`cron(...)` 里是原始表达式）。
**最近一次**是该 workflow 最新一个 run 的日期（UTC）与结论。**30 天运行**是**下界**：API 单页
上限 100，带 `+` 表示"还有更多"；**30 天结论**同样只统计这最多 100 个 run，所以 `100+` 行的
比例只能读作"这 100 个里的分布"。**累计**是该 workflow 有史以来的 run 总数（精确）。

| workflow | 它在防哪一种失败 | 触发 | 最近一次 | 结论 | 30 天运行 | 累计 | 30 天结论 | 必需 |
|---|---|---|---|---|---|---|---|---|
| `adopt-pr.yml` | 维护者在 fork PR 上评论 `/adopt` → 走同仓分支重签 DCO 后重建 PR | 评论+types | 2026-10-16 | skipped | 100+ | 4140 | skipped:100 | — |
| `apply-d1-schema.yml` | 手工应用 `workers/d1/schema.sql`（幂等，不部署 worker） | 手工 | 2026-09-13 | success | 0 | 1 | — | — |
| `approval-watch.yml` | `release` 环境上等待人工审批的 run 超过阈值 → 开/更新提醒 issue | cron(17,47 * * * *), 手工, run后+types | 2026-10-16 | success | 100+ | 131 | success:100 | — |
| `arch-review.yml` | 每月一次架构自审（对 ROADMAP/架构文档做漂移检查） | cron(0 2 1 * *), 手工 | 2026-10-01 | success | 1 | 1 | success:1 | — |
| `auto-draft.yml` | 崩溃墓碑 → draft lesson → 自动开 PR | 手工, repo事件+types | 2026-06-22 | success | 0 | 1 | — | — |
| `auto-merge-docs.yml` | 带 label 的纯 docs PR 自动 squash 合并 | PRt+types | 2026-10-16 | skipped | 100+ | 9533 | skipped:90 cancelled:10 | — |
| `auto-merge-lessons.yml` | 带 `auto-merge-lesson` 的纯 lessons PR 自动合并 | PR+types | 2026-10-16 | skipped | 100+ | 11863 | skipped:89 cancelled:11 | — |
| `auto-sync-prs.yml` | 定时把 open PR 的分支 rebase 到最新 main | cron(17 */6 * * *), 手工 | 2026-10-16 | failure | 100+ | 1986 | success:96 failure:4 | — |
| `benchmark-workers-ai.yml` | 每周跑 Workers AI 的检索基准，写基准报告 | cron(0 2 * * 1), 手工 | 2026-10-12 | success | 4 | 17 | success:4 | — |
| `bounty-claim-guard.yml` | 一个 bounty 只允许一个实现；冲突时只发评论（永不判红） | PR+types, 手工 | 2026-10-16 | success | 100+ | 1245 | success:96 cancelled:3 queued:1 | — |
| `build-feed.yml` | 生成首页 live feed / activity 静态数据 | push+paths+branches, cron(23 */3 * * *), 手工 | 2026-10-16 | success | 100+ | 645 | success:100 | — |
| `cf-diagnostics.yml` | 只读的 Cloudflare 运营视图（504/522 排查） | 手工 | 2026-09-25 | success | 8 | 8 | success:7 failure:1 | — |
| `check-documented-gates.yml` | `docs/ci-gates.md` 的必需检查清单 vs 线上 ruleset | cron(11 7 * * 1), 手工 | 2026-10-12 | success | 2 | 2 | success:2 | — |
| `ci-cross-platform.yml` | pytest 全矩阵（3 OS × 3 版本）—— 必需 context 所在 | PR+types, 手工 | 2026-10-16 | — | 100+ | 3668 | success:61 cancelled:25 failure:11 in_progress:2 queued:1 | **是** |
| `ci-lesson-search.yml` | CI 失败时检索 MisakaNet 课程并回帖（自己解析失败签名） | 手工, run后+types | 2026-10-16 | skipped | 100+ | 35825 | skipped:88 success:12 | — |
| `cite-lesson.yml` | `usage` 标签的 issue → 引用追踪评论 | 手工, issue+types | 2026-10-16 | skipped | 100+ | 2318 | skipped:100 | — |
| `claim-enforcer.yml` | 8 小时认领窗口到期后释放 bounty | cron(0 */6 * * *), 手工 | 2026-10-16 | success | 100+ | 488 | success:100 | — |
| `codeql.yml` | CodeQL 静态安全扫描 | push+branches, PR+branches, cron(0 6 * * 0) | 2026-10-16 | — | 100+ | 4466 | success:96 queued:3 in_progress:1 | — |
| `d1-backup.yml` | D1 逻辑导出（artifact，防"库坏了"而不只是"改错了"） | cron(10 4 * * 1), 手工 | 2026-10-12 | failure | 3 | 3 | failure:3 | — |
| `d1-bootstrap.yml` | 一次性/恢复用 D1 引导（建库、写 database_id、同步语料、部署） | 手工 | 2026-09-03 | success | 0 | 5 | — | — |
| `d1-counters-report.yml` | 只读打印 D1 counters 各 scope 的桶数/总量 | 手工 | 2026-09-23 | success | 2 | 4 | success:2 | — |
| `dco-check.yml` | `DCO / Signed-off-by` 必需检查（check run + commit status 两形态） | PRt+types, 手工 | 2026-10-16 | success | 100+ | 4741 | success:100 | **是** |
| `dependency-vuln-audit.yml` | 已存在的依赖新爆 CVE（PR 上不会变红的那一半） | cron(41 5 * * 2), 手工 | 2026-10-13 | success | 2 | 2 | success:2 | — |
| `deploy-freshness.yml` | 线上 worker 的 `commit_sha` 是否等于 main（抓"部署压根没发生"） | cron(53 4 * * *), 手工, run后+types | 2026-10-16 | failure | 38 | 38 | failure:22 success:16 | — |
| `deploy-worker.yml` | push main 部署主 worker（`release` 环境，需人工审批） | push+paths+branches, 手工 | 2026-10-16 | — | 100+ | 250 | success:50 cancelled:49 waiting:1 | — |
| `docs.yml` | 站点构建 + PR 上的生成页面门禁 | push+paths+branches, PR+paths+branches | 2026-10-16 | — | 100+ | 2386 | success:80 cancelled:19 in_progress:1 | — |
| `dsh-client-e2e.yml` | DSH 客户端半身的真宿主/真浏览器行为回归 | PR, cron(40 3 * * *), 手工 | 2026-10-16 | — | 100+ | 826 | success:93 cancelled:6 queued:1 | — |
| `example-capture.yml` | 示例：把 CI 失败抓成 intake artifact（自述不自动发布） | 手工 | 从未 | — | 0 | 0 | — | — |
| `external-asset-integrity.yml` | CDN 上的固定资源是否还被服务（SRI 供应链面） | cron(23 7 * * 3), 手工 | 2026-10-14 | success | 2 | 2 | success:2 | — |
| `fatal-guard-publish.yml` | 发布 `@misaka-net/fatal-guard` 到 npm | push, 手工 | 2026-07-25 | success | 0 | 4 | — | — |
| `fatal-guard.yml` | `packages/fatal-guard/**` 的单测 | push+paths+branches, PR+paths, 手工 | 2026-10-16 | success | 12 | 626 | success:12 | — |
| `field-report-schema.yml` | `docs/field-reports/**` 是否过证据门槛 | push+branches, PR, cron(23 6 * * 1), 手工 | 2026-10-16 | — | 100+ | 3007 | success:93 cancelled:4 queued:2 failure:1 | — |
| `fix-dco.yml` | 评论 `/fix-dco` → rebase --signoff 后 force-push | 评论+types | 2026-10-16 | skipped | 100+ | 8500 | skipped:100 | — |
| `gate-mutation-audit.yml` | 每周变异测试：门禁是否还"能变红" | cron(43 6 * * 1), 手工 | 2026-10-12 | success | 3 | 3 | success:3 | — |
| `guarded-repository.yml` | HOL Guard 扫描 + GitHub provenance attestation | push+branches, cron(0 7 * * 1), 手工 | 2026-10-16 | — | 100+ | 1396 | failure:87 success:12 in_progress:1 | — |
| `install-smoke.yml` | 真装一次（npm / git stdio）并发布 install 徽章 | cron(43 6 * * *), 手工 | 2026-10-16 | success | 17 | 17 | success:17 | — |
| `intake-auto-review.yml` | 新 intake issue 自动预审（去重/分类/收据） | 手工, issue+types | 2026-10-16 | success | 100+ | 796 | success:73 skipped:27 | — |
| `intake-benchmark.yml` | intake bot 的 50 例基准 | push+paths+branches, 手工 | 2026-10-16 | success | 26 | 33 | success:26 | — |
| `intake-bot-demo.yml` | 狗粮：以外部用户拿到的入口（仓库根 `action.yml`）跑 intake bot 并回帖 | 手工, run后+types | 2026-10-16 | skipped | 100+ | 24134 | skipped:88 success:12 | — |
| `intake-kind-audit.yml` | 每周审计"读起来是问题却被当课程"的 intake | cron(30 6 * * 1), 手工 | 2026-10-12 | success | 4 | 7 | success:4 | — |
| `intake-pipeline-test.yml` | intake pipeline 端到端冒烟（PRD ③，手工） | 手工 | 2026-08-28 | success | 0 | 1 | — | — |
| `intake-salvage-digest.yml` | 每日 salvage 摘要 | cron(0 8 * * *), 手工 | 2026-10-16 | success | 30 | 59 | success:30 | — |
| `issue-intake-triage.yml` | MCP intake issue 分诊（贴标签/收据） | 手工, issue+types | 2026-10-16 | success | 100+ | 2178 | success:85 skipped:15 | — |
| `issue-quality-gate.yml` | issue 形态门禁（模板字段/质量） | issue+types | 2026-10-16 | success | 100+ | 2096 | success:100 | — |
| `lesson-gate.yml` | 课程结构门禁 —— 必需 context `gate` 所在 | PR, 手工 | 2026-10-16 | success | 100+ | 2529 | success:91 failure:9 | **是** |
| `lesson-notify.yml` | `new-lesson` issue → 通知 | issue+types | 2026-10-16 | skipped | 100+ | 4702 | skipped:100 | — |
| `lesson-quality.yml` | 课程 lint（阻断）+ 质量分 0.5 阈值（顾问） | PR+paths | 2026-10-16 | success | 100+ | 588 | success:100 | — |
| `lesson-security.yml` | 课程注入/危险模式扫描 | push+paths+branches, PR+paths | 2026-10-16 | success | 100+ | 1188 | success:100 | — |
| `mcp-stress.yml` | MCP 端点压测 + worker `node --test` 全量 | push+paths+branches, PR+paths, 手工 | 2026-10-16 | — | 100+ | 1222 | success:98 queued:1 failure:1 | — |
| `misakanet-publish.yml` | 发布 npm 主包 `misakanet`（plugin/skill 通道） | push, 手工, release+types | 2026-10-16 | success | 40 | 44 | success:21 failure:16 cancelled:3 | — |
| `misakanet-setup-ci.yml` | 安装器单测 + 打包产物 e2e | push+paths+branches, PR+paths, 手工 | 2026-10-15 | failure | 77 | 77 | success:66 failure:10 cancelled:1 | — |
| `misakanet-setup-publish.yml` | 发布 `@misaka-net/misakanet-setup` | push, 手工 | 2026-09-19 | success | 3 | 15 | success:3 | — |
| `newbie-welcome.yml` | `good first issue` 上的新人欢迎语 | 评论+types | 2026-10-16 | skipped | 100+ | 8905 | skipped:100 | — |
| `nightly-mirror-consistency.yml` | 课程镜像与源是否一致 | cron(17 3 * * *) | 2026-10-16 | success | 30 | 33 | success:30 | — |
| `pr-agent-review.yml` | PR-Agent 机器评审（含 `/review` 等 slash 命令） | PR+types, 评论+types | 2026-10-16 | skipped | 100+ | 9374 | skipped:65 success:21 failure:10 in_progress:2 cancelled:2 | — |
| `pr-audit-watch.yml` | 看住 `pr-checks.yml` 本身"有没有跑" | cron(17 */2 * * *), 手工 | 2026-10-16 | success | 100+ | 107 | success:100 | — |
| `pr-checks.yml` | 审计门禁：DCO 审计、密钥扫描、依赖审计、worker 测试、覆盖率 —— 必需 context `audit` 所在 | PR+types, 手工 | 2026-10-16 | — | 100+ | 4748 | success:78 failure:20 in_progress:2 | **是** |
| `pr-genius-check.yml` | PR-Genius 机器评审，把分析贴成 PR 评论 | PR+types | 2026-10-16 | success | 100+ | 4116 | success:87 skipped:13 | — |
| `pr-merged-thank.yml` | PR 合并后感谢贡献者 | PRt+types | 2026-10-16 | — | 100+ | 1918 | success:92 skipped:7 queued:1 | — |
| `pr-quality-gate.yml` | 按 check 结果给 PR 贴质量标签 | PR+types, check后+types | 2026-10-16 | — | 100+ | 13758 | success:47 skipped:27 cancelled:22 queued:4 | — |
| `pr-shape-guard.yml` | PR 形状（单主题、无 diff/markdown 泄露、引用不是认领） | PRt+types | 2026-10-16 | — | 100+ | 4190 | success:95 failure:4 queued:1 | — |
| `pr-thank-you.yml` | PR 合并后感谢贡献者（另一份实现） | PRt+types | 2026-10-16 | success | 100+ | 1404 | success:93 skipped:7 | — |
| `pr-welcome.yml` | 首次贡献者 PR 欢迎语 | PRt+types | 2026-10-16 | skipped | 100+ | 1974 | skipped:93 success:7 | — |
| `protect-pinned-issues.yml` | 被 `Closes #N` 误关的长期 issue 自动 reopen | issue+types | 2026-10-16 | success | 100+ | 315 | success:100 | — |
| `provenance-gate.yml` | 课程 `source:` URL 是否真的存在（抓 404 编造来源） | PR+paths, cron(17 6 * * 1), 手工 | 2026-10-16 | success | 100+ | 713 | failure:91 success:9 | — |
| `publish-container.yml` | 发布容器镜像到 GHCR | 手工, release+types | 2026-10-16 | — | 25 | 45 | success:23 in_progress:1 skipped:1 | — |
| `publish-dist.yml` | 把生成站点产物推到 `dist` 分支 | push+branches, 手工 | 2026-10-16 | success | 5 | 5 | success:4 cancelled:1 | — |
| `publish-mcp-registry.yml` | 把 `server.json` 发布到官方 MCP registry | 手工 | 2026-10-16 | — | 26 | 26 | success:14 failure:11 in_progress:1 | — |
| `pypi-wheel-smoke.yml` | 构建 wheel → 干净 venv 安装 → MCP 握手 | push+paths+branches, PR+paths, 手工 | 2026-10-16 | — | 100+ | 877 | success:92 cancelled:6 queued:1 failure:1 | — |
| `question-autopilot.yml` | `[Question]` issue：测检索是否已能回答、聚类、开 bounty | cron(40 6 * * *), 手工 | 2026-10-16 | success | 21 | 21 | success:21 | — |
| `register.yml` | 御坂网络注册 issue 欢迎并关闭（此 job 不写仓库） | 手工, issue+types | 2026-10-16 | skipped | 100+ | 1115 | skipped:99 success:1 | — |
| `registry-drift-watch.yml` | registry 广告的工具面 vs 实际 `tools/list`（Glama 漂移） | cron(26 11 * * *), 手工 | 2026-10-16 | success | 14 | 14 | success:13 failure:1 | — |
| `release-please.yml` | release-please 开/维护 release PR，并 dispatch 下游发布 | push+branches | 2026-10-16 | success | 100+ | 1483 | success:99 failure:1 | — |
| `release-pypi.yml` | 发布到 PyPI | push, 手工 | 2026-10-16 | — | 24 | 33 | success:23 queued:1 | — |
| `shadow-branch.yml` | 外部贡献者的影子分支隔离 | PR+types | 2026-10-16 | skipped | 100+ | 4589 | skipped:93 success:7 | — |
| `site-health.yml` | 线上可达性/形态探针（6 项） | cron(37 5 * * *), 手工 | 2026-10-16 | success | 23 | 23 | success:23 | — |
| `stale.yml` | stale 标签与自动关闭 | cron(0 6 * * *), 手工 | 2026-10-16 | success | 30 | 126 | success:30 | — |
| `star-request.yml` | PR 打开/批准后请求 star | PR+types, review后+types | 2026-10-16 | success | 100+ | 1773 | success:99 skipped:1 | — |
| `sync-d1.yml` | 把课程同步进 D1 | push+paths+branches, cron(0 3 * * *), 手工 | 2026-10-16 | success | 100 | 179 | success:91 failure:8 cancelled:1 | — |
| `sync-question-answers.yml` | 把已答复的 question intake 同步进 D1 `questions` | cron(20 7 * * *), 手工, issue+types | 2026-10-16 | skipped | 100+ | 2087 | skipped:91 cancelled:7 success:2 | — |
| `update-badges.yml` | 把 `data` 分支的计数徽章刷成最新 | push+paths+branches, cron(23 3 * * 1), 手工, run后+types | 2026-10-16 | — | 100+ | 2691 | success:69 cancelled:30 pending:1 | — |
| `update-lessons.yml` | 重新生成 `data/lessons.json`、课程页、OKF 导出 | push+paths+branches, cron(0 0 * * *), 手工 | 2026-10-16 | success | 75 | 264 | success:75 | — |
| `update-smithery-badge.yml` | smithery 徽章 JSON → `data` 分支 | cron(0 6 * * *), 手工 | 2026-10-16 | success | 30 | 37 | success:30 | — |
| `workers-builds-watch.yml` | CF Workers Builds 的 check-run 变红 → 开 issue | cron(*/30 * * * *), 手工, suite后+types | 2026-10-16 | skipped | 100+ | 6625 | skipped:71 cancelled:15 success:14 | — |

### 1.4 四个数，单独拿出来说

1. **84** 个 workflow 文件、**211,404** 次历史运行。其中**前 25 个**占了 185,082 次（87.6%）。
2. **60,000 次运行（top-2）属于同一个功能的两份实现**：`ci-lesson-search.yml`（35,825）与
   `intake-bot-demo.yml`（24,134）——两者都只在 `workflow_run` 于 `Cross-Platform Tests` 完成时
   被创建，两者都用同一句 job 级 `if: ${{ … conclusion == 'failure' }}` 过滤，因此两者在最近
   30 天里各有 88% 的运行是 **skipped 的完整 run**（不是"job 被跳过"，是 run 被创建后什么都不做）。
3. **5 个 workflow 在最近 30 天的 100 次运行里，一次非 skipped 的结果都没有**（§3.1）。
4. **19 个 workflow 对每一个 PR 都无过滤地触发**（`pull_request` / `pull_request_target` 且无
   `paths:`）。27 个 workflow 至少有一个 PR 触发。一个 PR 会带起十几条 run。

### 1.5 取不到 / 只能取到下界的数

| 想量的东西 | 实际拿到什么 | 为什么 |
|---|---|---|
| 某 workflow **30 天内精确的运行次数** | 下界：`min(N, 100)`，`+` 表示更多 | GitHub 的 runs API 单请求上限 100；翻页要几十次调用且与本报告结论无关。**累计次数是精确的**（`total_count`） |
| 30 天结论的精确分布 | 最多 100 个 run 的分布 | 同上。"100+" 行的百分比只能读作"这 100 个里的比例" |
| 历史累计总运行数 | 211,404（84 个文件）；若含 9 个动态 workflow 则 218,570 | 动态 workflow 不是本仓的 CI，单列 |
| `guarded-repository.yml` 那 87 次失败的**原因** | 只知道最近 3 次 push 触发的 run 是 `success`；87 次失败集中在 30 天窗口前段 | run 日志已过 90 天保留期的部分取不到；API 对 `38931987715` 的 job log 返回 `BlobNotFound`。**要归因需要在 Actions 页读一个具体失败的 run** |
| 30 天前的"最近一次运行"分布 | 只有"有史以来最近一次" | 本报告只取该字段 |
| 线上规则是否与本地一致 | 一致（只有 1 个 ruleset，且 4 个 context 都能在本地 workflow 里找到归属） | ruleset API 可读；`check_documented_gates.py` 需要 token，本地拿不到（见 §6） |

## 2. 三个被点名的形状：实测结果

### 2.1 必需检查里，有没有"在多数 PR 上 skip"的？

**没有。** 四个必需 context 都来自**无 `paths:` 过滤、job 无 `if`** 的 job（§1.2 表的最后一列），
`gate` 还是为 #1920 专门去掉 `paths:` 的。这是本仓已经用事故换来的一条设计（#1920：一个有时
不跑的必需检查会让 PR 永久卡在 "Expected — waiting for status to be reported"）。

**但有一个真 narrower 的例外，值得写在这里而不是下次再查**：`dco-check.yml` 的 job
`if: github.event.pull_request.user.login != 'release-please[bot]'`——它**对 release PR 跳过**。
`DCO / Signed-off-by` 是必需 context，而 release-please 生成的提交现在带 `signoff`
（`release-please-config.json` 的 `signoff` 是字符串），所以跳过的风险被另一条机制盖住了。
`release-please.yml` 会显式 dispatch 下游发布，release PR 的合并路径有自己的一份记录。
**结论：不是当前故障，但是"必需 context 依赖另一个机制兜底"的唯一一处**，改动 `dco-check.yml`
的 `if` 之前要知道这条。

另外：`fix-dco.yml` 曾在 2026-09-25 用 `GITHUB_TOKEN` force-push，把整个 PR 的 run 挂成
`action_required`（已修，改 `SHELDON_PAT`）。"必需检查永远不出现"的两种成因——**skip** 与
**挂起**——本仓都踩过，前者现在没有，后者有测试（`tests/test_dco_reports_both_status_forms.py`）
和文档记着。

### 2.2 带 `schedule:` 的，有没有最近没跑的？

**没有一个是"该跑却没跑"的。** 31 个 workflow 带 `schedule:`，实测最近一次运行时间：

| 节奏 | workflow | 最近一次（UTC） | 距今 |
|---|---|---|---|
| 每小时 | `approval-watch`、`workers-builds-watch`(每 30 分) | 2026-10-16 | 同小时 |
| 每日 | `build-feed`、`claim-enforcer`、`deploy-freshness`、`dsh-client-e2e`、`install-smoke`、`intake-salvage-digest`、`nightly-mirror-consistency`、`pr-audit-watch`、`question-autopilot`、`registry-drift-watch`、`site-health`、`stale`、`sync-d1`、`sync-question-answers`、`update-lessons`、`update-smithery-badge` | 2026-10-16 | ≤1 天 |
| 每周（周一/周二/周三） | `benchmark-workers-ai`(10-12)、`check-documented-gates`(10-12)、`dependency-vuln-audit`(10-13)、`external-asset-integrity`(10-14)、`field-report-schema`(10-16)、`gate-mutation-audit`(10-12)、`guarded-repository`(10-16)、`intake-kind-audit`(10-12)、`provenance-gate`(10-16)、`update-badges`(10-16) — 这些同时被 push/PR 触发 | 2026-10-12…16 | ≤5 天 |
| 每月 1 日 | `arch-review` | **2026-10-01** | 15 天 |
| 每周日 | `codeql`（同时被 push/PR 触发） | 2026-10-16 | ≤1 天 |

即：**没有一个触发了 GitHub 的 60 天不活跃停用规则**（最久的是 `arch-review` 的 15 天，它的
cron 本来就是每月 1 日）。9 个 workflow 的 API `state` 全是 `active`。

**"最近没跑"的是另一批——没有 `schedule:`、只在手工或窄条件下触发的那 5 个**（§3.2）：
`example-capture`（从未运行）、`auto-draft`（2026-06-22）、`fatal-guard-publish`（2026-07-25）、
`intake-pipeline-test`（2026-08-28）、`d1-bootstrap`（2026-09-03）、`apply-d1-schema`（2026-09-13）、
`d1-counters-report`（2026-09-23）、`cf-diagnostics`（2026-09-25）。
它们的风险不是被停用，而是**路径本身没人走**。

### 2.3 有没有两个 workflow 在查同一件事？

按"同一个 PR 事件上做同一件事"找，实测有四组**高置信**重复：

| 组 | 成员 | 重复在哪 | 它们各自还有的独有内容 |
|---|---|---|---|
| A | `ci-lesson-search.yml` + `intake-bot-demo.yml` | 同一 `workflow_run`（`Cross-Platform Tests`）+ 同一句 job `if`；都直接调用 `scripts/intake_bot.py` 拿裁决，然后把建议贴成 PR 评论 | `ci-lesson-search` 自己在 job 里解析失败签名（`ERROR_SIGNATURES`）并显式区分"机器人失败"与"没找到"；`intake-bot-demo` 走的是**仓库根 `action.yml`**，也就是外部用户引用的 `Ikalus1988/MisakaNet@v1` 那个入口。**两者加起来 59,959 次历史运行** |
| B | `pr-thank-you.yml` + `pr-merged-thank.yml` | 都在 `pull_request_target: closed` 且 `merged == true` 时给贡献者留言 | thank-you 读 `docs/_lessons_count.txt` 报语料规模；merged-thank 是另一份实现 |
| C | `update-badges.yml` + `update-smithery-badge.yml` + `install-smoke.yml`（后半段） | 三者都 `git push origin data`，写 `data` 分支的 `badges/*.json` | 各写不同文件（计数 / smithery / install）——**这不是真重复**，是同一个写者通道的三条实现；真正的成本在并发：`update-badges` 最近 30 天有 **30 次 cancelled**，四个触发里有两个是 `push` 到 main 和 `workflow_run`，会互相追尾 |
| D | `lesson-quality.yml` + `lesson-security.yml` | 都在 PR/`lessons/**` 过滤下跑课程检查 | security 做注入/危险模式；quality 做 lint + 质量分。两者都有独立红夹具，删任一个都会少一类失败 |

低置信（**不建议**在这个 PR 的基础上再合并，需要第二次意见）：
`pr-agent-review` / `pr-genius-check`（两个第三方机器评审，付费面与触发面不同）、
`intake-kind-audit` / `dependency-vuln-audit`（都开周报 issue，但查的是两个不相干的清单）。

### 2.4 补充：那个"从未报过它要报的漂移"的监控

上一次提交（`fe55c7d6`，2026-10-16）修的是 `registry-drift-watch.yml`——它的检测逻辑写错了，
所以它**从来没有报过它存在的唯一理由**。这类失败没法从运行历史里自动检出（"逻辑写错"不留形状），
能检出的只有它的近亲：**输出被写进没人读的地方**。实测两个：

* `cf-diagnostics.yml`（8 次运行，最后一次 2026-09-25）：只读、把答案打进 job 日志。没有 issue、
  没有 artifact、没有 check。**它没有自动读者**，只在有人已经知道要看什么时才有用。
* `arch-review.yml`（1 次运行，2026-10-01）：每月 1 日跑 `scripts/arch_review.py`，**输出有一等
  公民读者**——它用 `create-issue-from-file` 开一个带 `architecture`/`automated` 标签的 issue，
  并上传 `arch-report.json` artifact。它的问题不是没人读，是**每月只跑一次、且 issue 靠人看一眼**。

这两条**不建议删**（它们都是"出问题时唯一能回答某个问题"的工具），但说明了 §5 那条规则里
"输出写给谁"为什么必须写下来：`cf-diagnostics` 的答案是"没有自动读者"，
`arch-review` 的答案是"一个 issue + 一个 artifact"。

## 3. 分组与逐条理由

分四组：**保留**（必需，或有红夹具证明它能抓东西）、**合并**（两三个在做一件事）、
**移除**（被取代 / 重复 / 永久 skip / 保护的事实没人读）、**修**（本该跑却没跑好）。
**本 PR 不删除任何文件**；每条"移除"都写清"少了它会漏掉哪一种失败"，写不出来的就照直写
"说不出"。

### 3.1 保留（必需检查，4 个）

`dco-check.yml`、`ci-cross-platform.yml`、`lesson-gate.yml`、`pr-checks.yml`。
理由不是"它们在跑"，是 ruleset 23826057 要求它们，且它们的 job 不会在 PR 上 skip（§1.2）。
删掉或给它们加 `paths:` 过滤都会让 PR 卡在 "Expected — waiting for status to be reported"。

### 3.2 保留（有独立失败面，其余大部分）

判据：**说得出它防哪一种失败**，且那个失败别的 workflow 不会替它抓。
`fatal-guard.yml`、`field-report-schema.yml`、`lesson-quality.yml`、`lesson-security.yml`、
`mcp-stress.yml`、`pypi-wheel-smoke.yml`、`misakanet-setup-ci.yml`、`external-asset-integrity.yml`、
`dependency-vuln-audit.yml`、`gate-mutation-audit.yml`、`check-documented-gates.yml`、
`site-health.yml`、`install-smoke.yml`、`publish-dist.yml`、`publish-container.yml`、
`publish-mcp-registry.yml`、`release-please.yml`、`release-pypi.yml`、`deploy-worker.yml`、
`deploy-freshness.yml`、`approval-watch.yml`、`sync-d1.yml`、`sync-question-answers.yml`、
`update-lessons.yml`、`build-feed.yml`、`nightly-mirror-consistency.yml`、`claim-enforcer.yml`、
`stale.yml`、`question-autopilot.yml`、`issue-intake-triage.yml`、`issue-quality-gate.yml`、
`intake-auto-review.yml`、`intake-salvage-digest.yml`、`intake-kind-audit.yml`、
`protect-pinned-issues.yml`、`workers-builds-watch.yml`、`pr-audit-watch.yml`、
`pr-shape-guard.yml`、`pr-quality-gate.yml`、`bounty-claim-guard.yml`、`codeql.yml`、
`docs.yml`、`dsh-client-e2e.yml`、`provenance-gate.yml`、`guarded-repository.yml`、
`shadow-branch.yml`、`intake-benchmark.yml`、`benchmark-workers-ai.yml`、
`arch-review.yml`、`cf-diagnostics.yml`（后两个见 §2.4），以及 `intake-bot-demo.yml`
——它是那个**已发布 GitHub Action** 的唯一狗粮路径：`tests/test_intake_bot_action.py` 用 13 个
测试钉着它，删它会让 `Ikalus1988/MisakaNet@v1` 没有任何自动验证。**要减它的运行数，走 §3.3
组 A 的合并，而不是删文件。**

其中两条**今天就在抓真东西**，别误读成噪音：

* `deploy-freshness.yml`（30 天 22 红）——写这份报告时实测 `https://misakanet.org/api/health`
  的 `commit_sha` 是 `2e0d954bbe08`，而 main 是 `678adb26`，**线上落后 15 个提交**；
  `deploy-worker.yml` 最近 8 次里 5 次 `cancelled`、1 次仍在 `waiting` 等人工审批
  （`concurrency.cancel-in-progress` 让每次新 push 都取消掉上一个还在等审批的 run）。
  **这不是门禁坏了，是门禁抓到了它存在的理由。**
* `guarded-repository.yml`（30 天 87 红）——最近 3 次 push 触发的 run 都是 `success`，87 次失败
  集中在窗口前段（含 2026-10-07 那次被 `timeout-minutes` 弄成"GitHub 拒绝解析"的时段）。
  要归因得去 Actions 页读一个具体失败的 run（API 日志已不可取，见 §1.5）。

### 3.3 合并（三组，按可行性排序）

**组 A（推荐，但需要一次小心的一致性改动）：`intake-bot-demo.yml` → 并入
`ci-lesson-search.yml`。**
两者是同一事件的两次运行：都在 `workflow_run` 上监听 `Cross-Platform Tests`，都用
`if: … conclusion == 'failure'` 过滤，最近 30 天各 100 次运行里 88 次是"创建后什么都不做"的
skipped run。累计 35,825 + 24,134 = **59,959 次运行**。
但**不能直接删** `intake-bot-demo.yml`：它是 `./`（仓库根 `action.yml`，即外部用户引用的
`Ikalus1988/MisakaNet@v1`）的唯一调用点，`tests/test_intake_bot_action.py` 的
`test_the_dogfood_workflow_calls_the_entry_point_external_users_get` 钉着这一点。
正确做法是**把那次 `uses: ./` 调用搬进 `ci-lesson-search.yml` 的同一次运行**，然后删
`intake-bot-demo.yml`，并同步更新 `docs/CI.md`（`tests/test_workflow_inventory.py` 会强制这
两件事同时发生）与 `tests/test_workflow_triggers.py`。⚠️ 顺带保住一个**现在有的性质**：规则要求
"只由失败才能启动的路径必须也能手工启动"——`ci-lesson-search` 已经有 `workflow_dispatch`，
合并后**必须保留**，否则会掉进 `tests/test_workflow_inventory.py` 的第一条规则。
少了它会漏掉：**没有**（同一次失败仍然会被检索，`./` 仍然被调用；只是少创建一次 run）。

**组 B（推荐，小改动）：`pr-thank-you.yml` + `pr-merged-thank.yml` → 一个。**
两者都在 `pull_request_target: closed` 且 `merged == true` 时给贡献者留言，各有一套文案。
少了它会漏掉：**没有**（合并者仍会收到一条留言，只是从两条变一条）。
需要先决定保留哪一份文案（thank-you 读 `docs/_lessons_count.txt`，信息更多）。

**组 C（推荐，但只合并"写者通道"、不合并文件）：`update-badges.yml` +
`update-smithery-badge.yml` + `install-smoke.yml` 的 data 分支写入。**
三者都 `git push origin data`，写 `badges/*.json` 的不同文件。它们的触发面重叠
（`update-badges` 同时在 push main、`workflow_run`、周一 cron 上跑），最近 30 天
**30 次 cancelled**——不是功能重复，是并发打架。做法是给写 `data` 分支的步骤加一个共享
`concurrency` 组（或让三者都走同一条 `land_change.py` 式通道），**不删任何文件**。
少了它会漏掉：**没有**。

### 3.4 移除：建议删（3 个），附"少了它会漏掉什么"

| # | 文件 | 建议 | 少了它会漏掉哪一种失败 |
|---|---|---|---|
| 1 | `example-capture.yml` | **删**（或搬进 `docs/`） | **说不出。** 文件自述 "does NOT auto-publish"、名字带 "(not active)"、**累计 0 次运行**。它是给外部用户抄的用法示例。搬去文档后功能仍在，Actions 列表少一条。 |
| 2 | `intake-pipeline-test.yml` | **删**（需第二次意见） | **说不出。** 累计 **1 次**运行（2026-08-28），30 天 0 次，是 PRD ③ 的一次性手工冒烟，今天没有任何自动调用者。**为什么需要第二意见**：它验证的是"D1 里真的落了 draft 行、issue 真的开了"这条端到端路径；如果 `intake_pipeline.py` 仍需要一个人工冒烟入口，删它会少一个工具。 |
| 3 | `cite-lesson.yml` | **删**（需第二次意见） | **说不出。** 最近 30 天 100/100 skipped，窗口内没有一次非 skipped 结果；它已经在 `tests/test_no_workflow_pushes_to_main.py` 的例外名单里，理由是"它的 `git push` 目前什么都不推（前一步不写任何文件）——**是一次 no-op，不是被拦住的写**"。也就是说它维护着一条什么都不做的路径。**为什么需要第二意见**：`usage` 标签的引用追踪是**产品特性**（不是 CI），删 workflow 等于 retire 这个特性；`docs/CI.md` 也把它列为"设计上安静"的一类。**先决定特性是否还要，再决定 workflow。** |

### 3.5 移除：**不建议**删（容易被误删，逐个说明）

| 文件 | 看起来像 | 实际上 | 30 天实测 |
|---|---|---|---|
| `newbie-welcome.yml` | 8,905 次运行 100% skipped | 它只在**带 `good first issue` 标签的 issue 上、非成员**评论时说话；本仓最近没有这种组合。它的输出是一条欢迎语，不是门禁 | skipped:100 |
| `fix-dco.yml` | 8,500 次运行 100% skipped | 它是 **DCO 的求救通道**，`tests/test_fix_dco_wiring.py` 钉着它。skip 是因为没人发 `/fix-dco`——**这是健康，不是失效**（2026-09-25 真用到时它修好了 PR #2201/#2202） | skipped:100 |
| `adopt-pr.yml` | 4,140 次运行 100% skipped，`/adopt` 真实使用 0 次 | 同上，是**维护者工具**。`docs/CI.md` 已把它记为"删不删是 owner 的选择，不是维护者的默认动作" | skipped:100 |
| `lesson-notify.yml` | 4,702 次运行 100% skipped | 真短板是**投递成功与否不可见**，不是它多余（`docs/CI.md` 已记录） | skipped:100 |
| `pr-welcome.yml`、`shadow-branch.yml`、`auto-merge-docs.yml`、`auto-merge-lessons.yml`、`pr-agent-review.yml`、`register.yml`、`sync-question-answers.yml`、`workers-builds-watch.yml`、`intake-auto-review.yml` | skip 比例高（65–93%） | 都在条件的另一侧真的动过（7–35 次 success）。**高 skip 比例是窄入口的正常形状**；要修的是"run 被创建后什么都不做"这个成本（§3.3 组 A），不是删功能 | 见 §1.3 表 |

### 3.6 修（3 个，带证据）

1. **`misakanet-publish.yml` 的 `release:` 触发每次都失败，成功的发布全部来自
   `workflow_dispatch`。** 最近 30 天 40 次运行：21 success / 16 failure / 3 cancelled。
   失败 run 的注解原文（run 38931987715，2026-10-16）：

   > `X Tag "v2.44.2" is not allowed to deploy to npm-release due to environment protection rules.`
   > `X The deployment was rejected or didn't satisfy other protection rules.`

   实测 `repos/.../environments/npm-release/deployment-branch-policies` 是
   `[{"name":"main"},{"name":"v*"}]`，而 `deployments` 列表显示每个 release 都会产生**两个**
   deployment：一个 ref=`main`（成功）、一个 ref=`v2.44.2`（被拒）。**失败的是 tag 那个**，
   而成功的发布由 release-please 的 `workflow_dispatch` 完成。所以 tag 触发的这一半是
   **结构性必红**：要么把它从 `on:` 里去掉（发布仍由 dispatch 完成），要么在 GitHub 侧把
   规则改成环境真正允许的形状。**这类红的代价不是失败本身，是它教人忽略这个 workflow 的红。**
2. **`misakanet-setup-ci.yml` 最近一次运行（2026-10-15）是红的**（77 次运行里 10 次失败）。
   失败在 `e2e (ubuntu-latest, node 22)` 的 `Live endpoint checks` 步骤——一条腿上的联网探针
   打生产端点。**它不是必需检查，但会在 main 上留红**，和上一条同一个代价。要么把联网探针
   改成不阻塞（并在文件里写明为什么），要么固定它所依赖的端点。
3. **`d1-backup.yml` 3 次运行全部失败，一次都没成功过。** 2026-09-24 建，每周一 04:10 UTC，
   最近三次（09-28 / 10-05 / 10-12）全 `failure`；30 天窗口内 3/3 红。它自称与 Time Travel
   互补（覆盖"六周后发现库坏了"这一格），所以这三条红意味着**这一格现在是空的**。
   **归因未完成**：job log API 返回 `BlobNotFound`，需要在 Actions 页打开一次失败的 run 读原因。
   这是本报告里唯一一条"门禁在红、原因未查明"的项。

### 3.7 结论：把数说出来

**84 个 workflow 文件保护着远少于 84 类的失败。** 按本报告能叫出名字的独立失败面归类，
真正不可替代的失败面约 **20 种**（四个必需 context、安装器 e2e、wheel、MCP 压测、
课程结构 / 质量 / 安全 / 来源、field report schema、外部资源完整性、已存在依赖的 CVE、
门禁能否变红、文档 vs ruleset、站点健康、部署新鲜度、审批等待、D1 同步、question 同步、
语料生成一致性、registry 漂移、Workers Builds 红、误关 issue、bounty 认领、stale…）。
**20 / 84 ≈ 24%。** 剩下 64 个文件里，大部分是**同一类失败的不同表达**（通知/欢迎类 8 个、
周报审计类 6 个、发布类 6 个、`data` 徽章写入 3 个、PR 评论机器人 7 个、D1 手工运维 3 个），
另有 **4 个说不出自己在防什么**：§3.4 的 3 个，加上 `auto-draft.yml`（唯一一次运行是
2026-06-22 的手工测试，30 天 0 次，它的 `repository_dispatch` 入口依赖一个本仓之外的 relay）。

**这就是那个数：84 个 workflow，约 20 种失败面。** 未来新增 CI 的默认答案应该是"否"。

## 4. 本报告用到的证据与复现命令

采集时间 2026-10-17 00:30–00:45 UTC。任何人可以原样重跑：

```bash
# workflow 记录与 state（本报告 §1.1）
gh api "repos/Ikalus1988/MisakaNet/actions/workflows?per_page=100" \
  --jq '.workflows[] | [.id, .state, .path, .name] | @tsv'

# 唯一一个 ruleset 与它的必需 context（§1.2）
gh api repos/Ikalus1988/MisakaNet/rulesets
gh api repos/Ikalus1988/MisakaNet/rulesets/23826057 \
  --jq '.rules[]|select(.type=="required_status_checks")|.parameters.required_status_checks[].context'

# 某个 workflow 的累计次数 + 最近一次 + 最近 30 天（§1.3；30 天列表最多 100 条）
gh api "repos/Ikalus1988/MisakaNet/actions/workflows/<id>/runs?per_page=1" --jq '.total_count'
gh api "repos/Ikalus1988/MisakaNet/actions/workflows/<id>/runs?created=%3E<ISO8601>&per_page=100" \
  --jq '.workflow_runs | length'

# 线上 worker 到底跑在哪一个 commit（§3.2）
curl -sS https://misakanet.org/api/health | python3 -c "import json,sys;print(json.load(sys.stdin)['commit_sha'])"
git log -1 --format=%H

# npm-release 环境的 deployment 规则与真实 deployment 的 ref（§3.6 第 1 条）
gh api repos/Ikalus1988/MisakaNet/environments/npm-release/deployment-branch-policies
gh api "repos/Ikalus1988/MisakaNet/deployments?environment=npm-release&per_page=10" \
  --jq '.[] | [.id, .ref, .created_at] | @tsv'
```

本地读的部分（不需要网络）：

```bash
ls .github/workflows/ | wc -l                       # 84
python3 -c "import yaml,glob;[yaml.safe_load(open(p)) for p in glob.glob('.github/workflows/*.yml')]"
grep -c 'workflow_run' .github/workflows/*.yml | grep -v ':0'
```

那 3 个"幽灵 workflow"的判据（§1.1）：

```bash
gh api "repos/Ikalus1988/MisakaNet/commits?path=.github/workflows/ci-boost.yml" --jq 'length'   # 0
gh api "search/code?q=repo:Ikalus1988/MisakaNet+filename:ci-boost.yml" --jq '.total_count'      # 0
```

## 5. 一条规则（已写进 `docs/agents/repo-operations.md` §2）

```text
新增一个 workflow 或 job 之前，先回答三件事，答不出来就不加：

1. 它防的是哪一种具体的失败？说得出名字，而不是"多加一道保险"。
2. 有没有一个红夹具（测试）证明它**能在缺失时变红**？没有夹具的门禁和没有门禁
   从外面看一模一样——2026-10-07 的两个 workflow 就是这样在 main 上死了八天。
3. 它会不会阻断合并？会的话，它必须在**每一个** PR 上都有结论（不要用 `paths:` 过滤
   一个必需检查，否则 PR 会永远停在 "Expected — waiting for status to be reported"，#1920）。
```

这条规则也适用于"加一个 job"，不只是加文件：本仓最贵的两次不是多了一个 workflow，是
**一个必需 job 在等一个永不出现的 context**。

## 6. 没能验证的部分

| 项 | 状态 | 需要什么 |
|---|---|---|
| `guarded-repository.yml` 87 次失败的具体原因 | 未查明。只知道最近 3 次 push 触发是 success，30 天窗口前段集中失败 | 在 Actions 页读一个具体失败的 run（API job log 对已过期 run 返回 `BlobNotFound`） |
| `d1-backup.yml` 三次失败的原因 | 未查明 | 同上（同上原因） |
| 30 天内每个 workflow 的**精确**运行次数 | 只有下界 `min(N,100)` | 翻页几十次 API 调用；不影响本报告任何结论 |
| `misakanet-setup-ci.yml` 的 `Live endpoint checks` 是本仓端点抖动还是探针本身不稳 | 未查明 | 读那次 run 的失败步骤日志 |
| `ci-cross-platform.yml` 最近 100 个 run 里 25 次 `cancelled` 为何偏高 | 未查明（`concurrency.cancel-in-progress` 在 PR 上是设计如此，但 25% 值得看一眼） | `gh api .../actions/runs?status=cancelled` 逐条看 `run_attempt` 与 head |
| 本地 `check_documented_gates.py` 的"文档 vs ruleset"比对 | **未做**：无 token，脚本按设计 exit 2（"未比对"，不是漂移）。而同一份 ruleset 已用 `gh` 直接读过（§1.2），四项与 `docs/ci-gates.md` 的 Hard Gates 表一致 | 给脚本 `SHELDON_PAT`，或 `--from-file` 喂一份保存的 ruleset 响应 |

