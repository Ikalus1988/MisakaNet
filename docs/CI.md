# MisakaNet CI Workflow 清单（docs/CI.md）

> 审计 2026-09-05（T2.3）：`.github/workflows/` 当时共 **53 个** workflow，本页为其完整
> 索引，之后新增的门禁按同一格式补录（最近一次：`misakanet-setup-ci.yml`，2026-09-18；
> 目录现为 69 个文件，未逐条收录的以 `ARCHITECTURE.md` 的计数与目录本身为准）。
> 触发条件建议以各
> workflow 文件内的 `on:` 为准；分类是维护性归类，非强制。
>
> 定位问题：先看「失败的是哪个 job」→ 在本表找到 workflow → 点 GitHub Actions
> 对应运行查看日志 → 按文末「常见失败与修复」处理。CI 运行失败不等于代码坏了：
> 许多 workflow 是机器人/数据管道，失败常在外部依赖（D1、registry、配额）。


## 质量门禁（21）

| workflow | 用途 | 触发 | 定时 |
|---|---|---|---|
| `auto-merge-docs.yml` | Auto-Merge Docs PRs | PR |  |
| `auto-merge-lessons.yml` | Auto-Merge Lessons（`auto-merge-lesson` opt-in 标签）| PR, check_suite |  |
| `bounty-claim-guard.yml` | Bounty Claim Guard | PR（opened/edited）|  |
| `ci-cross-platform.yml` | Cross-Platform Tests | PR, 手动 |  |
| `codeql.yml` | CodeQL | PR, push, 定时 | `0 6 * * 0` |
| `dco-check.yml` | DCO Check | PR, 手动 |  |
| `field-report-schema.yml` | Field Report Schema | PR, push, 手动 |  |
| `fix-dco.yml` | DCO Auto-Fix | 评论 |  |
| `gate-mutation-audit.yml` | Gate Mutation Audit | 定时, 手动 | `43 6 * * 1` |
| `lesson-gate.yml` | Lesson Quality Gate | PR |  |
| `lesson-quality.yml` | Lesson Quality Score | PR |  |
| `lesson-security.yml` | Lesson Security Scan | PR, push |  |
| `mcp-stress.yml` | MCP Endpoint Stress Tests | PR, push, 手动 |  |
| `misakanet-setup-ci.yml` | Setup Package CI（安装器：3 OS × Node 18/20/22 单测 + 打包产物 e2e）| PR, push, 手动 |  |
| `pr-agent-review.yml` | PR-Agent Code Review | PR, 评论 |  |
| `pr-checks.yml` | Misaka Network Agent Auditor | PR, 手动 |  |
| `pr-genius-check.yml` | PR Genius Check | PR |  |
| `pr-quality-gate.yml` | PR Quality Gate | PR |  |
| `provenance-gate.yml` | Provenance Gate（溯源矩阵完整性）| PR, 定时, 手动 | `17 6 * * 1` |
| `pr-shape-guard.yml` | PR Shape Guard | PR(目标) |  |
| `shadow-branch.yml` | Shadow Branch - External Agent Isolation | PR |  |

## 数据/索引（22）

