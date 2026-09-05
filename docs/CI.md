# MisakaNet CI Workflow 清单（docs/CI.md）

> 审计 2026-09-05（T2.3）：`.github/workflows/` 共 **53 个** workflow。本页为完整
> 索引——名称、触发条件（机器提取）、类别与通用修复路径。触发条件建议以各
> workflow 文件内的 `on:` 为准；分类是维护性归类，非强制。
>
> 定位问题：先看「失败的是哪个 job」→ 在本表找到 workflow → 点 GitHub Actions
> 对应运行查看日志 → 按文末「常见失败与修复」处理。CI 运行失败不等于代码坏了：
> 许多 workflow 是机器人/数据管道，失败常在外部依赖（D1、registry、配额）。


## 质量门禁（16）

| workflow | 用途 | 触发 | 定时 |
|---|---|---|---|
| `auto-merge-docs.yml` | Auto-Merge Docs PRs | PR |  |
| `ci-cross-platform.yml` | Cross-Platform Tests | PR, 手动 |  |
| `codeql.yml` | CodeQL | PR, push, 定时 | `0 6 * * 0` |
| `dco-check.yml` | DCO Check | PR, 手动 |  |
| `fix-dco.yml` | DCO Auto-Fix | 评论 |  |
| `lesson-gate.yml` | Lesson Quality Gate | PR |  |
| `lesson-quality.yml` | Lesson Quality Score | PR |  |
| `lesson-security.yml` | Lesson Security Scan | PR, push |  |
| `manual-audit.yml` | Manual PR Audit | 手动 |  |
| `mcp-stress.yml` | MCP Endpoint Stress Tests | PR, push, 手动 |  |
| `pr-agent-review.yml` | PR-Agent Code Review | PR, 评论 |  |
| `pr-checks.yml` | Misaka Network Agent Auditor | PR, 手动 |  |
| `pr-genius-check.yml` | PR Genius Check | PR |  |
| `pr-quality-gate.yml` | PR Quality Gate | PR |  |
| `pr-shape-guard.yml` | PR Shape Guard | PR(目标) |  |
| `shadow-branch.yml` | Shadow Branch - External Agent Isolation | PR |  |

## 数据/索引（15）

| workflow | 用途 | 触发 | 定时 |
|---|---|---|---|
| `auto-draft.yml` | Auto-Draft from Crash Tombstone | 手动 |  |
| `auto-sync-prs.yml` | Auto-Sync PR Branches | push, 手动 |  |
| `benchmark-workers-ai.yml` | Workers AI Lesson Benchmark (weekly) | 定时, 手动 | `0 2 * * 1` |
| `build-feed.yml` | Build Live Feed | push, 定时, 手动 | `23 */3 * * *` |
| `example-capture.yml` | Example Capture (not active) | 手动 |  |
| `intake-auto-review.yml` | Intake Auto Review | issues, 手动 |  |
| `intake-kind-audit.yml` | Intake Kind Audit | 定时, 手动 | `30 6 * * 1` |
| `intake-pipeline-test.yml` | Intake Pipeline Test (PRD ③) | 手动 |  |
| `intake-salvage-digest.yml` | Intake Salvage Digest | 定时, 手动 | `0 8 * * *` |
| `issue-intake-triage.yml` | MCP Intake Triage | issues, 手动 |  |
| `sync-d1.yml` | Sync Lessons to D1 (PRD ④) | push, 定时, 手动 | `0 3 * * *` |
| `sync-data.yml` | Sync Metadata to data Branch | push |  |
| `sync-question-answers.yml` | Sync Question Answers | 定时, 手动 | `20 7 * * *` |
| `update-badges.yml` | Update Badge Counts | push, 定时, 手动 | `23 3 * * 1` |
| `update-lessons.yml` | Update lessons.json | 定时, 手动 | `0 0 * * *` |

## 发布/部署（8）

| workflow | 用途 | 触发 | 定时 |
|---|---|---|---|
| `d1-bootstrap.yml` | D1 Bootstrap (PRD ④) | 手动 |  |
| `deploy-worker.yml` | Deploy Cloudflare Worker | push, 手动 |  |
| `docs.yml` | Deploy Documentation | PR, push |  |
| `fatal-guard-publish.yml` | Publish @misaka-net/fatal-guard | push |  |
| `fatal-guard.yml` | fatal-guard CI | PR, push, 手动 |  |
| `publish-container.yml` | Publish Container to GHCR | 手动, release |  |
| `release-please.yml` | Release Please | push |  |
| `release-pypi.yml` | Release to PyPI | push |  |

## 社区/机器人（12）

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

## 基础设施（2）

| workflow | 用途 | 触发 | 定时 |
|---|---|---|---|
| `ci-lesson-search.yml` | Search MisakaNet on CI Failure | workflow_run(任意失败) |  |
| `ci-self-heal.yml` | CI Self-Heal | 被调用 |  |

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
| ci-lesson-search / ci-self-heal 相关 | 检索质量巡检 / CI 自愈 | 输出即提交入口：把失败案例作为 lesson 提交，喂给知识库 |

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

