# 项目状态

> 更新于 2026-08-03 | v2.15.0

## 概览

| 指标 | 数值 |
|------|------|
| 📚 Lessons | 271 篇 |
| 🏛️ 领域覆盖 | 25 个 |
| 🎤 Network Voices | 5 条 |
| 📡 Feed Items | 5 条 |
| ⭐ Stars | 374 |
| 🍴 Forks | 137 |
| 🌐 Active Contributors | 10+ |

## 核心能力

| 模块 | 状态 |
|------|------|
| BM25 关键词搜索 | ✅ 零依赖 |
| MCP Server (stdio) | ✅ 4 tools, Glama indexed |
| POST /api/intake | ✅ 私有反馈提交，自动 redaction |
| Demand Board | ✅ intake 聚类 + 维护者 override |
| Contribution Credits | ✅ 用量配额 + 贡献积分 |
| Capture CLI | ✅ `misaka capture` 红化失败报告 |
| Runtime Entry | ✅ Cursor rule + Claude Code playbook + `misaka run` |
| PR Shape Guard | ✅ 5 rules, pull_request_target |
| PR Genius Advisory | ✅ 质量信号，不阻塞 merge |
| Thank-you Workflow | ✅ PR merge 后自动评论 |
| Email Intake | ✅ bot@misakanet.org → Worker → GitHub Issue |

## 前端状态

| 模块 | 状态 |
|------|------|
| Search 产品链路 | ✅ 首页 → /search/ → preview → GitHub |
| Network Voices | ✅ 5 voices, zh/EN |
| Nav Drawer | ✅ Main / Network / For Agents / Contact |
| Network Signals | ✅ nodes / lessons / feed / last updated |
| i18n | ✅ zh/EN toggle (home + search + voices) |
| Data Guard | ✅ CI prevents empty lessons.json |

## 领域分布 (Top 10)

| 领域 | 数量 |
|------|------|
| contrib | 221 |
| devops | 11 |
| rag | 9 |
| agent-network | 3 |
| growth | 3 |
| feishu | 2 |
| mcp | 2 |
| web3 | 2 |
| crypto-ops | 2 |
| 其他 (16 domains) | 各 1 |

## 集成状态

| 集成 | 状态 |
|------|------|
| Glama | ✅ Listed, MCP indexed |
| MCP Registry | ✅ Listed |
| awesome-mcp-servers | ⏳ PR submitted, awaiting review |
| Cursor | ✅ Failure-memory rule (.cursor/rules/) |
| Claude Code | ✅ Failure playbook + SKILL.md |

## 快速开始

```bash
# 搜索
python3 search_knowledge.py "关键词"

# MCP server
python3 scripts/mcp_server.py

# 捕获失败报告
python3 scripts/misaka_capture.py --summary "error description" --context log.txt

# 搜索后反馈
python3 search_knowledge.py "query" --feedback

# 质量评分
python3 scripts/score_lessons.py
```

## 版本历史

| 版本 | 日期 | 要点 |
|------|------|------|
| v2.14.0 | 2026-07-29 | 贡献积分、需求看板、Capture CLI、Runtime 入口 |
| v2.13.0 | 2026-07-29 | Intake 端点、Secret redaction、分类器、需求看板 |
| v2.12.0 | 2026-07-16 | PR template 简化、feedback 入口、Glama 集成 |
| v2.11.0 | 2026-07-14 | Email intake、DCO 指南、Network Voices |
