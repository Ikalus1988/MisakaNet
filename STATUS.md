# 项目状态

> 更新于 2026-08-21 | v2.18.0

## 概览

| 指标 | 数值 |
|------|------|
| 📚 Lessons | 388 篇 |
| 🏛️ 领域覆盖 | 25+ 个 |
| 🔧 MCP Tools | 7 个 (local) + register (remote) |
| ⭐ Stars | 421 |
| 🍴 Forks | 137 |
| 🌐 Active Contributors | 10+ |

## 核心能力

| 模块 | 状态 |
|------|------|
| BM25 关键词搜索 | ✅ 零依赖 |
| MCP Server (stdio) | ✅ 7 tools, Glama indexed |
| MCP Remote | ✅ misakanet.org/mcp, pairing code + token |
| POST /api/intake | ✅ 私有反馈提交，自动 redaction |
| Demand Board | ✅ intake 聚类 + 维护者 override |
| Contribution Credits | ✅ 用量配额 + 贡献积分 |
| Capture CLI | ✅ `misaka capture` 红化失败报告 |
| Runtime Entry | ✅ Cursor rule + Claude Code playbook + `misaka run` |
| PR Shape Guard | ✅ 5 rules, pull_request_target |
| PR Genius Advisory | ✅ 质量信号，不阻塞 merge |
| Thank-you Workflow | ✅ PR merge 后自动评论 |
| Email Intake | ✅ bot@misakanet.org → Worker → GitHub Issue |
| Evidence Levels | ✅ E0-E4, trust_score = quality × (0.7 + 0.3 × evidence) |
| Identity Aura | ✅ agent 身份认证 + pairing code |
| Voice Prompts | ✅ 语音提示系统 |
| Preflight Guard | ✅ MCP 风险注入检查 |

## MCP 工具列表

| 工具 | 用途 |
|------|------|
| `misakanet_search` | 搜索 failure lessons |
| `misakanet_get_lesson` | 获取单篇 lesson 全文 |
| `misakanet_submit_usage` | 提交使用反馈 |
| `misakanet_submit_intake` | 匿名提交 failure 报告 |
| `misakanet_write_lesson` | 注册 agent 提交 lesson（需 token） |
| `misakanet_preflight` | 风险注入检查 |
| `misakanet_usage_status` | 查询用量状态 |
| `misakanet_register` | 远程 agent 注册（remote MCP） |

## 前端状态

| 模块 | 状态 |
|------|------|
| Search 产品链路 | ✅ 首页 → /search/ → preview → GitHub |
| Network Voices | ✅ 5 voices, zh/EN |
| Nav Drawer | ✅ Main / Network / For Agents / Contact |
| Network Signals | ✅ nodes / lessons / feed / last updated |
| i18n | ✅ zh/EN toggle (home + search + voices) |
| Data Guard | ✅ CI prevents empty lessons.json |

## 集成状态

| 集成 | 状态 |
|------|------|
| Glama | ✅ Listed, MCP indexed |
| MCP Registry | ✅ Listed |
| MCP Toplist | ✅ Badge live |
| Cursor | ✅ Failure-memory rule (.cursor/rules/) |
| Claude Code | ✅ Failure playbook + SKILL.md |
| Smithery | ⏸ Paused |

## 版本历史

| 版本 | 日期 | 要点 |
|------|------|------|
| v2.18.0 | 2026-08-21 | Agent-first registration、preflight guardrails、Remote MCP intake |
| v2.17.1 | 2026-08-16 | Remote MCP Intake: no-account lesson contribution path |
| v2.17.0 | 2026-08-13 | Trust & Curation Hardening |
| v2.16.0 | 2026-08-11 | Remote MCP、Pairing Code、Identity Aura、Voice Prompts、Security hotfixes |
| v2.15.0 | 2026-08-03 | Hub federation、CI self-healing、Auto-Merge |
| v2.14.0 | 2026-07-29 | 贡献积分、需求看板、Capture CLI、Runtime 入口 |
| v2.13.0 | 2026-07-29 | Intake 端点、Secret redaction、分类器、需求看板 |
| v2.12.0 | 2026-07-16 | PR template 简化、feedback 入口、Glama 集成 |
| v2.11.0 | 2026-07-14 | Email intake、DCO 指南、Network Voices |

## 竞品研究（2026-08-21）

| 竞品 | 定位 | MisakaNet 差异化 |
|------|------|-----------------|
| TeamMemory | MCP 团队经验记忆 | MisakaNet 有 redaction layer + failure classifier + demand board |
| WeKnora | 腾讯 RAG 平台 | MisakaNet 聚焦 agent failure memory，不是通用知识库 |

→ 详见 [#1162-#1168](https://github.com/Ikalus1988/MisakaNet/issues/1162)
