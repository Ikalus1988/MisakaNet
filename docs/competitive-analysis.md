# Competitive Analysis

> Last updated: 2026-08-21

## Competitors

| Competitor | Positioning | MisakaNet Differentiation |
|---|---|---|
| TeamMemory | MCP team experience memory | MisakaNet has redaction layer + failure classifier + demand board |
| WeKnora | Tencent RAG platform | MisakaNet focuses on agent failure memory, not general knowledge base |

## Detailed Analysis

See issues [#1162-#1168](https://github.com/Ikalus1988/MisakaNet/issues/1162) for detailed competitive analysis.

## Key Differentiators

1. **Failure-memory focus**: Not a general knowledge base, but specialized for agent failure recovery
2. **Redaction layer**: Automatic PII/secret removal before storage
3. **Demand board**: Intake clustering for maintainer prioritization
4. **Evidence levels**: E0-E4 trust scoring for lesson quality
5. **Git-backed**: No server required, works offline via local search

---

## Failure-memory relatives (Glama-listed)

MisakaNet is **not** a general memory system (Mem0 / agentmemory / Memorix etc. are
a different category — see [What this is NOT](#what-this-is-not) above). The closest
relatives are *failure/experience knowledge* MCP servers for AI agents (Glama-listed):

| Project | ⭐ | 定位（shared model） | 与 MisakaNet 差异 |
|---------|-----|---------------------|-------------------|
| **MisakaNet** | ![stars](https://img.shields.io/github/stars/Ikalus1988/MisakaNet?style=social) | Public Git-backed failure memory — indexed failure lessons, searchable by agents & humans | — |
| [deadends.dev](https://github.com/dbwls99706/deadends.dev) | ![stars](https://img.shields.io/github/stars/dbwls99706/deadends.dev?style=social) | Structured failure knowledge — dead ends, workarounds, error chains | 同类最接近：同样存"失败→解法"；差异：我们的 lesson 走 DCO 审校 + 证据分级 + 可全文搜索/基准护栏，且零依赖本地可查 |
| [Prior](https://github.com/cg3inc/prior_mcp) (io.cg3) | ![stars](https://img.shields.io/github/stars/cg3inc/prior_mcp?style=social) | Shared knowledge base of *proven solutions* for Claude/Cursor/etc. | 偏"已验证方案"经验交换，非专门失败记忆；我们按失败原语组织、命中可量化 |
| [Kira](https://github.com/aibenyclaude-coder/Kira) | ![stars](https://img.shields.io/github/stars/aibenyclaude-coder/Kira?style=social) | Auto-manages Skills & Scars (persistent failure warnings) for agents | Scars 偏"本次会话/项目级警告"；我们是跨项目、公开、可审计的失败课程库 |
| [Casebook-MCP](https://github.com/AgentPostmortem/Casebook-MCP) | ![stars](https://img.shields.io/github/stars/AgentPostmortem/Casebook-MCP?style=social) | Remote MCP over AgentPostmortem — registry of documented AI-agent failures | 同为 agent 故障复盘库；差异：我们带 intake 闭环 + 证据分级 + 课程可升格 contrib |
| [knownissue](https://github.com/gong8/knownissue) | ![stars](https://img.shields.io/github/stars/gong8/knownissue?style=social) | Shared debugging memory — search/report/patch/verify issues | 同为调试记忆共享；我们侧重"已审校 lesson 可检索复用"，非 issue 工单闭环 |
| [fix-memory-mcp](https://github.com/l111403717-cloud/fix-memory-mcp) | ![stars](https://img.shields.io/github/stars/l111403717-cloud/fix-memory-mcp?style=social) | Local-first coding fix memory for agents | 本地私有 fix 记忆；我们是公开共享 + 网络化检索 |
| [cogmem](https://github.com/dcondrey/cogmem) | ![stars](https://img.shields.io/github/stars/dcondrey/cogmem?style=social) | Self-improving, verifiable memory layer for coding agents | 通用 agent 记忆层；我们是失败知识专库，非会话/状态记忆 |

> Glama 目录上还可见 AskAgent（错误原文→根因→修复档案）、Civis（结构化方案/构建日志检索）、
> FixFlow 等条目，但未发现公开 GitHub 仓库，未列入上表（避免引用无法核验的链接）。
> 上表仅收录可核验仓库；⭐ 为写时快照。

> **MisakaNet is not the only shared failure-memory system.** Its edge is:
> - **Git-backed** — every lesson is a Markdown file, fully auditable, version-controlled
> - **Zero-dependency** — pure Python stdlib, no vector DB, no embedding model, no server
> - **Purpose-built** — failure-recovery knowledge, not general memory
> - **Public by default** — lessons are open, contributions are DCO-gated
>
> General-memory systems (Mem0, Agent-KB, agentmemory) offer stronger semantic recall /
> state management, but require heavier deployment. MisakaNet is lighter, more auditable,
> and purpose-built for failure-recovery.

> 📦 Core engine is **zero-dep** (pure Python stdlib). Optional extras: `pip install misakanet[semantic|hub|feishu]`.
> → [Architecture details](ARCHITECTURE.md) · [Benchmark: LessonReuseBench](docs/lesson-reuse-benchmark.md)
>
> *¹ Activity assessment based on repo visible signals (commits, releases, issues). As of 2026-08-12.*

_Table lifted from the README (2026-09-20); ⭐ counts are a snapshot from when it was written._