| workflow | 用途 | 触发 | 定时 |
|---|---|---|---|
| `auto-draft.yml` | Auto-Draft from Crash Tombstone | 手动 |  |
| `auto-sync-prs.yml` | Auto-Sync PR Branches | push, 手动 |  |
| `benchmark-workers-ai.yml` | Workers AI Lesson Benchmark (weekly) | 定时, 手动 | `0 2 * * 1` |
| `build-feed.yml` | Build Live Feed（并写 `docs/data/activity.json`：首页活动面板的静态快照，由 `scripts/sync_site_activity.py` 生成——`/api/analytics/traffic` 冷路径实测 17 秒，不能让浏览器直连）| push, 定时, 手动 | `23 */3 * * *` |
| `example-capture.yml` | Example Capture (not active) | 手动 |  |
| `intake-auto-review.yml` | Intake Auto Review | issues, 手动 |  |
| `intake-kind-audit.yml` | Intake Kind Audit | 定时, 手动 | `30 6 * * 1` |
| `intake-pipeline-test.yml` | Intake Pipeline Test (PRD ③) | 手动 |  |
| `intake-salvage-digest.yml` | Intake Salvage Digest（另跑 `scripts/done_but_open.py`：工作已在 `main`、issue 还开着的 intake，非空才写进 digest 议题；**只报告，不关单**）| 定时, 手动 | `0 8 * * *` |
| `issue-intake-triage.yml` | MCP Intake Triage | issues, 手动 |  |
| `sync-d1.yml` | Sync Lessons to D1 (PRD ④) | push, 定时, 手动 | `0 3 * * *` |
| `d1-backup.yml` | D1 backup（每周一次 `d1 export` 存档 + 打印 storage backend 与 Time Travel bookmark；artifact 保留 90 天）| 定时, 手动 | `10 4 * * 1` |
| `sync-node-counter.yml` | Mirror Node Counter（把 D1 计数镜像到 main）| 定时, 手动 |  |
| `apply-d1-schema.yml` | Apply D1 schema | 手动 |  |
| `d1-counters-report.yml` | D1 counters report | 手动 |  |
| `cf-diagnostics.yml` | CF diagnostics（只读运维视图：#2126 的 504/522 归因 + 区级 route 表与 KV namespace 清单 + D1 Time Travel 资格与 bookmark + durable store 健康）| 手动 |  |
| `guarded-repository.yml` | Guarded Repository（仓库守卫巡检）| push, 定时, 手动 | `0 7 * * 1` |
| `update-smithery-badge.yml` | Update Smithery Badge (daily) | 定时, 手动 | `0 6 * * *` |
| `sync-question-answers.yml` | Sync Question Answers | 定时, 手动 | `20 7 * * *` |
| `update-badges.yml` | Update Badge Counts | push, 定时, 手动 | `23 3 * * 1` |
| `update-lessons.yml` | Update lessons.json | 定时, 手动 | `0 0 * * *` |
| `nightly-mirror-consistency.yml` | Nightly Mirror Consistency（镜像一致性）| 定时 |  |

## 发布/部署（12）

| workflow | 用途 | 触发 | 定时 |
|---|---|---|---|
| `d1-bootstrap.yml` | D1 Bootstrap (PRD ④) | 手动 |  |
| `deploy-worker.yml` | Deploy Cloudflare Worker（`workers/register-proxy-sw.js` **和** `workers/wrangler.toml` 变更都触发；部署后按 config 校对 keepalive cron，不一致即失败） | push, 手动 |  |
| `docs.yml` | Deploy Documentation | PR, push |  |
| `fatal-guard-publish.yml` | Publish @misaka-net/fatal-guard | push |  |
| `fatal-guard.yml` | fatal-guard CI | PR, push, 手动 |  |
| `publish-container.yml` | Publish Container to GHCR | 手动, release |  |
| `release-please.yml` | Release Please | push |  |
| `release-pypi.yml` | Release to PyPI | push |  |
| `pypi-wheel-smoke.yml` | PyPI Wheel Smoke（wheel 安装冒烟）| PR, push, 手动 |  |
| `misakanet-publish.yml` | Publish misakanet（npm，由 release-please 派发并回写版本）| tag push, 手动 |  |
| `misakanet-setup-publish.yml` | Publish @misaka-net/misakanet-setup | tag push, 手动 |  |
| `publish-mcp-registry.yml` | Publish to MCP Registry（等 PyPI 落地后发布）| 手动 |  |

## 社区/机器人（15）

