# MisakaNet 3-Month Task Breakdown (Aug-Oct 2026)

> 主战略：AI agent 的 redacted failure-memory + intake + reuse layer

---

## P0：叙事收口（8月第1周）

| # | 任务 | 交付物 | 验收 |
|---|---|---|---|
| T1 | README 首屏只讲一个 use case | README.md 重写顶部 | 30秒内回答：这是什么？什么时候用？怎么试？ |
| T2 | Core/Optional 项目矩阵 | README.md 新增 "What is core?" 节 | 新访客不会误解成"全栈框架" |

**首屏文案：**
> MisakaNet is a redacted failure-memory layer for AI coding agents.
> Paste an error from Cursor, Claude Code, Codex, or CI.
> MisakaNet searches real failure-recovery lessons and returns a fix path.

**Core vs Optional：**
- Core: Search failure lessons, MCP access, Feedback intake
- Optional: fatal-guard, bench-core, VS Code/Cursor integrations, demand board

---

## P1：Intake 飞轮产品化（8月）

| # | 任务 | 交付物 | 验收 | 状态 |
|---|---|---|---|---|
| T3 | `misakanet capture` CLI | `scripts/misaka_capture.py` | `misakanet capture --summary "DCO failed" --context error.txt` 返回 id + redaction_summary | ❌ |
| T4 | GitHub Action capture 模板 | `.github/actions/misaka-capture/action.yml` | CI failure 时生成 redacted artifact，不自动发公网 | ❌ |
| T5 | contribution → lesson draft 转换 | `contribution_review.py convert` 命令 | 生成 `lessons/drafts/<slug>.md` 含 Problem/Root Cause/Fix/Verification/Redaction note | ❌ |
| T6 | --feedback 接入 intake | search_knowledge.py --feedback 写入 queue | 搜索后反馈进入 contribution_queue | ⏳ #622 |
| T7 | demand board 接入 Worker KV | register-proxy-sw.js endpoint | demand-board API 可用 | ❌ |
| T8 | trust semantics 统一 | README/docs/site | indexed/published/verified 含义一致 | ❌ |
| T9 | regression queries 补充 | data/regression_queries.json 20+ 条 | 覆盖 DCO/token/pip/MCP/Feishu/FANUC/WSL/CI | ❌ |
| T10 | contribution quality scorer 集成 | 提交时自动跑 quality_scorer.py | 低于 75 分的提交被拦截 | ❌ |

---

## P2：Runtime entry（9月）

| # | 任务 | 交付物 | 验收 |
|---|---|---|---|
| T11 | Cursor 失败场景规则 | `.cursor/rules/misakanet-failure-memory.mdc` + `docs/integrations/cursor-failure-memory.md` | README 有一键复制说明；遇错误时先 search MisakaNet |
| T12 | Claude Code failure playbook | `docs/integrations/claude-code-failure-memory.md` | 可直接粘进 CLAUDE.md；命令失败两次时触发 search |
| T13 | `misakanet run` wrapper | `scripts/misaka_run.py` | `misakanet run -- python -m pytest` 失败时输出 top 3 lessons；不自动重试 |
| T14 | entry point 验证 | 测试报告 | 至少 2 个真实失败场景下返回有用建议 |

**关键约束：** 先做"失败后建议"，不做"无感自愈中枢"。不自动重试，不自动修复。

---

## P2：i18n（9月，与 Runtime 并行）

| # | 任务 | 交付物 | 验收 |
|---|---|---|---|
| T15 | 韩语 lesson 入库 | 1 篇高质量韩语 lesson | quality_scorer ≥ 75（#651） |
| T16 | 日语 lesson 入库 | 1 篇高质量日语 lesson | quality_scorer ≥ 75（#652） |
| T17 | 语言元数据支持 | search_knowledge.py --lang | 按语言过滤搜索结果 |

---

## P3：Benchmark 背书（10月）

| # | 任务 | 交付物 | 验收 |
|---|---|---|---|
| T18 | agent self-healing mini benchmark | `bench/self-healing/` 10 个任务 | DCO/pip/token/MCP/encoding/pytest/deploy/schema/npm/stale-data |
| T19 | benchmark 报告 | `docs/reports/agent-self-healing-2026-10.md` | with vs without MisakaNet 有结果表 + 改善率 |
| T20 | bench-core 内部化 | benchmark 不绑主仓库 | 作为内部验证工具 |

---

## P3：外部分发（10月）

| # | 任务 | 交付物 | 验收 |
|---|---|---|---|
| T21 | MCP runtime verification | 部署后 tools/list 验证 | 所有 4 个 tool 可用 |
| T22 | server.json 元数据刷新 | description + version + counts 对齐 | 下一个真实 release 时做 |
| T23 | Glama 质量跟进 | score 页面更新 | 不破坏安装路径 |
| T24 | GitHub /mcp nomination packet | 准备材料 | Glama + PyPI + quickstart + benchmark 结果 |
| T25 | llms.txt 更新 | 反映 4 个 MCP tools + intake 能力 | 搜索引擎可索引 |

---

## 里程碑总览

| 月 | 主题 | 核心闭环 | 验收标准 |
|---|---|---|---|
| **8月** | 叙事收口 + Intake 产品化 | README 清晰 + capture CLI + queue→draft | 30秒理解 + `misakanet capture` 可用 + contribution 转 lesson draft |
| **9月** | Runtime entry + i18n | 失败后自动建议 | 至少 1 个 entry point 在真实失败场景下返回有用建议 |
| **10月** | Benchmark + Distribution | 有/无 MisakaNet 对比 | benchmark 报告 + MCP 验证通过 + 元数据一致 |

---

## 推荐执行顺序

```
Week 1:  T1 README首屏 → T2 项目矩阵
Week 2:  T3 capture CLI → T5 contribution→draft
Week 3:  T4 GitHub Action → T8 trust semantics → T9 regression queries
Week 4:  T6 --feedback → T7 demand board KV → T10 quality scorer
Week 5:  T11 Cursor rules → T12 Claude Code playbook
Week 6:  T13 misakanet run wrapper → T14 entry point 测试
Week 7:  T15 韩语 lesson → T16 日语 lesson → T17 语言过滤
Week 8:  T18 mini benchmark → T19 benchmark 报告
Week 9:  T21 MCP verification → T22 server.json → T23 Glama
Week 10: T24 /mcp packet → T25 llms.txt → T20 bench-core 内部化
```

---

## 不做的事（3个月内）

- ❌ 通用 Agent 框架 / 多编排器兼容
- ❌ 自动重试闭环默认开启
- ❌ 拆掉 fatal-guard
- ❌ VS Code extension 单独切出去
- ❌ benchmark 作为第一战略
- ❌ "全栈防御体系"叙事
- ❌ Smithery 恢复
- ❌ GitHub /mcp 强推
- ❌ 为了 listing polish 单独 bump 版本