| workflow | 用途 | 触发 | 定时 |
|---|---|---|---|
| `cite-lesson.yml` | 知识引用追踪 | issues, 手动 |  |
| `claim-enforcer.yml` | Claim Window Enforcer | 定时, 手动 | `0 */6 * * *` |
| `issue-quality-gate.yml` | Issue Quality Gate | issues |  |
| `leaderboard-watch.yml` | Leaderboard Watch | push, 手动 |  |
| `lesson-notify.yml` | 新 Lesson 通知 | issues |  |
| `newbie-welcome.yml` | Newbie Welcome | 评论 |  |
| `pr-merged-thank.yml` | Thank Merged PR Contributor | PR(目标) |  |
| `pr-thank-you.yml` | PR Thank You | PR(目标) |  |
| `pr-welcome.yml` | PR Welcome | PR(目标) |  |
| `register.yml` | 御坂网络注册 | issues, 手动 |  |
| `stale.yml` | Stale PR / Issue Manager | 定时, 手动 | `0 6 * * *` |
| `star-request.yml` | Star Request | PR |  |
| `adopt-pr.yml` | Adopt Fork PR（维护者评论 `/adopt`）| 评论 |  |
| `protect-pinned-issues.yml` | Protect long-running issues | issues |  |
| `pr-audit-watch.yml` | PR Audit Watch（PR 审查巡检）| 定时, 手动 | `17 */2 * * *` |

## 基础设施（6）

| workflow | 用途 | 触发 | 定时 |
|---|---|---|---|
| `ci-lesson-search.yml` | Search MisakaNet on CI Failure（CI 失败时检索匹配课程；`workflow_dispatch` 可手工验证）| workflow_run（仅 `Cross-Platform Tests` 失败）、手动 |  |
| `intake-bot-demo.yml` | Intake Bot Demo（失败 CI 上跑 intake-bot 的 dogfood 入口）| workflow_run, 手动 |  |
| `intake-benchmark.yml` | Intake Bot Benchmark | push, 手动 |  |
| `arch-review.yml` | Monthly Architecture Review | 定时（月度）, 手动 |  |
| `workers-builds-watch.yml` | Site build watch（站点部署流水线 `Workers Builds: misakanet-web` 变红时开 issue；**只报状态变化**、不刷屏，也不把该 check 加进规则集必查项——理由见 #2136）| check_suite（仅 Cloudflare app、仅 main）, 定时, 手动 | `*/30 * * * *` |
| `site-health.yml` | Site Health（`scripts/site_health_check.py` 的 CI 调用点：每天探线上首页与 `/api/*` 等 6 个入口 + 首页关键标记；**连续 3 次都不过才算失败**——实测从真实机器发出约 1/4 请求会在 TLS 握手超时，单次失败是天气不是故障。报告进 step summary，并作为 artifact 留存）| 定时, 手动 | `37 5 * * *` |

## 有意保持安静的自动化（#1826 的结论，2026-09-25 复核）

这一节存在的理由：`#1826` 的审计把"跑了很多次但那个有用的分支从没走到"列成清单，其中几条**不是坏掉的**，
而是**设计上就不会触发**。静默空转确实比没有更贵（它让人以为有人管），但**把"设计如此"和"坏了"分开**才是重点——
下面每条都带实测状态与"什么情况下它会真的动"。下次审计不必重新发现一遍。

| workflow | 实测（2026-09-25） | 它为什么安静 | 什么会让它动 |
|---|---|---|---|
| `adopt-pr.yml` | 70 次运行 / 70 次 skipped；`/adopt` 真实使用 **0** 次 | 入口是维护者在 fork PR 上评论 `/adopt`；这条路径从没被用起过 | 有人真的评论 `/adopt`（`docs/maintainer/adopt-fork-pr.md`）。**删掉它是 owner 的选项**，不是维护者的默认动作 |
| `stale.yml` | 97 次 success；`label:stale` 1 条；自动关闭评论 0 条 | 豁免面很大（`keep`/`registered`/`help wanted`/`bounty` + `exempt-all-milestones`），而本仓多数开放项都带其中至少一个 | 出现既不豁免、又 14 天（PR）/30 天（issue）无活动的项。**这是它的设计目的**：宁可空转，也不要在一堆 bounty 上乱贴 stale |
| `lesson-notify.yml` | 2953 次运行：2946 skipped / 2 success / 5 failure | 只在 `new-lesson` 标签出现时才有意义，而该标签全仓只有 6 条 | 新建的 lesson PR 打上 `new-lesson`。投递成功与否**不可见**——这是它真正的短板，要改不是关 |
| `intake-kind-audit.yml` | 3 次 clean；2026-09-25 手工重跑仍然 clean（37 条 open `mcp-intake`） | 语料里**确实**没有错分 | 出现"内容读起来是问题、却被当课程处理"的 intake。这条以前无法区分"真的干净"和"检测从不触发"，现在 `tests/test_intake_kind_audit.py` 用夹具证明检测能触发、且摘要句与 workflow 的 grep 是同一条 |
| `automation_output_audit.py` | 2026-09-21 定时运行 **success**（job `automation-output-audit`） | push 触发时该 job 会被 skip，只有每周一 07:00 的窗口才跑 | 每周一。`#1826` 记的"这个 job 一次都没跑过"是因为当时窗口还没到——**已经跑过了** |

**已修好的那几条**（同一次复核）：`pr-checks.yml` 的 Auto-Merge Gate（布尔比 `true` 而不是 GraphQL 的 `MERGEABLE` 枚举）、
`auto-merge-docs.yml` 的触发补上 `labeled`、`auto-draft.yml` 不再依赖没有写入者的 `crash-reports/` 路径、
以及 `claim-enforcer.yml` 的窗口（4h → 与文档一致的 **8h**，并把数字收进一个变量，见 `tests/test_claim_window.py`）。

## 常见失败与修复路径

| 失败信号 | 原因 | 修复 |
|---|---|---|
| DCO Check 红 | commit 缺 `Signed-off-by` | `git commit --amend -s`；或在 PR 评论发 `/fix-dco`（`fix-dco.yml`） |
| lesson-gate / lesson-quality 红 | lesson 命名/结构/质量不达标 | 本地 `python3 scripts/check_lesson_quality.py` 与 `python3 scripts/validate_lessons.py` 复现后修改 |
| pr-shape-guard 红 | PR 改动形状/单次意图不合规 | 读 guard 输出；保持 PR 单主题、避免大杂烩提交 |
| lesson-security 红 | lesson 内含疑似密钥/危险模式 | 本地 `gitleaks git --pre-commit --config .gitleaks.toml` 复现；参考 `docs/cloudflare-waf/` 与 SECURITY.md |
| CodeQL 红 | 静态分析告警（security-extended） | 看告警路径；.github/codeql/codeql-config.yml 记录了已知误报与排除理由 |
| sync-d1 红 | D1/远端同步失败（配额/凭据/网络） | `workflow_dispatch` 重跑；检查 `CF_API_TOKEN` 与 D1 database_id |
| update-lessons 红/无提交 | lessons.json 无变化则跳过提交是**预期** | 需要强制刷新时 `workflow_dispatch` 触发 |
| release-please 出 PR | 发版流程**正常** | review 后合并；合并后按 handoff 的“对齐”流程更新 server.json/glama.json（2.27.x 线） |
| ci-lesson-search 相关 | 检索质量巡检 | 输出即提交入口：把失败案例作为 lesson 提交，喂给知识库 |

## 说明与边界

- 本清单的「触发」列由脚本读取 `on:` 提取（push/pull_request/schedule/manual 等），
  未展开 paths/branches 过滤；精确行为以 workflow 文件为准。
- 「失败时看哪」：GitHub Actions → 左侧 workflow → 最近运行 → 点失败 job 展开日志；
  机器人类 workflow 的日志头部通常直接给出原因与重跑方式。
- 53 个文件中有部分是**一次性/演练**性质（如 `d1-bootstrap.yml`、
  `intake-pipeline-test.yml`、`example-capture.yml`——后者注释自述不自动发布），
  日常开发主要关心「质量门禁」组。
- 维护：`.github/workflows/` 增删后手工更新本表；本页为 2026-09-05 快照
  （53 个 workflow，触发条件由脚本读取 `on:` 提取）。

